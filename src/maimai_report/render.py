"""Build deterministic, private-by-default maimai session reports.

The renderer performs no network access. It accepts already-fetched JSON data,
adds display-only metadata, and embeds the report plus all presentation assets in
one HTML file. Optional native support checkout loads only after a click.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Mapping, Sequence
from importlib import resources
from pathlib import Path
from typing import Any

from .badges import badge_css
from .compatibility import enrich_report
from .io import atomic_write_text
from .preparation import PartyContext, PreparedReport, enrich_report_data, prepare_report
from .preparation import support_enabled as _support_enabled

ASSET_PACKAGE = "maimai_report.assets"
TEMPLATE_TOKENS = (
    "__CONTENT_SECURITY_POLICY__",
    "__FAVICON__",
    "__INLINE_CSS__",
    "__REPORT_JSON__",
    "__JACKET_JSON__",
    "__DOWNLOAD_JSON__",
    "__PARTY_JSON__",
    "__INLINE_JS__",
)
EXTERNAL_URL = re.compile(r"https?://", re.IGNORECASE)
SEALED_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; connect-src 'none'; font-src 'none'; media-src 'none'; "
    "object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"
)
SUPPORT_CONTENT_SECURITY_POLICY = (
    SEALED_CONTENT_SECURITY_POLICY.replace(
        "script-src 'unsafe-inline'",
        "script-src 'unsafe-inline' https://js.stripe.com https://*.js.stripe.com https://checkout.stripe.com",
    )
    .replace(
        "connect-src 'none'",
        "connect-src https://maimai.party https://api.stripe.com https://checkout.stripe.com "
        "https://link.com https://*.link.com",
    )
    .replace("img-src data:", "img-src data: https://*.stripe.com https://*.link.com")
    .replace(
        "frame-src 'none'",
        "frame-src https://js.stripe.com https://*.js.stripe.com https://hooks.stripe.com "
        "https://checkout.stripe.com https://link.com https://*.link.com",
    )
)


def report_content_security_policy(support: bool, hosted: bool = False) -> str:
    policy = SUPPORT_CONTENT_SECURITY_POLICY if support else SEALED_CONTENT_SECURITY_POLICY
    if hosted:
        policy = policy.replace("connect-src 'none'", "connect-src 'self'")
        if support:
            policy = policy.replace("connect-src ", "connect-src 'self' ", 1)
    return policy


_REPORT_DATA = re.compile(
    r'<script id="report-data" type="application/json">(.*?)</script>', re.DOTALL
)


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object and include the path in validation errors."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def json_for_html(value: object) -> str:
    """Encode JSON for an HTML script-data element without an escape hatch.

    Escaping ``<`` prevents an input string containing ``</script>`` from
    terminating the data element. The other substitutions avoid ambiguous HTML
    parsing and JavaScript line-separator behavior while remaining valid JSON.
    """

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        encoded.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def compact_json(value: object) -> str:
    """Compatibility alias for the source renderer's compact encoder."""

    return json_for_html(value)


def support_enabled_in_html(html: str) -> bool:
    """Read the explicit report flag; malformed or unrelated HTML grants nothing."""
    matches = _REPORT_DATA.findall(html)
    if len(matches) != 1:
        return False
    try:
        report = json.loads(matches[0])
    except (ValueError, RecursionError):
        return False
    return isinstance(report, dict) and report.get("support") is True


def validate_generated_html(html: str) -> None:
    """Allow external project links only in the exact bundled controllers."""
    matches = _REPORT_DATA.findall(html)
    if len(matches) != 1:
        raise ValueError("Generated report must contain one report-data element")
    try:
        report = json.loads(matches[0])
    except (ValueError, RecursionError) as exc:
        raise ValueError("Generated report contains invalid report data") from exc
    if not isinstance(report, dict):
        raise ValueError("Generated report data must be an object")
    enabled = _support_enabled(report.get("support"))
    policy = report_content_security_policy(
        enabled, report.get("partyIntegration", {}).get("hosted") is True
    )
    marker = f'<meta http-equiv="Content-Security-Policy" content="{policy}" />'
    if html.count(marker) != 1:
        raise ValueError("Generated report must contain its expected content security policy")
    inspected = html.replace(marker, "", 1)
    controller = _party_controller()
    if "partyIntegration" in report and inspected.count(controller) != 1:
        raise ValueError("Generated report must contain its fixed-origin party controller")
    inspected = inspected.replace(controller, "", 1)
    if enabled:
        controller = _asset_text("support.js")
        if inspected.count(controller) != 1:
            raise ValueError("Generated report must contain its developer support controller")
        inspected = inspected.replace(controller, "", 1)
    if EXTERNAL_URL.search(inspected):
        raise ValueError("Generated report contains an unapproved external HTTP or HTTPS URL")


def _asset_text(name: str) -> str:
    return resources.files(ASSET_PACKAGE).joinpath(name).read_text(encoding="utf-8")


def _party_controller() -> str:
    return _asset_text("party-report.js").replace(
        "__PARTY_WORDMARK__", json_for_html(_asset_text("party-site-brand.html"))
    )


def _jacket_data(jackets: Mapping[str, str] | None) -> dict[str, str]:
    """Accept already prepared raster thumbnails only; never fetch image URLs."""

    if jackets is None:
        return {}
    if not isinstance(jackets, Mapping):
        raise ValueError("Jackets must map song IDs to embedded raster thumbnails")
    result = {}
    for song_id, image in jackets.items():
        if not isinstance(song_id, str) or not isinstance(image, str):
            raise ValueError("Jacket keys and images must be strings")
        match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", image)
        if not match:
            raise ValueError("Jackets must be base64 PNG, JPEG, or WebP data images")
        try:
            decoded = base64.b64decode(match[2], validate=True)
        except binascii.Error as exc:
            raise ValueError("Invalid jacket base64") from exc
        valid = {
            "png": decoded.startswith(b"\x89PNG\r\n\x1a\n"),
            "jpeg": decoded.startswith(b"\xff\xd8\xff"),
            "webp": decoded.startswith(b"RIFF") and decoded[8:12] == b"WEBP",
        }
        if not valid[match[1]] or len(decoded) > 204_800:
            raise ValueError("Jackets must be raster thumbnails no larger than 200 KiB")
        result[song_id] = image
    return result


def build_html(
    report: Mapping[str, Any],
    *,
    jackets: Mapping[str, str] | None = None,
    b50_path: str | None = None,
    b50_unavailable: bool = False,
    badge_pack: Path | str | None = None,
    party_enabled: bool | None = None,
    party_latest_path: str | None = None,
) -> str:
    """Compatibility entry point: prepare data, then assemble one offline report."""
    return render_prepared(
        prepare_report(report, party_enabled=party_enabled, party_latest_path=party_latest_path),
        jackets=jackets,
        b50_path=b50_path,
        b50_unavailable=b50_unavailable,
        badge_pack=badge_pack,
    )


def render_prepared(
    prepared: PreparedReport,
    *,
    jackets: Mapping[str, str] | None = None,
    b50_path: str | None = None,
    b50_unavailable: bool = False,
    badge_pack: Path | str | None = None,
) -> str:
    """Assemble the existing assets without deriving or fetching domain data."""
    if not isinstance(prepared, PreparedReport):
        raise ValueError("Expected a prepared report")
    if b50_path is not None and not re.fullmatch(r"(?:/[A-Za-z0-9_-]+/)?b50\.webp", b50_path):
        raise ValueError("B50 downloads must use the installation's local b50.webp path")
    if b50_path and b50_unavailable:
        raise ValueError("A B50 download cannot also be unavailable")
    report_data, party_settings = prepared.data, prepared.party
    support = prepared.support
    content_security_policy = report_content_security_policy(support, prepared.hosted)

    template = _asset_text("template.html")
    substitutions = {
        "__CONTENT_SECURITY_POLICY__": content_security_policy,
        "__FAVICON__": _asset_text("favicon.html"),
        "__INLINE_CSS__": "\n\n".join(
            (
                _asset_text("styles.css"),
                badge_css(badge_pack),
                _asset_text("support.css"),
                _asset_text("party-site-brand.css"),
                _asset_text("party-report.css"),
            )
        ),
        "__REPORT_JSON__": json_for_html(report_data),
        "__JACKET_JSON__": json_for_html(_jacket_data(jackets)),
        "__DOWNLOAD_JSON__": json_for_html({"href": b50_path, "unavailable": b50_unavailable}),
        "__PARTY_JSON__": json_for_html(party_settings),
        "__INLINE_JS__": _party_controller()
        + "\n\n"
        + _asset_text("app.js")
        + ("\n\n" + _asset_text("support.js") if support else ""),
    }
    for token in TEMPLATE_TOKENS:
        count = template.count(token)
        if count != 1:
            raise ValueError(f"Report template must contain {token} exactly once; found {count}")

    token_pattern = re.compile("|".join(map(re.escape, TEMPLATE_TOKENS)))
    html = token_pattern.sub(lambda match: substitutions[match.group(0)], template)

    validate_generated_html(html)
    return html


def write_prepared(prepared: PreparedReport, output_path: Path, **presentation) -> Path:
    """Write an already prepared report without recomputing recommendations."""
    output_path = Path(output_path)
    atomic_write_text(output_path, render_prepared(prepared, **presentation))
    return output_path


def render_report(
    report: Mapping[str, Any],
    output_path: Path,
    *,
    jackets: Mapping[str, str] | None = None,
    b50_path: str | None = None,
    b50_unavailable: bool = False,
    badge_pack: Path | str | None = None,
    party_enabled: bool | None = None,
    party_latest_path: str | None = None,
) -> Path:
    """Write a report to ``output_path`` and return that path."""

    output_path = Path(output_path)
    atomic_write_text(
        output_path,
        build_html(
            report,
            jackets=jackets,
            b50_path=b50_path,
            b50_unavailable=b50_unavailable,
            badge_pack=badge_pack,
            party_enabled=party_enabled,
            party_latest_path=party_latest_path,
        ),
    )
    return output_path


def render(report: Mapping[str, Any], output_path: Path) -> Path:
    """Compatibility wrapper matching the source renderer's public operation."""

    return render_report(report, output_path)


def render_from_files(
    report_input_path: Path,
    after_pbs_path: Path | None,
    output_path: Path,
    *,
    player: Mapping[str, str] | None = None,
    current_version_display_names: Sequence[str] | None = None,
    support: bool | None = None,
    jackets: Mapping[str, str] | None = None,
    badge_pack: Path | str | None = None,
) -> Path:
    """Read local JSON inputs, enrich them, and write a private report."""

    report = read_json(Path(report_input_path))
    after_payload = read_json(Path(after_pbs_path)) if after_pbs_path is not None else None
    enriched = enrich_report_data(
        report,
        after_payload,
        player=player,
        current_version_display_names=current_version_display_names,
        support=support,
    )
    from .player_capture import from_documents

    prepared = prepare_report(
        enriched, context=PartyContext(from_documents(enriched, after_payload))
    )
    return write_prepared(prepared, Path(output_path), jackets=jackets, badge_pack=badge_pack)


def render_demo(
    output_path: Path,
    *,
    scenario: str = "complete",
    badge_pack: Path | str | None = None,
    support: bool = True,
) -> Path:
    """Render a bundled synthetic scenario without credentials or network access."""

    from .fixtures import load_scenario
    from .fixtures.artwork import demo_jackets

    report, after_payload = load_scenario(scenario)
    from .player_capture import from_documents

    enriched = enrich_report_data(report, after_payload, support=support)
    prepared = prepare_report(
        enriched, context=PartyContext(from_documents(enriched, after_payload))
    )
    return write_prepared(
        prepared,
        Path(output_path),
        jackets=demo_jackets(after_payload),
        badge_pack=badge_pack,
    )


__all__ = [
    "build_html",
    "compact_json",
    "enrich_report",
    "json_for_html",
    "read_json",
    "render",
    "render_demo",
    "render_from_files",
    "render_report",
    "validate_generated_html",
]

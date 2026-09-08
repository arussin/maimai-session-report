"""Build deterministic, private-by-default maimai session reports.

The renderer performs no network access. It accepts already-fetched JSON data,
adds display-only metadata, and embeds the report plus all presentation assets in
one HTML file. Reports remain fully sealed unless an optional, explicitly
configured Buy Me a Coffee checkout frame is enabled.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from importlib import resources
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .badges import badge_css
from .io import atomic_write_text

ASSET_PACKAGE = "maimai_report.assets"
TEMPLATE_TOKENS = (
    "__CONTENT_SECURITY_POLICY__",
    "__INLINE_CSS__",
    "__REPORT_JSON__",
    "__JACKET_JSON__",
    "__DOWNLOAD_JSON__",
    "__INLINE_JS__",
)
EXTERNAL_URL = re.compile(r"https?://", re.IGNORECASE)
BUY_ME_A_COFFEE_ORIGIN = "https://buymeacoffee.com"
BUY_ME_A_COFFEE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
SEALED_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; connect-src 'none'; font-src 'none'; media-src 'none'; "
    "object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'"
)
BUY_ME_A_COFFEE_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; connect-src 'none'; font-src 'none'; media-src 'none'; "
    f"object-src 'none'; frame-src {BUY_ME_A_COFFEE_ORIGIN}; base-uri 'none'; "
    "form-action 'none'"
)
_SUPPORT_KEYS = {"provider", "id", "label", "description", "color"}


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


def _payload_body(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    body = payload.get("body")
    if isinstance(body, Mapping):
        return body
    if all(key in payload for key in ("pbs", "charts", "songs")):
        return payload
    raise ValueError("after-pbs JSON must contain a body object with pbs, charts, and songs")


def _make_maps(
    body: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    charts = body.get("charts")
    songs = body.get("songs")
    if not isinstance(charts, list) or not isinstance(songs, list):
        raise ValueError("after-pbs JSON is missing the charts or songs list")

    chart_map = {
        chart["chartID"]: chart
        for chart in charts
        if isinstance(chart, Mapping) and isinstance(chart.get("chartID"), str)
    }
    song_map = {
        song["id"]: song
        for song in songs
        if isinstance(song, Mapping) and isinstance(song.get("id"), str)
    }
    return chart_map, song_map


def _rate_value(record: Mapping[str, Any]) -> int:
    calculated = record.get("calculatedData")
    if not isinstance(calculated, Mapping):
        return 0
    value = calculated.get("rate")
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _display_version(
    record: Mapping[str, Any], chart_map: Mapping[str, Mapping[str, Any]]
) -> str | None:
    chart = chart_map.get(record.get("chartID"), {})
    chart_data = chart.get("data")
    if not isinstance(chart_data, Mapping):
        return None
    value = chart_data.get("displayVersion")
    return value if isinstance(value, str) else None


def _compact_record(
    record: Mapping[str, Any],
    chart_map: Mapping[str, Mapping[str, Any]],
    song_map: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    chart = chart_map.get(record.get("chartID"), {})
    song = song_map.get(record.get("songID"), {})
    if not song and isinstance(chart.get("song"), Mapping):
        song = chart["song"]

    score_data = record.get("scoreData")
    score_data = score_data if isinstance(score_data, Mapping) else {}
    optional = score_data.get("optional")
    optional = optional if isinstance(optional, Mapping) else {}
    judgements = score_data.get("judgements")
    judgements = judgements if isinstance(judgements, Mapping) else {}
    calculated = record.get("calculatedData")
    calculated = calculated if isinstance(calculated, Mapping) else {}
    chart_data = chart.get("data")
    chart_data = chart_data if isinstance(chart_data, Mapping) else {}

    return {
        "chartID": record.get("chartID"),
        "songID": record.get("songID"),
        "title": song.get("title"),
        "artist": song.get("artist"),
        "difficulty": chart.get("difficulty"),
        "level": chart.get("level"),
        "levelNum": chart.get("levelNum"),
        "displayVersion": chart_data.get("displayVersion"),
        "percent": score_data.get("percent"),
        "rate": calculated.get("rate"),
        "grade": score_data.get("grade"),
        "lamp": score_data.get("lamp"),
        "fast": optional.get("fast"),
        "slow": optional.get("slow"),
        "miss": judgements.get("miss"),
        "good": judgements.get("good"),
        "great": judgements.get("great"),
        "perfect": judgements.get("perfect"),
        "pcrit": judgements.get("pcrit"),
        "timeAchieved": record.get("timeAchieved"),
    }


def _version_names(
    report: Mapping[str, Any], explicit: Sequence[str] | None, *, required: bool
) -> list[str]:
    values: object = explicit if explicit is not None else report.get("currentNewDisplayVersions")
    if values is None:
        if required:
            raise ValueError(
                "Current-version display names are required to classify the New 15 pool"
            )
        return []
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError("Current-version display names must be a list of non-empty strings")
    names = sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})
    if not names:
        raise ValueError("At least one current-version display name is required")
    if len(names) != len(values):
        invalid = [value for value in values if not isinstance(value, str) or not value.strip()]
        if invalid:
            raise ValueError("Current-version display names must be non-empty strings")
    return names


def _player_data(existing: object, overlay: Mapping[str, str] | None) -> dict[str, str]:
    result: dict[str, str] = {
        "username": "player",
        "displayName": "Player",
        "timezone": "UTC",
        "game": "maimai DX",
    }
    if existing is not None:
        if not isinstance(existing, Mapping):
            raise ValueError("report-input player value must be an object")
        for key in result:
            value = existing.get(key)
            if isinstance(value, str) and value.strip():
                result[key] = value.strip()
    if overlay is not None:
        aliases = {"display_name": "displayName"}
        for input_key, value in overlay.items():
            key = aliases.get(input_key, input_key)
            if key in result:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"Player {input_key!r} must be a non-empty string")
                result[key] = value.strip()
    if result["displayName"] == "Player" and result["username"] != "player":
        result["displayName"] = result["username"]
    if result["timezone"] != "UTC":
        try:
            ZoneInfo(result["timezone"])
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(
                f"Unknown or unavailable IANA timezone {result['timezone']!r}; correct "
                "the name, or on Windows install the project's 'timezone' extra"
            ) from exc
    return result


def _support_text(value: object, *, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Support {field} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValueError(f"Support {field} is too long (maximum {maximum} characters)")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError(f"Support {field} may not contain control characters")
    return normalized


def _support_data(value: object) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("Support configuration must be an object")
    unknown = sorted(set(value) - _SUPPORT_KEYS)
    if unknown:
        raise ValueError("Unknown support configuration key(s): " + ", ".join(unknown))

    provider = _support_text(value.get("provider"), field="provider", maximum=40)
    if provider != "buy_me_a_coffee":
        raise ValueError("Unsupported support provider; expected buy_me_a_coffee")

    account_id = _support_text(value.get("id"), field="id", maximum=128)
    if not BUY_ME_A_COFFEE_ID.fullmatch(account_id):
        raise ValueError(
            "Invalid Buy Me a Coffee ID; use letters, digits, dots, underscores, or hyphens"
        )

    label = _support_text(value.get("label"), field="label", maximum=80)
    description = _support_text(value.get("description"), field="description", maximum=200)
    color = _support_text(value.get("color"), field="color", maximum=7)
    if not HEX_COLOR.fullmatch(color):
        raise ValueError("Support color must be a six-digit hexadecimal color such as #5F7FFF")

    return {
        "provider": provider,
        "id": account_id,
        "label": label,
        "description": description,
        "color": color.upper(),
    }


def enrich_report(
    report: dict[str, Any],
    after_payload: dict[str, Any] | None = None,
    *,
    player: Mapping[str, str] | None = None,
    current_version_display_names: Sequence[str] | None = None,
    support: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return a display-ready copy of an existing report input.

    When an after-PBs response is supplied, all current-version PBs are compacted
    into ``after.newPool`` for target suggestions. No input object is mutated.
    """

    if not isinstance(report, dict):
        raise ValueError("report-input JSON must be an object")
    result = deepcopy(report)
    versions = _version_names(
        result,
        current_version_display_names,
        required=after_payload is not None,
    )
    if versions:
        result["currentNewDisplayVersions"] = versions

    after = result.setdefault("after", {})
    if not isinstance(after, dict):
        raise ValueError("report-input after value must be an object")

    if after_payload is not None:
        if not isinstance(after_payload, dict):
            raise ValueError("after-pbs JSON must be an object")
        body = _payload_body(after_payload)
        pbs = body.get("pbs")
        if not isinstance(pbs, list):
            raise ValueError("after-pbs JSON is missing the pbs list")
        chart_map, song_map = _make_maps(body)
        version_set = set(versions)
        new_pool = [
            pb
            for pb in pbs
            if isinstance(pb, Mapping) and _display_version(pb, chart_map) in version_set
        ]
        # Python's stable sort preserves the upstream PB order for equal rates.
        # The original report used that order, so retaining it avoids a visual
        # reshuffle during migration while still ranking higher rates first.
        new_pool.sort(key=_rate_value, reverse=True)
        after["newPool"] = [_compact_record(pb, chart_map, song_map) for pb in new_pool]

    session = result.setdefault("session", {})
    if not isinstance(session, dict):
        raise ValueError("report-input session value must be an object")
    scores = session.get("scores", [])
    if not isinstance(scores, list):
        raise ValueError("report-input session scores must be a list")
    achieved_times = [
        item["timeAchieved"]
        for item in scores
        if isinstance(item, Mapping)
        and isinstance(item.get("timeAchieved"), int)
        and not isinstance(item.get("timeAchieved"), bool)
    ]
    session["startTimeAchieved"] = min(achieved_times) if achieved_times else None
    session["endTimeAchieved"] = max(achieved_times) if achieved_times else None

    if support is not None:
        result["support"] = _support_data(support)
    elif "support" in result:
        normalized_support = _support_data(result["support"])
        if normalized_support is None:
            result.pop("support", None)
        else:
            result["support"] = normalized_support

    result["schemaVersion"] = 1
    result["player"] = _player_data(result.get("player"), player)
    result.setdefault("ratingVersionAssumption", "Configured current-version B35/N15")
    return result


def _asset_text(name: str) -> str:
    return resources.files(ASSET_PACKAGE).joinpath(name).read_text(encoding="utf-8")


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
) -> str:
    """Return one deterministic HTML document with a fail-closed runtime policy."""

    if not isinstance(report, Mapping):
        raise ValueError("Report must be an object")
    if b50_path is not None and not re.fullmatch(r"(?:/[A-Za-z0-9_-]+/)?b50\.webp", b50_path):
        raise ValueError("B50 downloads must use the installation's local b50.webp path")
    if b50_path and b50_unavailable:
        raise ValueError("A B50 download cannot also be unavailable")

    report_data = deepcopy(dict(report))
    support = _support_data(report_data.get("support"))
    if support is None:
        report_data.pop("support", None)
        content_security_policy = SEALED_CONTENT_SECURITY_POLICY
    else:
        report_data["support"] = support
        content_security_policy = BUY_ME_A_COFFEE_CONTENT_SECURITY_POLICY

    template = _asset_text("template.html")
    substitutions = {
        "__CONTENT_SECURITY_POLICY__": content_security_policy,
        "__INLINE_CSS__": "\n\n".join(
            (_asset_text("styles.css"), badge_css(badge_pack), _asset_text("support.css"))
        ),
        "__REPORT_JSON__": json_for_html(report_data),
        "__JACKET_JSON__": json_for_html(_jacket_data(jackets)),
        "__DOWNLOAD_JSON__": json_for_html({"href": b50_path, "unavailable": b50_unavailable}),
        "__INLINE_JS__": _asset_text("app.js") + "\n\n" + _asset_text("support.js"),
    }
    for token in TEMPLATE_TOKENS:
        count = template.count(token)
        if count != 1:
            raise ValueError(f"Report template must contain {token} exactly once; found {count}")

    token_pattern = re.compile("|".join(map(re.escape, TEMPLATE_TOKENS)))
    html = token_pattern.sub(lambda match: substitutions[match.group(0)], template)

    inspected_html = html
    if support is not None:
        inspected_html = inspected_html.replace(BUY_ME_A_COFFEE_ORIGIN, "")
    if EXTERNAL_URL.search(inspected_html):
        raise ValueError("Generated report contains an unapproved external HTTP or HTTPS URL")
    return html


def render_report(
    report: Mapping[str, Any],
    output_path: Path,
    *,
    jackets: Mapping[str, str] | None = None,
    b50_path: str | None = None,
    b50_unavailable: bool = False,
    badge_pack: Path | str | None = None,
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
    support: Mapping[str, str] | None = None,
    jackets: Mapping[str, str] | None = None,
    badge_pack: Path | str | None = None,
) -> Path:
    """Read local JSON inputs, enrich them, and write a private report."""

    report = read_json(Path(report_input_path))
    after_payload = read_json(Path(after_pbs_path)) if after_pbs_path is not None else None
    enriched = enrich_report(
        report,
        after_payload,
        player=player,
        current_version_display_names=current_version_display_names,
        support=support,
    )
    return render_report(enriched, Path(output_path), jackets=jackets, badge_pack=badge_pack)


def render_demo(
    output_path: Path, *, scenario: str = "complete", badge_pack: Path | str | None = None
) -> Path:
    """Render a bundled synthetic scenario without credentials or network access."""

    from .fixtures import load_scenario
    from .fixtures.artwork import demo_jackets

    report, after_payload = load_scenario(scenario)
    return render_report(
        enrich_report(report, after_payload),
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
]

"""Prepare and verify a protected Worker; deployment is an explicit workflow step."""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from ..history.bundle import ArchiveError, canonical, report_data, sha256
from ..history.cloudflare import D1, R2, Cloudflare, NoRedirects, required
from ..history.setup import bindings, verify_private_bucket
from ..history.support import history_support
from ..render import ASSET_PACKAGE, json_for_html
from .config import Instance


def check(condition: object, message: str) -> None:
    if not condition:
        raise ArchiveError(message)


class ProviderError(ArchiveError):
    def __init__(self, status: int):
        self.status = status
        super().__init__(f"Cloudflare deployment request failed (HTTP {status})")


class WorkerAPI:
    def __init__(self, instance: Instance, environ: dict | None = None):
        self.instance = instance
        self.token = required(os.environ if environ is None else environ, "CLOUDFLARE_API_TOKEN")

    def read(self, path: str, *, raw: bool = False):
        check(
            path.startswith(("/accounts/", "/zones/")) and ".." not in path,
            "Unsupported management endpoint",
        )
        request = urllib.request.Request(  # noqa: S310 -- fixed Cloudflare management origin
            "https://api.cloudflare.com/client/v4" + path,
            headers={"Authorization": "Bearer " + self.token, "Accept": "application/json"},
        )
        try:
            with urllib.request.build_opener(NoRedirects()).open(request, timeout=30) as response:
                content = response.read(30 * 1024 * 1024 + 1)
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            raise ProviderError(exc.code) from None
        except urllib.error.URLError:
            raise ArchiveError("Cloudflare deployment connection failed") from None
        check(len(content) <= 30 * 1024 * 1024, "Cloudflare response exceeded the read bound")
        if raw:
            return content, content_type
        payload = json.loads(content)
        check(payload.get("success") is True, "Cloudflare rejected the deployment read")
        return payload["result"]

    def state(self, endpoint: str):
        check(
            endpoint in {"settings", "subdomain", "deployments", "content/v2"},
            "Unsupported Worker read",
        )
        instance = self.instance
        return self.read(
            f"/accounts/{instance.account_id}/workers/scripts/{instance.worker_name}/{endpoint}",
            raw=endpoint == "content/v2",
        )

    def routes(self, *, bootstrap: bool = False) -> list:
        instance = self.instance
        zone = self.read(f"/zones/{instance.zone_id}")
        check(
            zone.get("account", {}).get("id") == instance.account_id,
            "Configured zone belongs to another account",
        )
        routes = self.read(f"/zones/{instance.zone_id}/workers/routes")
        check(isinstance(routes, list), "Worker routes are unavailable")
        owned = [row for row in routes if row.get("script") == instance.worker_name]
        exact = [row for row in routes if row.get("pattern") == instance.route["pattern"]]
        check(
            all(row.get("script") == instance.worker_name for row in exact),
            "Configured route is assigned to a different Worker",
        )
        check(
            all(row.get("pattern") == instance.route["pattern"] for row in owned),
            "Worker has unrelated routes that need explicit preservation",
        )
        check(
            (bootstrap and not owned and not exact) or (len(owned) == len(exact) == 1),
            "Expected protected Worker route is missing or duplicated",
        )
        domains = self.read(f"/accounts/{instance.account_id}/workers/domains")
        check(
            isinstance(domains, list)
            and not any(row.get("service") == instance.worker_name for row in domains),
            "Worker has a custom domain outside the protected installation route",
        )
        return owned


def parse_modules(raw: bytes, content_type: str) -> dict[str, bytes]:
    check("\r" not in content_type and "\n" not in content_type, "Invalid multipart content type")
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + raw
    )
    check(message.is_multipart(), "Expected multipart Worker modules")
    modules = {}
    for part in message.iter_parts():
        name = part.get_filename() or part.get_param("name", header="content-disposition")
        if name:
            check(name not in modules, "Duplicate Worker module name")
            body = part.get_payload(decode=True)
            check(isinstance(body, bytes), "Worker module is not bytes")
            modules[name] = body
    check(modules, "Worker has no downloadable modules")
    return modules


def module_named(modules: dict, suffix: str, *, optional: bool = False) -> bytes | None:
    values = [value for name, value in modules.items() if name.endswith(suffix)]
    if optional and not values:
        return None
    check(len(values) == 1, "Expected exactly one retained " + suffix + " module")
    return values[0]


def verify_bindings(settings: dict, instance: Instance) -> None:
    expected = (
        {
            "HISTORY_OBJECTS": ("r2_bucket", "bucket_name", instance.bucket),
            "HISTORY_DB": ("d1", "id", instance.database_id),
            "HISTORY_SCOPE": ("plain_text", "text", instance.scope),
            "HISTORY_ORIGIN": ("plain_text", "text", instance.origin),
            "HISTORY_PREFIX": ("plain_text", "text", instance.prefix),
        }
        if instance.history_enabled
        else {}
    )
    actual = settings.get("bindings")
    check(isinstance(actual, list), "Worker binding list is unavailable")
    check(
        len(actual) == len(expected) and {r.get("name") for r in actual} == set(expected),
        "Missing, duplicate or unrelated Worker bindings need explicit review",
    )
    for row in actual:
        kind, field, value = expected[row["name"]]
        check(
            row.get("type") == kind and row.get(field) == value,
            "Worker binding differs from the configured private resource",
        )


def verify_domains(api: WorkerAPI) -> None:
    state = api.state("subdomain")
    check(
        state.get("enabled") is False and state.get("previews_enabled") is False,
        "Public Worker and preview URLs must remain disabled",
    )


class AccessRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verify_access(instance: Instance) -> None:
    prefix = instance.prefix
    paths = [prefix.rstrip("/"), prefix, prefix + "index.html", prefix + "b50.webp"]
    if instance.history_enabled:
        paths += [
            prefix + "history",
            prefix + "history/",
            prefix + "history/c/" + "0" * 64 + "/",
            prefix + "history/c/" + "0" * 64 + "/b50.webp",
        ]
    for path in paths:
        request = urllib.request.Request(instance.origin + path, method="GET")  # noqa: S310 -- validated exact HTTPS origin, no credentials
        try:
            with urllib.request.build_opener(AccessRedirects()).open(request, timeout=30):
                raise ArchiveError(
                    "Signed-out request reached the report; verify Cloudflare Access"
                )
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                continue
            target = urlsplit(exc.headers.get("Location", ""))
            check(
                exc.code in {302, 303, 307, 308}
                and target.scheme == "https"
                and (target.hostname or "").endswith(".cloudflareaccess.com"),
                "Expected a Cloudflare Access login or denial; arbitrary redirects do not pass",
            )
        except urllib.error.URLError:
            raise ArchiveError("Could not verify signed-out Cloudflare Access") from None


def verify_retained_copies(instance: Instance, html: bytes, b50: bytes | None) -> str:
    api = Cloudflare(instance.account_id, required(os.environ, "CLOUDFLARE_HISTORY_API_TOKEN"))
    latest = None
    for database_id, bucket in (
        (instance.database_id, instance.bucket),
        (instance.recovery_database_id, instance.backup_bucket),
    ):
        verify_private_bucket(api, bucket)
        rows = D1(api, database_id).query(
            "SELECT c.id,c.report_key,c.report_hash,c.b50_key,c.b50_hash "
            "FROM captures c JOIN archive_state s ON s.latest_id=c.id "
            "WHERE s.scope=? AND c.scope=? AND c.state='ready' AND c.meaningful=1",
            (instance.scope, instance.scope),
        )
        check(len(rows) == 1, "A verified meaningful latest capture is required in both indexes")
        row = rows[0]
        check(
            row["report_hash"] == sha256(html)
            and row["b50_hash"] == (sha256(b50) if b50 else None),
            "Live fallback differs from retained history; stop before publication",
        )
        if latest is not None:
            check(row == latest, "Primary and recovery latest pointers differ")
        latest = row
        objects = R2(instance.account_id, bucket)
        check(
            objects.get(row["report_key"]) == html,
            "Hosted report bytes differ from the live fallback",
        )
        if b50 is not None:
            check(
                objects.get(row["b50_key"]) == b50, "Hosted B50 bytes differ from the live fallback"
            )
    return latest["id"]


def stage(
    instance: Instance,
    destination: Path,
    core: Path,
    html: bytes,
    b50: bytes | None,
    *,
    settings: dict | None = None,
    bootstrap: bool = False,
) -> dict:
    instance.validate("stage")
    report_data(html)  # Retained HTML must expose the documented report payload.
    if instance.b50_mode == "required" and not bootstrap:
        check(b50 is not None, "This installation requires a retained B50")
    if b50 is not None:
        check(b50[:4] == b"RIFF" and b50[8:12] == b"WEBP", "Retained B50 is not a WebP")
    check(
        not destination.exists() or not any(destination.iterdir()),
        "Stage into an empty directory to prevent stale module reuse",
    )
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "report.html").write_bytes(html)
    if b50 is not None:
        (destination / "b50.webp").write_bytes(b50)
    for source, target in (
        ("hosted.js", "hosted.js"),
        ("history.js", "history-reader.js"),
        ("security.js", "security.js"),
    ):
        shutil.copyfile(core / "deploy/cloudflare/src" / source, destination / target)
    support = history_support(html)
    (destination / "support.js").write_text("export default " + json.dumps(support) + ";\n")
    config = {
        "origin": instance.origin,
        "prefix": instance.prefix,
        "scope": instance.scope,
        "historyEnabled": instance.history_enabled,
    }
    (destination / "worker.js").write_text(
        "import report from './report.html';\n"
        + ("import b50 from './b50.webp';\n" if b50 is not None else "const b50 = null;\n")
        + "import support from './support.js';\nimport {createHostedWorker} from './hosted.js';\n"
        + "export default createHostedWorker(report, b50, support, "
        + json.dumps(config)
        + ");\n"
    )
    previous = settings or {}
    wrangler = {
        "name": instance.worker_name,
        "account_id": instance.account_id,
        "main": "worker.js",
        "compatibility_date": previous.get("compatibility_date", "2026-08-31"),
        "compatibility_flags": previous.get("compatibility_flags", ["nodejs_compat"]),
        "workers_dev": False,
        "preview_urls": False,
        "send_metrics": False,
        "dependencies_instrumentation": {"enabled": False},
        "observability": {"enabled": False},
        "routes": [instance.route],
        "rules": [
            {"type": "Text", "globs": ["**/*.html"], "fallthrough": True},
            {"type": "Data", "globs": ["**/*.webp"], "fallthrough": True},
        ],
    }
    if previous.get("limits"):
        wrangler["limits"] = previous["limits"]
    if instance.history_enabled:
        wrangler.update(bindings(instance.history_config()))
    (destination / "wrangler.generated.json").write_bytes(canonical(wrangler))
    manifest = {
        "identity": instance.identity(),
        "reportSha256": sha256(html),
        "b50Sha256": sha256(b50) if b50 else None,
        "files": {p.name: sha256(p.read_bytes()) for p in destination.iterdir()},
        "scoreImportStarted": False,
        "workerDeployed": False,
        "bootstrap": bootstrap,
    }
    (destination / "staged.json").write_bytes(canonical(manifest))
    return manifest


def prepare_release(
    instance: Instance, destination: Path, core: Path, *, source: Path | None = None
) -> dict:
    instance.validate("prepare-release")
    api = WorkerAPI(instance)
    routes = api.routes()
    settings = api.state("settings")
    verify_bindings(settings, instance)
    verify_domains(api)
    verify_access(instance)
    raw, content_type = api.state("content/v2")
    modules = parse_modules(raw, content_type)
    html = module_named(modules, "report.html")
    b50 = module_named(
        modules, "b50.webp", optional=source is not None or instance.b50_mode != "required"
    )
    latest = (
        verify_retained_copies(instance, html, b50)
        if instance.history_enabled and source is None
        else None
    )
    check(
        not destination.exists() or not any(destination.iterdir()), "Use an empty release directory"
    )
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "worker-multipart.bin").write_bytes(raw)
    (destination / "content-type.txt").write_text(content_type)
    (destination / "previous-settings.json").write_bytes(canonical(settings))
    (destination / "previous-deployments.json").write_bytes(canonical(api.state("deployments")))
    (destination / "report.html").write_bytes(html)
    if b50 is not None:
        (destination / "b50.webp").write_bytes(b50)
    saved = {
        "identity": instance.identity(),
        "latestCaptureID": latest,
        "routes": routes,
        "modules": {name: sha256(value) for name, value in modules.items()},
        "settings": settings,
        "scoreImportStarted": False,
        "workerDeployed": False,
    }
    (destination / "prepared.json").write_bytes(canonical(saved))
    if source is not None:
        html = (source / "maimai-report.html").read_bytes()
        b50_file = source / "maimai-b50.webp"
        b50 = b50_file.read_bytes() if b50_file.is_file() else None
    return stage(instance, destination / "staged", core, html, b50, settings=settings)


def recheck(instance: Instance, destination: Path) -> None:
    saved = json.loads((destination / "prepared.json").read_bytes())
    check(
        saved["identity"] == instance.identity(), "Installation identity changed after preparation"
    )
    if saved.get("bootstrap"):
        verify_empty_installation(instance)
    else:
        api = WorkerAPI(instance)
        check(api.routes() == saved["routes"], "Worker routes changed during release preparation")
        check(
            api.state("settings") == saved["settings"],
            "Worker settings changed during release preparation",
        )
        modules = parse_modules(*api.state("content/v2"))
        check(
            {k: sha256(v) for k, v in modules.items()} == saved["modules"],
            "Live Worker changed during release preparation",
        )
        verify_domains(api)
        verify_access(instance)
    verify_staged(instance, destination / "staged")


def verify_staged(instance: Instance, source: Path) -> dict:
    manifest = json.loads((source / "staged.json").read_bytes())
    check(manifest["identity"] == instance.identity(), "Staged identity differs from installation")
    check(
        all(Path(name).name == name for name in manifest["files"]),
        "Staged manifest contains an invalid path",
    )
    check(
        {
            p.name
            for p in source.iterdir()
            if not (p.name == ".wrangler" and p.is_dir() and not p.is_symlink())
        }
        == set(manifest["files"]) | {"staged.json"},
        "Staged release contains unexpected files",
    )
    check(
        all(
            sha256((source / name).read_bytes()) == digest
            for name, digest in manifest["files"].items()
        ),
        "Staged release bytes changed after validation",
    )
    config = json.loads((source / "wrangler.generated.json").read_bytes())
    check(
        config["name"] == instance.worker_name
        and config["account_id"] == instance.account_id
        and config["routes"] == [instance.route]
        and config["workers_dev"] is False
        and config["preview_urls"] is False,
        "Staged deployment destination or privacy settings differ",
    )
    return manifest


def verify_release(instance: Instance, destination: Path) -> None:
    staged = destination / "staged"
    manifest = json.loads((staged / "staged.json").read_bytes())
    check(manifest["identity"] == instance.identity(), "Release belongs to another installation")
    api = WorkerAPI(instance)
    modules = parse_modules(*api.state("content/v2"))
    (destination / "observed-after-deploy.json").write_bytes(
        canonical(
            {
                "identity": instance.identity(),
                "modules": {k: sha256(v) for k, v in modules.items()},
                "deployments": api.state("deployments"),
                "verified": False,
            }
        )
    )
    api.routes()
    verify_bindings(api.state("settings"), instance)
    verify_domains(api)
    verify_access(instance)
    for name, key in (("report.html", "reportSha256"), ("b50.webp", "b50Sha256")):
        content = module_named(modules, name, optional=manifest[key] is None)
        check(
            (sha256(content) if content is not None else None) == manifest[key],
            "Deployed report/B50 differs from validated retained bytes",
        )
    (destination / "deployed.json").write_bytes(
        canonical(
            {
                "identity": instance.identity(),
                "modules": {k: sha256(v) for k, v in modules.items()},
                "deployments": api.state("deployments"),
                "scoreImportStarted": False,
                "privateHistoryBindingsVerified": True,
                "publicWorkerDomainsDisabled": True,
            }
        )
    )


def verify_empty_installation(instance: Instance) -> None:
    """A fresh bootstrap cannot overwrite an existing Worker or any archived capture."""
    instance.validate("bootstrap")
    api = WorkerAPI(instance)
    check(not api.routes(bootstrap=True), "Bootstrap requires an unused Worker route")
    try:
        api.state("settings")
    except ProviderError as exc:
        if exc.status != 404:
            raise
    else:
        raise ArchiveError("Worker already exists; use retained release, not bootstrap")
    verify_access(instance)
    if instance.history_enabled:
        storage = Cloudflare(
            instance.account_id, required(os.environ, "CLOUDFLARE_HISTORY_API_TOKEN")
        )
        for database_id, bucket in (
            (instance.database_id, instance.bucket),
            (instance.recovery_database_id, instance.backup_bucket),
        ):
            verify_private_bucket(storage, bucket)
            rows = D1(storage, database_id).query("SELECT COUNT(*) count FROM captures")
            check(
                len(rows) == 1 and rows[0].get("count") == 0,
                "Bootstrap requires empty history indexes",
            )
            check(
                next(iter(R2(instance.account_id, bucket).keys("")), None) is None,
                "Bootstrap requires empty private archives",
            )


def bootstrap(instance: Instance, destination: Path, core: Path) -> dict:
    from importlib import resources

    from ..cli import _support

    verify_empty_installation(instance)
    check(
        not destination.exists() or not any(destination.iterdir()), "Use an empty release directory"
    )
    destination.mkdir(parents=True, exist_ok=True)
    support = _support(instance.app)
    data = {"support": support} if support else {}
    assets = resources.files(ASSET_PACKAGE)
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="referrer" content="no-referrer"><title>maimai report · ready to play</title>'
        "<style>body{margin:0;background:#effcfd;color:#123b49;font:16px system-ui}"
        ".setup{max-width:700px;margin:12vh auto;padding:32px}h1{font-size:clamp(28px,5vw,44px)}"
        "p{line-height:1.65}.label{color:#007a8c;font-weight:800;letter-spacing:.08em}"
        + assets.joinpath("support.css").read_text()
        + "</style></head><body>"
        '<main id="app" class="setup"><p class="label">MAIMAI · SESSION REPORT</p>'
        "<h1>Ready for your first session.</h1><p>Your private installation is ready. "
        "Run Refresh in your installation repository when you want to capture a session.</p>"
        "<p>No scores have been imported and no session has been recorded by this setup.</p></main>"
        '<script id="report-data" type="application/json">'
        + json_for_html(data)
        + "</script><script>"
        + assets.joinpath("support.js").read_text()
        + "</script></body></html>"
    ).encode()
    (destination / "prepared.json").write_bytes(
        canonical(
            {
                "identity": instance.identity(),
                "bootstrap": True,
                "scoreImportStarted": False,
            }
        )
    )
    return stage(instance, destination / "staged", core, html, None, bootstrap=True)


def rollback_plan(instance: Instance, source: Path, output: Path) -> dict:
    instance.validate("rollback")
    saved = json.loads((source / "prepared.json").read_bytes())
    check(not saved.get("bootstrap"), "A first bootstrap has no previous Worker version")
    check(saved["identity"] == instance.identity(), "Rollback belongs to another installation")
    verify_staged(instance, source / "staged")
    observed = json.loads((source / "observed-after-deploy.json").read_bytes())
    check(observed["identity"] == instance.identity(), "Rollback evidence has conflicting identity")
    api = WorkerAPI(instance)
    api.routes()
    verify_bindings(api.state("settings"), instance)
    verify_domains(api)
    verify_access(instance)
    actual = parse_modules(*api.state("content/v2"))
    check(
        {k: sha256(v) for k, v in actual.items()} == observed["modules"],
        "Worker changed after this release; review the newer deployment before rollback",
    )
    prior = json.loads((source / "previous-deployments.json").read_bytes())
    deployments = prior.get("deployments", [])
    versions = deployments[0].get("versions", []) if deployments else []
    check(
        len(versions) == 1 and versions[0].get("percentage") == 100,
        "Rollback requires one previously active version at 100 percent",
    )
    version = versions[0].get("version_id", "")
    check(str(UUID(version)) == version, "Invalid saved Worker version")
    result = {
        "version": version,
        "identity": instance.identity(),
        "previousModules": saved["modules"],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "rollback-plan.json").write_bytes(canonical(result))
    return result


def verify_rollback(instance: Instance, destination: Path) -> None:
    saved = json.loads((destination / "rollback-plan.json").read_bytes())
    check(saved["identity"] == instance.identity(), "Rollback installation identity changed")
    api = WorkerAPI(instance)
    api.routes()
    verify_bindings(api.state("settings"), instance)
    verify_domains(api)
    verify_access(instance)
    modules = parse_modules(*api.state("content/v2"))
    check(
        {k: sha256(v) for k, v in modules.items()} == saved["previousModules"],
        "Rollback did not restore the saved Worker modules",
    )

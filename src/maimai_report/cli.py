from __future__ import annotations

import argparse
import os
import platform
import sys
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import __version__
from .api import KamaitachiClient, validate_score_payload
from .artwork import prepare_jackets
from .badges import export_badge_pack
from .capture import capture_existing, list_sessions, save_baseline, write_capture
from .config import AppConfig, get_api_token, load_config
from .errors import MaimaiReportError
from .io import ensure_output_directory, write_json
from .render import enrich_report, read_json, render_demo, render_report
from .server import serve_file
from .sync import synchronize, write_sync_result

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_OPERATION = 3


def _add_config_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="TOML configuration path (default: MAIMAI_REPORT_CONFIG or ./config.toml)",
    )
    parser.add_argument("--username", help="Kamaitachi username override")
    parser.add_argument("--display-name", help="Player display name override")
    parser.add_argument("--timezone", help="IANA timezone override")
    parser.add_argument("--game", help="Kamaitachi game identifier override")
    parser.add_argument("--import-type", help="Kamaitachi import type override")
    parser.add_argument(
        "--current-version",
        action="append",
        dest="current_versions",
        metavar="DISPLAY_NAME",
        help="Exact current-version display name; repeat for aliases",
    )
    parser.add_argument("--output-dir", type=Path, help="Private JSON output directory override")
    parser.add_argument(
        "--badge-pack", help="Rating frames: builtin, plain, or a local TOML artwork manifest"
    )
    _add_support_option(parser)


def _add_support_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--support",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="support_enabled",
        help="Show or hide developer support (checkout loads only after a click)",
    )


def _add_artwork_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--jackets", type=Path, help="Prepared local raster jacket JSON; no network")
    group.add_argument(
        "--prepare-jackets",
        action="store_true",
        help="Prepare embedded jackets from public static artwork at build time",
    )
    parser.add_argument("--jacket-cache", type=Path, help="Reusable local public-artwork cache")
    parser.add_argument("--artwork-catalogue", type=Path, help="Saved official song catalogue JSON")
    parser.add_argument(
        "--offline-artwork", action="store_true", help="Only use cached public artwork"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maimai-report",
        description="maimai Session Report: private session reports and rating progress",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor", help="Validate local setup without starting an import")
    _add_config_options(doctor)
    doctor.add_argument(
        "--network",
        action="store_true",
        help="Also make one authenticated read-only API request; never starts an import",
    )

    demo = commands.add_parser("demo", help="Generate a fully offline synthetic report")
    demo.add_argument("--output", type=Path, required=True)
    demo.add_argument(
        "--badge-pack", help="Rating frames: builtin, plain, or a local TOML artwork manifest"
    )
    _add_support_option(demo)
    demo.add_argument(
        "--scenario",
        choices=("complete", "empty", "incomplete"),
        default="complete",
        help="Bundled synthetic scenario",
    )

    export_badges = commands.add_parser(
        "export-badges", help="Export the bundled rating artwork as an editable local pack"
    )
    export_badges.add_argument("--output-dir", type=Path, required=True)

    render = commands.add_parser("render", help="Render existing local JSON inputs")
    _add_config_options(render)
    render.add_argument("--report-input", type=Path, required=True)
    render.add_argument("--after-pbs", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    _add_artwork_options(render)

    artwork = commands.add_parser(
        "prepare-jackets", help="Prepare jacket JSON from retained inputs; no score API"
    )
    _add_config_options(artwork)
    artwork.add_argument("--report-input", type=Path, required=True)
    artwork.add_argument("--after-pbs", type=Path, required=True)
    artwork.add_argument("--output", type=Path, required=True)
    _add_artwork_options(artwork)

    sync = commands.add_parser("sync", help="Run one import and save private JSON only")
    _add_config_options(sync)

    combined = commands.add_parser(
        "sync-and-render", help="Run one import and render a local HTML report"
    )
    _add_config_options(combined)
    combined.add_argument("--output", type=Path, required=True)
    _add_artwork_options(combined)

    sessions = commands.add_parser("sessions", help="List existing Kamaitachi sessions; read only")
    _add_config_options(sessions)
    baseline = commands.add_parser("snapshot", help="Save a PB baseline before playing; read only")
    _add_config_options(baseline)
    baseline.add_argument("--output", type=Path, required=True)
    existing = commands.add_parser(
        "from-kamaitachi", help="Generate from an existing Kamaitachi session; never imports"
    )
    _add_config_options(existing)
    selection = existing.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--session-id", help="Exact ID from the sessions command or Kamaitachi session URL"
    )
    selection.add_argument(
        "--latest", action="store_true", help="Explicitly select the most recent session"
    )
    selection.add_argument(
        "--pb-snapshot",
        action="store_true",
        help="Report current PBs without claiming a play session",
    )
    existing.add_argument("--baseline", type=Path, help="Previously saved baseline.json; optional")
    existing.add_argument("--output", type=Path, required=True)
    _add_artwork_options(existing)

    instance = commands.add_parser(
        "instance", help="Configure and maintain a private hosted installation"
    )
    instance.add_argument("arguments", nargs=argparse.REMAINDER)

    serve = commands.add_parser("serve", help="Serve one generated report locally")
    serve.add_argument("--file", type=Path, required=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    return parser


def _config_path(args: argparse.Namespace, environ: Mapping[str, str]) -> Path:
    if args.config is not None:
        return args.config
    configured = environ.get("MAIMAI_REPORT_CONFIG")
    return Path(configured) if configured else Path("config.toml")


def _load_cli_config(args: argparse.Namespace, environ: Mapping[str, str]) -> AppConfig:
    pairs = {
        "username": getattr(args, "username", None),
        "display_name": getattr(args, "display_name", None),
        "timezone": getattr(args, "timezone", None),
        "game": getattr(args, "game", None),
        "import_type": getattr(args, "import_type", None),
        "current_version_display_names": getattr(args, "current_versions", None),
        "output_dir": getattr(args, "output_dir", None),
        "badge_pack": getattr(args, "badge_pack", None),
        "support_enabled": getattr(args, "support_enabled", None),
    }
    overrides = {key: value for key, value in pairs.items() if value is not None}
    return load_config(_config_path(args, environ), cli_overrides=overrides, environ=environ)


def _player(config: AppConfig) -> dict[str, str]:
    display_name = config.display_name or config.username or "Player"
    game_name = "maimai DX" if config.game == "maimaidx" else config.game
    return {
        "username": config.username or "offline-player",
        "displayName": display_name,
        "game": game_name,
        "timezone": config.timezone,
    }


def _doctor(args: argparse.Namespace, environ: Mapping[str, str]) -> int:
    checks: list[tuple[str, str]] = []
    # Doctor explicitly reports this even when invoked from an unsupported source checkout.
    if sys.version_info < (3, 11):  # noqa: UP036
        raise MaimaiReportError("Python 3.11 or newer is required")
    checks.append(("Python", f"{platform.python_version()} (supported)"))

    config = _load_cli_config(args, environ)
    config.validate(for_network=args.network)
    config_file = _config_path(args, environ)
    checks.append(
        (
            "Configuration",
            str(config_file.resolve())
            if config_file.is_file()
            else "safe defaults (no config.toml)",
        )
    )

    if config.timezone != "UTC":
        try:
            ZoneInfo(config.timezone)
        except ZoneInfoNotFoundError as exc:
            raise MaimaiReportError(
                f"Unknown or unavailable IANA timezone {config.timezone!r}; correct the "
                "name, or on Windows install this project with the 'timezone' extra"
            ) from exc
    checks.append(("Timezone", config.timezone))
    checks.append(("Rating badges", "validated; " + config.badge_pack))

    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".write-check-", dir=output_dir, delete=True):
        pass
    checks.append(("Output", f"writable: {output_dir}"))

    if config.current_version_display_names:
        checks.append(("New 15 versions", ", ".join(config.current_version_display_names)))
    else:
        checks.append(
            (
                "New 15 versions",
                "not configured (fine for demo; required before live sync)",
            )
        )

    if config.support_enabled:
        checks.append(("Developer support", "enabled; in-page checkout loads only after a click"))
    else:
        checks.append(("Developer support", "disabled; report remains fully sealed"))

    if args.network:
        token = get_api_token(environ, required=True)
        client = KamaitachiClient(token)
        payload = client.get_pbs(config.username, config.game, authenticated=True)
        validate_score_payload(payload, "pbs")
        checks.append(("API", "authenticated read succeeded; no import was started"))
    else:
        checks.append(("Network", "not requested; no network request made"))

    for name, detail in checks:
        print(f"[ok] {name}: {detail}")
    print("Doctor completed without initiating a sync.")
    return EXIT_OK


def _render_command(args: argparse.Namespace, environ: Mapping[str, str]) -> int:
    config = _load_cli_config(args, environ)
    report = enrich_report(
        read_json(args.report_input),
        read_json(args.after_pbs),
        player=_player(config),
        current_version_display_names=(config.current_version_display_names or None),
        support=config.support_enabled,
    )
    output = render_report(
        report, args.output, jackets=_artwork(args, config, report), badge_pack=config.badge_pack
    )
    print(f"Rendered private report: {output.resolve()}")
    return EXIT_OK


def _artwork(args: argparse.Namespace, config: AppConfig, report: dict) -> dict | None:
    if args.jackets:
        return read_json(args.jackets)
    if not args.prepare_jackets and args.command != "prepare-jackets":
        return None
    cache = args.jacket_cache or config.output_dir / "artwork-cache"
    result = prepare_jackets(
        report, cache, catalogue_path=args.artwork_catalogue, offline=args.offline_artwork
    )
    write_json(cache / "provenance.json", result.provenance)
    print(
        f"Prepared {len(result.jackets)} of {result.requested} jackets from public static artwork"
    )
    for warning in result.warnings:
        print(f"Artwork: {warning}", file=sys.stderr)
    return result.jackets


def _artwork_command(args: argparse.Namespace, environ: Mapping[str, str]) -> int:
    config = _load_cli_config(args, environ)
    report = enrich_report(
        read_json(args.report_input),
        read_json(args.after_pbs),
        current_version_display_names=config.current_version_display_names or None,
    )
    write_json(args.output, _artwork(args, config, report) or {})
    print(f"Saved private jacket mapping: {args.output.resolve()}")
    return EXIT_OK


def _sync_command(args: argparse.Namespace, environ: Mapping[str, str], *, render: bool) -> int:
    config = _load_cli_config(args, environ)
    # Validate every live setting and destination before the first API request.
    config.validate(for_network=True)
    ensure_output_directory(config.output_dir)
    if render:
        output_path = args.output.expanduser()
        if output_path.exists() and output_path.is_dir():
            raise MaimaiReportError(f"HTML output path is a directory: {output_path}")
        ensure_output_directory(output_path.parent)
    result = synchronize(config, environ=environ)
    paths = write_sync_result(result, config.output_dir)
    print(f"Saved private sync JSON in: {config.output_dir.resolve()}")
    for path in paths.values():
        print(f"  {path.name}")
    if render:
        report = enrich_report(
            result.report_input,
            result.after_pbs,
            player=_player(config),
            current_version_display_names=config.current_version_display_names,
            support=config.support_enabled,
        )
        output = render_report(
            report,
            args.output,
            jackets=_artwork(args, config, report),
            badge_pack=config.badge_pack,
        )
        print(f"Rendered private report: {output.resolve()}")
    return EXIT_OK


def run(args: argparse.Namespace, *, environ: Mapping[str, str] | None = None) -> int:
    env = os.environ if environ is None else environ
    if args.command in {"sessions", "snapshot", "from-kamaitachi"}:
        config = _load_cli_config(args, env)
        if args.command == "sessions":
            sessions = list_sessions(config)
            print("Recent Kamaitachi sessions (up to 100). Use a session ID with from-kamaitachi:")
            for item in sessions:
                # Session names are user-supplied; do not emit terminal control characters.
                name = " ".join(str(item.get("name", "Session")).split())
                name = "".join(c for c in name if c.isprintable())
                when = datetime.fromtimestamp(item["timeEnded"] / 1000, UTC).isoformat()
                print(f"{item['sessionID']}  {when}  {name}")
            if not sessions:
                print("No sessions found. Import recent plays first, or use --pb-snapshot.")
            return EXIT_OK
        if args.command == "snapshot":
            output = save_baseline(config, args.output)
            print(f"Saved private PB baseline: {output.resolve()}")
            return EXIT_OK
        if config.output_dir.exists() and any(config.output_dir.iterdir()):
            raise MaimaiReportError("Choose an empty --output-dir for this capture.")
        if args.output.exists():
            raise MaimaiReportError("Choose a new HTML output filename.")
        # Refuse destinations that would replace the baseline or retained evidence.
        reserved = {
            config.output_dir / name
            for name in (
                "baseline.json",
                "metadata.json",
                "report-input.json",
                "before-pbs.json",
                "after-pbs.json",
                "before-recent-scores.json",
                "after-recent-scores.json",
                "kamaitachi-session.json",
            )
        }
        if args.output.resolve() in {p.resolve() for p in reserved}:
            raise MaimaiReportError("HTML output must not replace capture JSON.")
        capture = capture_existing(
            config,
            session_id=args.session_id,
            latest=args.latest,
            pb_snapshot=args.pb_snapshot,
            baseline_path=args.baseline,
        )
        write_capture(capture, config.output_dir)
        result = capture[0]
        report = enrich_report(
            result.report_input,
            result.after_pbs,
            player=_player(config),
            current_version_display_names=config.current_version_display_names,
            support=config.support_enabled,
        )
        output = render_report(
            report,
            args.output,
            jackets=_artwork(args, config, report),
            badge_pack=config.badge_pack,
        )
        print(f"Rendered private Kamaitachi report: {output.resolve()}")
        baseline_output = (config.output_dir / "baseline.json").resolve()
        print(f"Saved a baseline for future comparisons: {baseline_output}")
        return EXIT_OK
    if args.command == "doctor":
        return _doctor(args, env)
    if args.command == "demo":
        config = load_config(
            None,
            environ={
                key: value
                for key, value in env.items()
                if key in {"MAIMAI_REPORT_BADGE_PACK", "MAIMAI_REPORT_SUPPORT_ENABLED"}
            },
            cli_overrides={
                "badge_pack": args.badge_pack,
                "support_enabled": args.support_enabled,
                "output_dir": args.output.parent,
            },
        )
        output = render_demo(
            args.output,
            scenario=args.scenario,
            badge_pack=config.badge_pack,
            support=config.support_enabled,
        )
        print(f"Rendered offline synthetic report: {output.resolve()}")
        return EXIT_OK
    if args.command == "render":
        return _render_command(args, env)
    if args.command == "export-badges":
        manifest = export_badge_pack(args.output_dir)
        print(f"Exported local rating artwork pack: {manifest.resolve()}")
        return EXIT_OK
    if args.command == "prepare-jackets":
        return _artwork_command(args, env)
    if args.command == "sync":
        return _sync_command(args, env, render=False)
    if args.command == "sync-and-render":
        return _sync_command(args, env, render=True)
    if args.command == "serve":
        serve_file(args.file, host=args.host, port=args.port)
        return EXIT_OK
    raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments and arguments[0] == "instance":
        from .installation.__main__ import main as instance_main

        return instance_main(arguments[1:])
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (MaimaiReportError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_OPERATION

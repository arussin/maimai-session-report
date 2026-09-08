"""Small, dependency-free PEP 517 backend for this pure-Python project.

The backend exists so a clean clone can be installed in an offline Python 3.11+
virtual environment without downloading a build backend first.
"""

from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import io
import os
import tarfile
import zipfile
from pathlib import Path

NAME = "maimai_session_report"
DISPLAY_NAME = "maimai-session-report"
VERSION = "0.1.0"
DIST_INFO = f"{NAME}-{VERSION}.dist-info"
WHEEL_NAME = f"{NAME}-{VERSION}-py3-none-any.whl"


def get_requires_for_build_wheel(config_settings: dict | None = None) -> list[str]:
    return []


def get_requires_for_build_sdist(config_settings: dict | None = None) -> list[str]:
    return []


def get_requires_for_build_editable(config_settings: dict | None = None) -> list[str]:
    return []


def _metadata() -> str:
    readme = Path("README.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    headers = (
        "Metadata-Version: 2.4\n"
        f"Name: {DISPLAY_NAME}\n"
        f"Version: {VERSION}\n"
        "Summary: maimai Session Report: private session reports and rating progress\n"
        "Description-Content-Type: text/markdown\n"
        "Author: arussin\n"
        "Keywords: maimai,kamaitachi,myt,report\n"
        "License-Expression: MIT AND LicenseRef-SEGA-Game-Artwork\n"
        "License-File: LICENSE\n"
        "License-File: THIRD_PARTY_NOTICES.md\n"
        "License-File: docs/RATING_ASSETS.md\n"
        "Requires-Python: >=3.11\n"
        "Classifier: Development Status :: 4 - Beta\n"
        "Classifier: Environment :: Console\n"
        "Classifier: Programming Language :: Python :: 3\n"
        "Classifier: Programming Language :: Python :: 3.11\n"
        "Classifier: Programming Language :: Python :: 3.12\n"
        "Classifier: Programming Language :: Python :: 3.13\n"
        "Classifier: Topic :: Games/Entertainment\n"
        "Project-URL: Repository, https://github.com/arussin/maimai-session-report\n"
        "Project-URL: Issues, https://github.com/arussin/maimai-session-report/issues\n"
        "Provides-Extra: timezone\n"
        'Requires-Dist: tzdata>=2025.2; extra == "timezone"\n'
        "Provides-Extra: artwork\n"
        'Requires-Dist: Pillow==12.3.0; extra == "artwork"\n'
        "Provides-Extra: history\n"
        'Requires-Dist: boto3==1.43.89; extra == "history"\n'
    )
    return f"{headers}\n{readme}"


def _wheel_text() -> str:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: maimai-build-backend\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    )


def prepare_metadata_for_build_wheel(
    metadata_directory: str, config_settings: dict | None = None
) -> str:
    target = Path(metadata_directory, DIST_INFO)
    target.mkdir(parents=True, exist_ok=True)
    target.joinpath("METADATA").write_text(_metadata(), encoding="utf-8")
    target.joinpath("WHEEL").write_text(_wheel_text(), encoding="utf-8")
    target.joinpath("entry_points.txt").write_text(
        "[console_scripts]\nmaimai-report = maimai_report.cli:main\n", encoding="utf-8"
    )
    return DIST_INFO


def prepare_metadata_for_build_editable(
    metadata_directory: str, config_settings: dict | None = None
) -> str:
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def _digest(data: bytes) -> str:
    value = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return "sha256=" + value.decode("ascii")


def _wheel_entries(editable: bool) -> dict[str, bytes]:
    root = Path.cwd()
    entries: dict[str, bytes] = {}
    if editable:
        source = root.joinpath("src").resolve()
        entries[f"{NAME}.pth"] = (os.fspath(source) + "\n").encode()
    else:
        for path in sorted(root.joinpath("src", "maimai_report").rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                entries[path.relative_to(root / "src").as_posix()] = path.read_bytes()
    entries[f"{DIST_INFO}/METADATA"] = _metadata().encode()
    entries[f"{DIST_INFO}/WHEEL"] = _wheel_text().encode()
    entries[f"{DIST_INFO}/entry_points.txt"] = (
        b"[console_scripts]\nmaimai-report = maimai_report.cli:main\n"
    )
    entries[f"{DIST_INFO}/licenses/LICENSE"] = root.joinpath("LICENSE").read_bytes()
    entries[f"{DIST_INFO}/licenses/THIRD_PARTY_NOTICES.md"] = root.joinpath(
        "THIRD_PARTY_NOTICES.md"
    ).read_bytes()
    entries[f"{DIST_INFO}/licenses/docs/RATING_ASSETS.md"] = root.joinpath(
        "docs/RATING_ASSETS.md"
    ).read_bytes()
    return entries


def _write_wheel(wheel_directory: str, editable: bool) -> str:
    target = Path(wheel_directory, WHEEL_NAME)
    target.parent.mkdir(parents=True, exist_ok=True)
    entries = _wheel_entries(editable)
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, data in entries.items():
        writer.writerow((name, _digest(data), len(data)))
    writer.writerow((f"{DIST_INFO}/RECORD", "", ""))
    entries[f"{DIST_INFO}/RECORD"] = record.getvalue().encode()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return target.name


def build_wheel(
    wheel_directory: str,
    config_settings: dict | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _write_wheel(wheel_directory, editable=False)


def build_editable(
    wheel_directory: str,
    config_settings: dict | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _write_wheel(wheel_directory, editable=True)


def build_sdist(sdist_directory: str, config_settings: dict | None = None) -> str:
    root = Path.cwd()
    filename = f"{DISPLAY_NAME}-{VERSION}.tar.gz"
    target = Path(sdist_directory, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    included_files = [
        ".gitignore",
        ".python-version",
        "CONTRIBUTING.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "README.md",
        "SECURITY.md",
        "pyproject.toml",
        "config.example.toml",
        "requirements-dev.txt",
        "docs/sample-report.html",
        "docs/images/demo-desktop.png",
        "docs/images/demo-mobile.png",
        "docs/images/demo-scores.png",
        "docs/images/demo-pools.png",
        "docs/images/demo-targets.png",
        "deploy/cloudflare/package-lock.json",
        "deploy/cloudflare/package.json",
        "deploy/cloudflare/history.example.json",
        "deploy/cloudflare/scripts/generate-config.mjs",
        "deploy/cloudflare/src/worker.js",
        "deploy/cloudflare/src/security.js",
        "deploy/cloudflare/src/hosted.js",
        "deploy/cloudflare/src/history.js",
        "deploy/cloudflare/test/adapter.test.mjs",
        "deploy/cloudflare/test/history.test.mjs",
        "deploy/cloudflare/test/history-fixture.mjs",
        "archive/action.yml",
        "history/action.yml",
        "action.yml",
        "render/action.yml",
        "templates/private-caller/instance.toml",
        "templates/private-caller/README.md",
        "templates/private-caller/.gitignore",
        *(
            f"templates/private-caller/.github/workflows/{name}.yml"
            for name in ("validate", "refresh", "history", "release")
        ),
    ]
    included_directories = {
        ".github/workflows": {".yaml", ".yml"},
        "build_backend": {".py"},
        "docs": {".md"},
        "src": {".css", ".html", ".js", ".py", ".sql", ".txt"},
        "tests": {".py"},
        "installation": {".py", ".yml"},
        "scripts": {".py"},
    }
    excluded_parts = {"__pycache__", ".wrangler", "node_modules"}
    sources = [root / relative for relative in included_files]
    for relative, allowed_suffixes in included_directories.items():
        sources.extend(
            path
            for path in (root / relative).rglob("*")
            if path.is_file()
            and not excluded_parts.intersection(path.parts)
            and path.suffix in allowed_suffixes
        )

    with target.open("wb") as raw_handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as compressed:
            with tarfile.open(
                fileobj=compressed,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as archive:
                for path in sorted(set(sources), key=lambda item: item.as_posix()):
                    data = path.read_bytes()
                    relative = path.relative_to(root).as_posix()
                    info = tarfile.TarInfo(f"{DISPLAY_NAME}-{VERSION}/{relative}")
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    archive.addfile(info, io.BytesIO(data))
    return filename

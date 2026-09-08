"""Build the reviewed instance-file ZIP. It never creates a repository or deploys."""

from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "instance.toml",
    "README.md",
    ".gitignore",
    *(f".github/workflows/{name}.yml" for name in ("validate", "refresh", "history", "release")),
)


def package(output: Path, commit: str, *, root: Path = ROOT) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Select a complete reviewed core commit SHA")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            source = root / "templates/private-caller" / name
            data = source.read_text().replace("__CORE_SHA__", commit).encode()
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    output.with_suffix(output.suffix + ".sha256").write_text(
        hashlib.sha256(output.read_bytes()).hexdigest() + "  " + output.name + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package(args.output, args.commit)

"""Apply the reviewed TLS-only change to the exact optional upstream checkout.

This is local build preparation, not a network operation. It never changes the
upstream repository or accepts a different source revision silently.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

CATALOGUE_PATH = "apps/render/src/lib/catalog.ts"
UPSTREAM_FILES = {
    CATALOGUE_PATH: "1371a2cdc9f09a50b080908181754c992cac466d242bbde16d4fdf17740c2cb2",
    "apps/render/src/lib/render-image-server.ts": (
        "a35bac5b89f6f9b53c34717a68f1ae9335b5f706535948090b7ef7833c73fe14"
    ),
    "apps/render/src/lib/image_cacher.ts": (
        "52c9f6db623fc8a9e9158044f96ac91b67689f0b7df619b2bee8c953658c379c"
    ),
}
OLD = "rejectUnauthorized: false"
NEW = "rejectUnauthorized: true"
NOTICE = (
    "// Modified by maimai Session Report, 2026-09-08: restore TLS certificate verification.\n"
    "// Original source remains AGPL-3.0-only; see the upstream LICENSE and project notices.\n"
)


def harden(checkout: Path) -> bool:
    root = checkout.resolve(strict=True)
    changes = []
    # Validate the entire reviewed set before changing any upstream file.
    for relative, digest in UPSTREAM_FILES.items():
        target = (root / relative).resolve(strict=True)
        if not target.is_relative_to(root):
            raise ValueError("Tomomai source escapes its checkout")
        source = target.read_text(encoding="utf-8")
        patched = patched_source(source, digest)
        if patched != source:
            changes.append((target, patched))
    for target, patched in changes:
        target.write_text(patched, encoding="utf-8", newline="\n")
    return bool(changes)


def patched_source(source: str, digest: str) -> str:
    original = source
    if source.startswith(NOTICE):
        original = source.removeprefix(NOTICE).replace(NEW, OLD)
    if hashlib.sha256(original.encode()).hexdigest() != digest:
        raise ValueError("Tomomai source differs from the reviewed pin; refusing to patch")
    if original.count(OLD) != 1:
        raise ValueError("Expected exactly one upstream TLS setting; refusing to patch")
    patched = NOTICE + original.replace(OLD, NEW)
    if source == patched:
        return patched
    if source != original:
        raise ValueError("Tomomai source already contains an unrecognized modification")
    return patched


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    harden(args.checkout)
    print("Optional Tomomai renderer: reviewed sources and TLS verification confirmed.")

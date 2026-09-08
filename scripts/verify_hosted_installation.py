"""Standalone entry point; hosted owners can run History → verify-fresh in Actions."""

import argparse
from pathlib import Path

from maimai_report.errors import MaimaiReportError
from maimai_report.history.bundle import ArchiveError, canonical
from maimai_report.installation.config import load_instance
from maimai_report.installation.verification import verify_fresh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--renderer-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = verify_fresh(
        load_instance(args.config),
        args.output.parent / "verification-evidence",
        args.renderer_commit,
        apply=args.apply,
    )
    args.output.write_bytes(canonical(result) + b"\n")
    print("Hosted synthetic verification and scoped cleanup passed")


if __name__ == "__main__":
    try:
        main()
    except (MaimaiReportError, ArchiveError, OSError, ValueError) as exc:
        raise SystemExit(f"Hosted verification stopped ({type(exc).__name__})") from None

"""Verify or update a reviewed Party contract; never claim dirty files are committed."""

import argparse
from pathlib import Path

from maimai_report.contract_vendor import export_bundle, load_bundle, vendor_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source", type=Path, help="Local registry Git checkout")
    source.add_argument("--bundle", type=Path, help="Previously exported immutable bundle")
    parser.add_argument("--revision", required=True, help="Reviewed full upstream commit SHA")
    parser.add_argument("--bundle-sha256", help="Reviewed SHA256, required with --bundle")
    parser.add_argument("--check", action="store_true", help="Verify only; do not write files")
    args = parser.parse_args()
    if args.bundle and not args.bundle_sha256:
        parser.error("--bundle requires the reviewed --bundle-sha256")
    bundle = (
        load_bundle(args.bundle, args.revision, args.bundle_sha256)
        if args.bundle
        else export_bundle(args.source, args.revision)
    )
    destination = Path(__file__).resolve().parents[1] / "src/maimai_report"
    vendor_bundle(bundle, args.revision, destination, check=args.check)
    print("Verified pinned public contract" if args.check else "Updated pinned public contract")


if __name__ == "__main__":
    main()

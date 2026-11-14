"""Single command surface for local, CI and cloud execution."""

import argparse
import json
import sys
from pathlib import Path

from retail_analytics.download import download_olist
from retail_analytics.extract import DataQualityError
from retail_analytics.pipeline import resolve_run, run_pipeline


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Retail Analytics — Olist pipeline")
    commands = root.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("download", help="Download original Olist CSVs from Kaggle")
    fetch.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    run = commands.add_parser("run", help="Validate, transform, reconcile and publish a local run")
    run.add_argument("--raw-dir", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    run.add_argument("--source-kind", choices=["olist", "synthetic"], required=True)
    bq = commands.add_parser("bigquery", help="Load an already validated run using ADC/WIF")
    bq.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    bq.add_argument("--project", required=True)
    bq.add_argument("--dataset", default="retail_analytics")
    bq.add_argument("--location", default="US")
    bq.add_argument("--maximum-bytes-billed", type=int, default=1024**3)
    bq.add_argument("--allow-synthetic", action="store_true")
    bq.add_argument(
        "--no-partitioning",
        action="store_true",
        help="Load historical Sandbox facts without purchase-date partitions",
    )
    return root


def main(argv: list[str] | None = None) -> int:
    root = parser()
    args = root.parse_args(argv)
    try:
        if args.command == "download":
            print(json.dumps(download_olist(args.raw_dir), indent=2))
        elif args.command == "run":
            result = run_pipeline(args.raw_dir, args.output_dir, args.source_kind)
            print(f"Validated run: {result}")
            print((result / "summary.json").read_text(encoding="utf-8"))
        else:
            from retail_analytics.bigquery import publish

            result = publish(
                resolve_run(args.processed_dir),
                args.project,
                args.dataset,
                args.location,
                args.maximum_bytes_billed,
                args.allow_synthetic,
                partition_facts=not args.no_partitioning,
            )
            print(json.dumps(result, indent=2))
    except (DataQualityError, ValueError, FileNotFoundError, FileExistsError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

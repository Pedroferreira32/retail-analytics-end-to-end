"""Copy CSVs from an already validated run into Power BI's ignored local data directory."""

import argparse
import json
import shutil
from pathlib import Path

from retail_analytics.pipeline import resolve_run
from retail_analytics.warehouse import MODEL_TABLES


def prepare(processed_dir: Path, destination: Path) -> None:
    run = resolve_run(processed_dir)
    quality = json.loads((run / "quality.json").read_text(encoding="utf-8"))
    if quality["status"] != "passed":
        raise ValueError("A validated run is required")
    destination.mkdir(parents=True, exist_ok=True)
    for table in MODEL_TABLES:
        shutil.copy2(run / "csv" / f"{table}.csv", destination / f"{table}.csv")
    shutil.copy2(run / "summary.json", destination / "source_summary.json")
    print(f"Power BI data ready: {destination.resolve()}")
    print("In Desktop, set DataFolder to this path, keep DataSourceMode=CSV, then Refresh.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--destination", type=Path, default=Path("powerbi/data"))
    args = parser.parse_args()
    prepare(args.processed_dir, args.destination)

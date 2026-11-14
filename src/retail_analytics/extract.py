"""Explicit extraction, immutable inputs, and source fingerprints."""

import hashlib
from pathlib import Path

import pandas as pd

from retail_analytics.contracts import CONTRACTS


class DataQualityError(ValueError):
    """The source violates a blocking data contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract(raw_dir: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    missing = [c.filename for c in CONTRACTS.values() if not (raw_dir / c.filename).is_file()]
    if missing:
        raise DataQualityError(f"Missing source files: {', '.join(missing)}")
    tables, manifest = {}, {}
    for name, contract in CONTRACTS.items():
        path = raw_dir / contract.filename
        # Keep identifiers and ZIP prefixes as text; 'NA' is never a null sentinel.
        frame = pd.read_csv(path, dtype="string", keep_default_na=False, na_values=[""])
        absent = set(contract.columns) - set(frame.columns)
        if absent:
            raise DataQualityError(f"{name}: missing columns {sorted(absent)}")
        if frame.empty:
            raise DataQualityError(f"{name}: empty source table")
        tables[name] = frame.loc[:, list(contract.columns)].copy()
        manifest[name] = {
            "filename": contract.filename,
            "sha256": sha256_file(path),
            "rows": len(frame),
            "bytes": path.stat().st_size,
            "extra_columns": sorted(set(frame.columns) - set(contract.columns)),
        }
    return tables, manifest

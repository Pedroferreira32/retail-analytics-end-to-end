"""Download from the original public Kaggle endpoint, without redistributing raw data."""

import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from retail_analytics.contracts import CONTRACTS
from retail_analytics.extract import sha256_file
from retail_analytics.pipeline import write_json

DATASET_URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"
MAX_BYTES = 1024**3


def download_olist(destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    expected = {c.filename for c in CONTRACTS.values()}
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        archive = root / "olist.zip"
        request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "RetailAnalytics/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as target:
            size = 0
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > MAX_BYTES:
                    raise ValueError("Archive exceeds 1 GiB")
                target.write(block)
        if not zipfile.is_zipfile(archive):
            raise ValueError(
                "Kaggle did not return a ZIP; use the manual download in docs/data-source.md"
            )
        with zipfile.ZipFile(archive) as zipped:
            members = zipped.infolist()
            names = [m.filename for m in members]
            if len(names) != len(set(names)) or set(names) != expected:
                raise ValueError(
                    "Unexpected Olist archive contents; inspect before updating contracts"
                )
            if sum(m.file_size for m in members) > MAX_BYTES:
                raise ValueError("Expanded archive exceeds 1 GiB")
            for name in names:
                # No arbitrary archive paths are accepted; only contract filenames.
                with zipped.open(name) as source, (root / name).open("wb") as target:
                    shutil.copyfileobj(source, target)
            # Check every existing source before writing any file.
            for name in names:
                current = destination / name
                if current.exists() and sha256_file(current) != sha256_file(root / name):
                    raise FileExistsError(f"Refusing to overwrite changed source: {name}")
            for name in names:
                if not (destination / name).exists():
                    shutil.copy2(root / name, destination / name)
        metadata = {
            "dataset": "olistbr/brazilian-ecommerce",
            "url": DATASET_URL,
            "license": "CC BY-NC-SA 4.0",
            "archive_sha256": sha256_file(archive),
            "files": sorted(expected),
        }
        write_json(destination / "download_manifest.json", metadata)
    return metadata

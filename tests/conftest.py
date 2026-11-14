from pathlib import Path

import pytest

from retail_analytics.extract import extract
from retail_analytics.pipeline import run_pipeline
from retail_analytics.quality import normalize_and_validate
from retail_analytics.transform import build_model


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures" / "olist"


@pytest.fixture
def raw(fixtures_dir):
    return extract(fixtures_dir)[0]


@pytest.fixture
def normalized(raw):
    return normalize_and_validate(raw)[0]


@pytest.fixture
def model(normalized):
    return build_model(normalized)


@pytest.fixture
def validated_run(fixtures_dir, tmp_path):
    return run_pipeline(fixtures_dir, tmp_path / "processed", "synthetic")

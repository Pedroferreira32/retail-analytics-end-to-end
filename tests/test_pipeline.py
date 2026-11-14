import json
import shutil

import duckdb
import pandas as pd
import pytest
import sqlglot

from retail_analytics.cli import main
from retail_analytics.extract import DataQualityError
from retail_analytics.pipeline import resolve_run, run_pipeline
from retail_analytics.warehouse import MARTS, render_mart


@pytest.mark.integration
def test_full_pipeline_sql_and_rfm(validated_run):
    summary = json.loads((validated_run / "summary.json").read_text())
    assert summary["gmv_cents"] == 13031
    assert summary["delivered_orders"] == 3
    assert summary["average_review_score"] == 3.5
    assert summary["late_delivery_rate"] == 1 / 3
    assert summary["repeat_customers"] == 1
    with duckdb.connect(str(validated_run / "retail.duckdb"), read_only=True) as con:
        assert (
            con.execute(
                "SELECT monetary_cents FROM mart_customer_rfm WHERE customer_unique_id='u1'"
            ).fetchone()[0]
            == 3031
        )
        assert (
            con.execute(
                "SELECT recency_days FROM mart_customer_rfm WHERE customer_unique_id='u1'"
            ).fetchone()[0]
            == 2
        )
    assert all(json.loads((validated_run / "reconciliation.json").read_text())["checks"].values())
    assert resolve_run(validated_run.parents[1]) == validated_run


def test_repeat_run_has_identical_data(fixtures_dir, tmp_path):
    output = tmp_path / "processed"
    first = run_pipeline(fixtures_dir, output, "synthetic")
    second = run_pipeline(fixtures_dir, output, "synthetic")
    assert first != second
    for file in (first / "parquet").glob("*.parquet"):
        pd.testing.assert_frame_equal(
            pd.read_parquet(file), pd.read_parquet(second / "parquet" / file.name)
        )
    assert (first / "summary.json").read_bytes() == (second / "summary.json").read_bytes()


def test_failure_does_not_advance_latest(fixtures_dir, tmp_path):
    raw = tmp_path / "raw"
    shutil.copytree(fixtures_dir, raw)
    output = tmp_path / "processed"
    first = run_pipeline(raw, output, "synthetic")
    path = raw / "olist_order_items_dataset.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "price"] = -1
    frame.to_csv(path, index=False)
    with pytest.raises(DataQualityError):
        run_pipeline(raw, output, "synthetic")
    assert resolve_run(output) == first


def test_paths_must_not_overlap(fixtures_dir):
    with pytest.raises(ValueError, match="overlap"):
        run_pipeline(fixtures_dir, fixtures_dir / "out", "synthetic")


def test_latest_path_cannot_escape(tmp_path):
    (tmp_path / "latest.json").write_text('{"path":"../elsewhere"}')
    with pytest.raises(ValueError, match="Invalid latest"):
        resolve_run(tmp_path)


@pytest.mark.parametrize("name", MARTS)
def test_mart_sql_parses_in_bigquery(name):
    rendered = render_mart(name, "bigquery", "2018-10-18", "demo-project.retail_analytics")
    assert "{{" not in rendered
    assert sqlglot.parse_one(rendered, read="bigquery") is not None


def test_sql_rejects_interpolation():
    with pytest.raises(ValueError):
        render_mart("mart_monthly_sales", "bigquery", "2018-10-18", "bad`;DROP")
    with pytest.raises(ValueError):
        render_mart("mart_monthly_sales", "duckdb", "2018-10-18';DROP")


def test_cli_failure_returns_nonzero(tmp_path, capsys):
    assert (
        main(
            [
                "run",
                "--raw-dir",
                str(tmp_path),
                "--output-dir",
                str(tmp_path / "out"),
                "--source-kind",
                "synthetic",
            ]
        )
        == 1
    )
    assert "ERROR:" in capsys.readouterr().err

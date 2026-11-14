import json
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from retail_analytics.bigquery import publish, validate_target
from retail_analytics.extract import sha256_file


class FakeJob:
    job_id = "unit-test-job"

    def __init__(self, rows=()):
        self.rows = rows

    def result(self):
        return self.rows


class FakeClient:
    def __init__(self, run, bad_gmv=False, bad_rows=False):
        self.summary = json.loads((run / "summary.json").read_text())
        self.manifest = json.loads((run / "manifest.json").read_text())
        self.queries, self.loads, self.datasets = [], [], []
        self.bad_gmv, self.bad_rows = bad_gmv, bad_rows

    def create_dataset(self, dataset, **kwargs):
        self.datasets.append(dataset)

    def load_table_from_file(self, stream, table, **kwargs):
        assert stream.read(4) == b"PAR1"
        self.loads.append((table, kwargs))
        return FakeJob()

    def get_table(self, table):
        name = table.split(".")[-1]
        return SimpleNamespace(num_rows=self.manifest["output_rows"][name] + int(self.bad_rows))

    def query(self, sql, **kwargs):
        self.queries.append(sql)
        if "AS item_gmv" in sql:
            row = dict.fromkeys(
                ["item_gmv", "order_gmv", "monthly_gmv", "category_gmv", "state_gmv", "rfm_gmv"],
                self.summary["gmv_cents"],
            )
            row["payment_total"] = self.summary["recorded_payments_cents"]
            if self.bad_gmv:
                row["item_gmv"] += 1
            return FakeJob([row])
        return FakeJob()


@pytest.mark.parametrize(
    "project,dataset,limit",
    [
        ("x`;DROP", "retail", 10),
        ("demo-project", "x;DROP", 10),
        ("demo-project", "retail", 0),
    ],
)
def test_invalid_cloud_target(project, dataset, limit):
    with pytest.raises(ValueError):
        validate_target(project, dataset, limit)


def test_synthetic_upload_requires_explicit_flag(validated_run):
    with pytest.raises(ValueError, match="Synthetic upload blocked"):
        publish(validated_run, "demo-project", "retail", "US", client=FakeClient(validated_run))


def test_tampered_output_blocked(validated_run):
    path = validated_run / "parquet" / "dim_date.parquet"
    path.write_bytes(b"modified")
    with pytest.raises(ValueError, match="output was modified"):
        publish(
            validated_run,
            "demo-project",
            "retail",
            "US",
            allow_synthetic=True,
            client=FakeClient(validated_run),
        )


@pytest.mark.parametrize(
    "name,column,data_type",
    [
        ("dim_date", "date", pa.timestamp("ns")),
        ("fct_orders", "purchase_date", pa.timestamp("ns")),
        ("fct_orders", "purchase_date", pa.int64()),
    ],
)
def test_incompatible_parquet_types_fail_before_cloud_writes(
    validated_run, name, column, data_type
):
    # Reproduce a previously validated artifact, rather than a tampered-file error.
    path = validated_run / "parquet" / f"{name}.parquet"
    table = pq.read_table(path)
    table = table.set_column(
        table.schema.get_field_index(column), column, table[column].cast(data_type)
    )
    pq.write_table(table, path)
    manifest_path = validated_run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["parquet_sha256"][name] = sha256_file(path)
    manifest_path.write_text(json.dumps(manifest))
    client = FakeClient(validated_run)
    with pytest.raises(ValueError, match="retail run"):
        publish(validated_run, "demo-project", "retail", "US", allow_synthetic=True, client=client)
    assert not client.datasets
    assert not client.loads
    assert not client.queries


def test_cloud_snapshot_validates_before_promotion(validated_run):
    client = FakeClient(validated_run)
    result = publish(
        validated_run, "demo-project", "retail", "US", allow_synthetic=True, client=client
    )
    assert result["status"] == "published"
    assert len(client.loads) == 7
    checks = next(i for i, q in enumerate(client.queries) if "AS item_gmv" in q)
    promotions = [i for i, q in enumerate(client.queries) if q.startswith("CREATE OR REPLACE VIEW")]
    assert len(promotions) == 11
    assert min(promotions) > checks
    assert client.loads[0][1]["job_config"].write_disposition == "WRITE_EMPTY"
    facts = [kwargs["job_config"] for table, kwargs in client.loads if ".fct_" in table]
    assert all(c.time_partitioning.field == "purchase_date" for c in facts)


@pytest.mark.parametrize("bad_rows,bad_gmv", [(True, False), (False, True)])
def test_failed_cloud_validation_never_promotes(validated_run, bad_rows, bad_gmv):
    client = FakeClient(validated_run, bad_gmv=bad_gmv, bad_rows=bad_rows)
    with pytest.raises(ValueError, match="mismatch|reconciliation failed"):
        publish(validated_run, "demo-project", "retail", "US", allow_synthetic=True, client=client)
    assert not any(q.startswith("CREATE OR REPLACE VIEW") for q in client.queries)

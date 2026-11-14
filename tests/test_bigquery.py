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
    def __init__(self, run, bad_gmv=False, bad_rows=False, partition_expiration_ms=None):
        self.summary = json.loads((run / "summary.json").read_text())
        self.manifest = json.loads((run / "manifest.json").read_text())
        self.queries, self.loads, self.datasets = [], [], []
        self.bad_gmv, self.bad_rows = bad_gmv, bad_rows
        self.partition_expiration_ms = partition_expiration_ms

    def create_dataset(self, dataset, **kwargs):
        # Model server-applied Sandbox retention returned by create_dataset.
        dataset.default_partition_expiration_ms = self.partition_expiration_ms
        if self.partition_expiration_ms:
            dataset.default_table_expiration_ms = self.partition_expiration_ms
        self.datasets.append(dataset)
        return dataset

    def load_table_from_file(self, stream, table, **kwargs):
        assert stream.read(4) == b"PAR1"
        self.loads.append((table, kwargs))
        return FakeJob()

    def get_table(self, table):
        name = table.split(".")[-1]
        return SimpleNamespace(num_rows=self.manifest["output_rows"][name] + int(self.bad_rows))

    def query(self, sql, **kwargs):
        self.queries.append(sql)
        if "AS row_count" in sql:
            return FakeJob(
                [
                    {"table_name": name, "row_count": rows + int(self.bad_rows)}
                    for name, rows in self.manifest["output_rows"].items()
                ]
            )
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


def test_historical_partitions_are_blocked_before_upload(validated_run):
    client = FakeClient(validated_run, partition_expiration_ms=60 * 86400 * 1000)
    with pytest.raises(ValueError, match="partition expiration"):
        publish(validated_run, "demo-project", "retail", "US", allow_synthetic=True, client=client)
    assert not client.loads
    assert not client.queries


def test_unpartitioned_sandbox_load_preserves_retention_and_clustering(validated_run):
    retention = 60 * 86400 * 1000
    client = FakeClient(validated_run, partition_expiration_ms=retention)
    result = publish(
        validated_run,
        "demo-project",
        "retail",
        "US",
        allow_synthetic=True,
        client=client,
        partition_facts=False,
    )
    assert result["status"] == "published"
    assert result["fact_partitioning"] == "none"
    assert result["row_counts"] == client.manifest["output_rows"]
    assert client.datasets[0].default_table_expiration_ms == retention
    assert client.datasets[0].default_partition_expiration_ms == retention
    facts = [config["job_config"] for table, config in client.loads if ".fct_" in table]
    assert len(facts) == 3
    assert all(config.time_partitioning is None for config in facts)
    assert all(config.clustering_fields == ["order_status", "customer_id"] for config in facts)


def test_row_count_validation_queries_data_instead_of_table_metadata(validated_run):
    client = FakeClient(validated_run)
    client.get_table = lambda table: SimpleNamespace(num_rows=0)
    result = publish(
        validated_run, "demo-project", "retail", "US", allow_synthetic=True, client=client
    )
    assert result["row_counts"] == client.manifest["output_rows"]
    assert any("COUNT(*) AS row_count" in query for query in client.queries)


def test_cli_can_request_a_historical_sandbox_load(validated_run, monkeypatch):
    from retail_analytics import bigquery
    from retail_analytics.cli import main

    client = FakeClient(validated_run, partition_expiration_ms=60 * 86400 * 1000)
    original = bigquery.publish

    def with_client(*args, **kwargs):
        return original(*args, **kwargs, client=client)

    monkeypatch.setattr(bigquery, "publish", with_client)
    result = main(
        [
            "bigquery",
            "--processed-dir",
            str(validated_run),
            "--project",
            "demo-project",
            "--allow-synthetic",
            "--no-partitioning",
        ]
    )
    assert result == 0
    assert all(config["job_config"].time_partitioning is None for _, config in client.loads)


@pytest.mark.parametrize("bad_rows,bad_gmv", [(True, False), (False, True)])
def test_failed_cloud_validation_never_promotes(validated_run, bad_rows, bad_gmv):
    client = FakeClient(validated_run, bad_gmv=bad_gmv, bad_rows=bad_rows)
    with pytest.raises(ValueError, match="mismatch|reconciliation failed"):
        publish(validated_run, "demo-project", "retail", "US", allow_synthetic=True, client=client)
    assert not any(q.startswith("CREATE OR REPLACE VIEW") for q in client.queries)

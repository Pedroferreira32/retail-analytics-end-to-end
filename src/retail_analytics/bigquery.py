"""Validated, versioned BigQuery releases using ADC locally or WIF in Actions.

Canonical views are advanced only after ALL snapshot tables reconcile. View updates
are individually atomic; BigQuery does not offer a multi-view atomic DDL transaction.
Consumers requiring a consistent release should use the returned snapshot dataset.
"""

import json
import re
from pathlib import Path

from retail_analytics.extract import sha256_file
from retail_analytics.pipeline import write_json
from retail_analytics.warehouse import MARTS, MODEL_TABLES, render_mart


def validate_target(project: str, dataset: str, maximum_bytes_billed: int) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
        raise ValueError("Invalid GCP project ID")
    if not re.fullmatch(r"[A-Za-z_]\w{0,500}", dataset, flags=re.ASCII):
        raise ValueError("Invalid BigQuery dataset ID")
    if maximum_bytes_billed < 1:
        raise ValueError("maximum_bytes_billed must be positive")


def publish(
    run: Path,
    project: str,
    dataset: str,
    location: str,
    maximum_bytes_billed: int = 1024**3,
    allow_synthetic: bool = False,
    client=None,
) -> dict:
    validate_target(project, dataset, maximum_bytes_billed)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    quality = json.loads((run / "quality.json").read_text(encoding="utf-8"))
    reconciliation = json.loads((run / "reconciliation.json").read_text(encoding="utf-8"))
    if quality["status"] != "passed" or reconciliation["status"] != "passed":
        raise ValueError("Only validated runs can be published")
    if manifest["source_kind"] != "olist" and not allow_synthetic:
        raise ValueError("Synthetic upload blocked; use --allow-synthetic for isolated testing")
    for name in MODEL_TABLES + MARTS:
        if sha256_file(run / "parquet" / f"{name}.parquet") != manifest["parquet_sha256"][name]:
            raise ValueError(f"Validated output was modified: {name}")
    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise ValueError("Install cloud dependencies: pip install '.[bigquery]'") from exc
    client = client or bigquery.Client(project=project, location=location)
    release = re.sub(r"[^A-Za-z0-9_]", "_", manifest["run_id"])
    snapshot_id = f"{project}.{dataset}__{release}"
    canonical_id = f"{project}.{dataset}"
    # This is a new dataset per run: failed uploads never replace a working release.
    snapshot = bigquery.Dataset(snapshot_id)
    snapshot.location = location
    snapshot.description = f"Retail Analytics validated snapshot {manifest['run_id']}"
    snapshot.labels = {"project": "retail-analytics", "source": manifest["source_kind"]}
    client.create_dataset(snapshot, exists_ok=False)
    jobs = []
    for name in MODEL_TABLES:
        config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_EMPTY,
        )
        if name.startswith("fct_"):
            config.time_partitioning = bigquery.TimePartitioning(field="purchase_date")
            config.clustering_fields = ["order_status", "customer_id"]
        with (run / "parquet" / f"{name}.parquet").open("rb") as stream:
            job = client.load_table_from_file(
                stream, f"{snapshot_id}.{name}", job_config=config, location=location
            )
            job.result()
            jobs.append(job.job_id)
    query_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=maximum_bytes_billed, use_legacy_sql=False
    )
    for name in MARTS:
        sql = render_mart(name, "bigquery", summary["rfm_reference_date"], snapshot_id)
        job = client.query(
            f"CREATE TABLE `{snapshot_id}.{name}` AS {sql}",
            job_config=query_config,
            location=location,
        )
        job.result()
        jobs.append(job.job_id)
    # Full cloud reconciliation before canonical views change.
    for name, expected_rows in manifest["output_rows"].items():
        actual = client.get_table(f"{snapshot_id}.{name}").num_rows
        if actual != expected_rows:
            raise ValueError(f"BigQuery row count mismatch for {name}: {actual} != {expected_rows}")
    sql = f"""
    SELECT
      (SELECT SUM(price_cents) FROM `{snapshot_id}.fct_order_items`
        WHERE is_eligible_gmv) AS item_gmv,
      (SELECT SUM(merchandise_value_cents) FROM `{snapshot_id}.fct_orders`
        WHERE is_eligible_gmv) AS order_gmv,
      (SELECT SUM(gmv_cents) FROM `{snapshot_id}.mart_monthly_sales`) AS monthly_gmv,
      (SELECT SUM(gmv_cents) FROM `{snapshot_id}.mart_category_sales`) AS category_gmv,
      (SELECT SUM(gmv_cents) FROM `{snapshot_id}.mart_state_sales`) AS state_gmv,
      (SELECT SUM(monetary_cents) FROM `{snapshot_id}.mart_customer_rfm`) AS rfm_gmv,
      (SELECT SUM(payment_value_cents) FROM `{snapshot_id}.fct_payments`) AS payment_total
    """
    result = next(iter(client.query(sql, job_config=query_config, location=location).result()))
    for field in ["item_gmv", "order_gmv", "monthly_gmv", "category_gmv", "state_gmv", "rfm_gmv"]:
        if int(result[field] or 0) != summary["gmv_cents"]:
            raise ValueError(f"BigQuery GMV reconciliation failed: {field}")
    if int(result["payment_total"] or 0) != summary["recorded_payments_cents"]:
        raise ValueError("BigQuery payment reconciliation failed")
    canonical = bigquery.Dataset(canonical_id)
    canonical.location = location
    client.create_dataset(canonical, exists_ok=True)
    for name in MODEL_TABLES + MARTS:
        view = bigquery.Table(f"{canonical_id}.{name}")
        view.view_query = f"SELECT * FROM `{snapshot_id}.{name}`"
        # CREATE OR REPLACE VIEW refuses to overwrite a user's physical table.
        client.query(
            f"CREATE OR REPLACE VIEW `{canonical_id}.{name}` AS {view.view_query}",
            job_config=query_config,
            location=location,
        ).result()
    publication = {
        "status": "published",
        "run_id": manifest["run_id"],
        "canonical_dataset": canonical_id,
        "snapshot_dataset": snapshot_id,
        "location": location,
        "validation": "row counts, six GMV totals, payments",
        "job_ids": jobs,
    }
    write_json(run / "bigquery_publication.json", publication)
    return publication

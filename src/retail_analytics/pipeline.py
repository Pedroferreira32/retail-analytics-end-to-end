"""Publish a local run only after source contracts and SQL reconciliation pass."""

import json
import os
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from retail_analytics import __version__
from retail_analytics.extract import extract, sha256_file
from retail_analytics.quality import normalize_and_validate
from retail_analytics.transform import build_model
from retail_analytics.warehouse import build_warehouse, reconcile


def resolve_run(path: Path) -> Path:
    path = path.resolve()
    if (path / "manifest.json").is_file():
        return path
    metadata = json.loads((path / "latest.json").read_text(encoding="utf-8"))
    result = (path / metadata["path"]).resolve()
    if not result.is_relative_to(path / "runs"):
        raise ValueError("Invalid latest run pointer")
    return result


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )


def run_pipeline(raw_dir: Path, output_dir: Path, source_kind: str) -> Path:
    if source_kind not in {"olist", "synthetic"}:
        raise ValueError("source_kind must be olist or synthetic")
    raw_dir, output_dir = raw_dir.resolve(), output_dir.resolve()
    if (
        raw_dir == output_dir
        or output_dir.is_relative_to(raw_dir)
        or raw_dir.is_relative_to(output_dir)
    ):
        raise ValueError("Source and destination paths must not overlap")
    raw, source_manifest = extract(raw_dir)
    tables, quality = normalize_and_validate(raw)
    model = build_model(tables)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".pending-", dir=runs_dir))
    try:
        marts = build_warehouse(model, stage)
        reconciliation = reconcile(model, marts)
        (stage / "parquet").mkdir()
        (stage / "csv").mkdir()
        output_rows, output_hashes = {}, {}
        for name, frame in {**model, **marts}.items():
            # BigQuery recognizes Parquet millisecond/microsecond timestamps, not
            # Arrow's default nanoseconds. Refuse truncation and preserve naive times.
            frame.to_parquet(
                stage / "parquet" / f"{name}.parquet",
                index=False,
                engine="pyarrow",
                coerce_timestamps="us",
                allow_truncated_timestamps=False,
            )
            frame.to_csv(stage / "csv" / f"{name}.csv", index=False, encoding="utf-8")
            output_rows[name] = len(frame)
            output_hashes[name] = sha256_file(stage / "parquet" / f"{name}.parquet")
        orders = model["fct_orders"]
        observed = int(orders.delivery_observed.sum())
        delivered = orders.loc[orders.is_eligible_gmv]
        reviewed = delivered.review_score.dropna()
        summary = {
            "source_kind": source_kind,
            "currency": "BRL",
            "amount_unit": "cents",
            "purchase_start": orders.purchase_date.min().strftime("%Y-%m-%d"),
            "purchase_end": orders.purchase_date.max().strftime("%Y-%m-%d"),
            "rfm_reference_date": (orders.purchase_date.max()).strftime("%Y-%m-%d"),
            "placed_orders": len(orders),
            "delivered_orders": len(delivered),
            "canceled_orders": int(orders.is_canceled.sum()),
            "gmv_cents": reconciliation["gmv_cents"],
            "freight_cents": int(delivered.freight_value_cents.sum()),
            "recorded_payments_cents": int(orders.payment_value_cents.sum()),
            "average_ticket_brl": reconciliation["gmv_cents"] / 100 / len(delivered)
            if len(delivered)
            else None,
            "delivery_observed_orders": observed,
            "late_orders": int(orders.is_late.sum()),
            "late_delivery_rate": float(orders.is_late.sum()) / observed if observed else None,
            "average_delivery_days": float(orders.delivery_days.mean()) if observed else None,
            "reviewed_delivered_orders": len(reviewed),
            "average_review_score": float(reviewed.mean()) if len(reviewed) else None,
            "repeat_customers": int(marts["mart_customer_rfm"].frequency_orders.gt(1).sum()),
            "unique_delivered_customers": len(marts["mart_customer_rfm"]),
            "orders_payment_difference_over_one_cent": int(
                orders.payment_difference_cents.abs().gt(1).sum()
            ),
        }
        # Store the same fixed historical reference used by the SQL model, never today's date.
        from datetime import timedelta

        summary["rfm_reference_date"] = (orders.purchase_date.max() + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        write_json(stage / "quality.json", quality)
        write_json(stage / "reconciliation.json", reconciliation)
        write_json(stage / "summary.json", summary)
        write_json(
            stage / "manifest.json",
            {
                "run_id": run_id,
                "created_at_utc": datetime.now(UTC).isoformat(),
                "pipeline_version": __version__,
                "source_kind": source_kind,
                "source_url": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"
                if source_kind == "olist"
                else "repository tests/fixtures/olist",
                "sources": source_manifest,
                "output_rows": output_rows,
                "parquet_sha256": output_hashes,
            },
        )
        final = runs_dir / run_id
        os.replace(stage, final)
        pointer = output_dir / f".latest-{uuid.uuid4().hex}.json"
        write_json(pointer, {"run_id": run_id, "path": f"runs/{run_id}"})
        os.replace(pointer, output_dir / "latest.json")
        return final
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise

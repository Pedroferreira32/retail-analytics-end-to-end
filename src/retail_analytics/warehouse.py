"""SQL models shared by the DuckDB verification target and BigQuery."""

import re
from datetime import timedelta
from importlib.resources import files
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow.types as arrow_types

MARTS = ("mart_monthly_sales", "mart_category_sales", "mart_state_sales", "mart_customer_rfm")
MODEL_TABLES = (
    "dim_customers",
    "dim_sellers",
    "dim_products",
    "dim_date",
    "fct_orders",
    "fct_order_items",
    "fct_payments",
)


def query_frame(con, sql: str) -> pd.DataFrame:
    # SUM(BIGINT) returns HUGEINT in DuckDB. Direct .df() can use float64,
    # losing cents above 2**53. Arrow preserves decimal128 before INT64 checking.
    arrow = con.execute(sql).to_arrow_table()
    frame = arrow.to_pandas()
    for field in arrow.schema:
        if arrow_types.is_decimal(field.type) and field.type.scale == 0:
            frame[field.name] = frame[field.name].astype("Int64")
    return frame


def sql_root() -> Path:
    bundled = files("retail_analytics").joinpath("sql")
    if bundled.is_dir():
        return Path(str(bundled))
    return Path(__file__).resolve().parents[2] / "sql"


def render_mart(name: str, dialect: str, reference_date: str, dataset: str = "") -> str:
    if name not in MARTS or dialect not in {"duckdb", "bigquery"}:
        raise ValueError("Unsupported SQL model/dialect")
    # Validate before interpolating any value as an SQL identifier or literal.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", reference_date):
        raise ValueError("reference_date must be YYYY-MM-DD")
    if dialect == "bigquery" and not re.fullmatch(
        r"[a-z][a-z0-9-]{4,61}[a-z0-9]\.[A-Za-z_]\w*", dataset
    ):
        raise ValueError("Expected project.dataset")
    sql = (sql_root() / "marts" / f"{name}.sql").read_text(encoding="utf-8")
    sql = re.sub(
        r"\{\{ref:(\w+)\}\}",
        lambda m: f"`{dataset}.{m[1]}`" if dialect == "bigquery" else f'"{m[1]}"',
        sql,
    )
    recency = (
        f"DATE_DIFF(DATE '{reference_date}', CAST(MAX(o.purchase_date) AS DATE), DAY)"
        if dialect == "bigquery"
        else f"date_diff('day', CAST(MAX(o.purchase_date) AS DATE), DATE '{reference_date}')"
    )
    return sql.replace("{{recency}}", recency)


def build_warehouse(model: dict[str, pd.DataFrame], output: Path) -> dict[str, pd.DataFrame]:
    db_path = output / "retail.duckdb"
    reference_date = (
        model["fct_orders"].purchase_date.max().date() + timedelta(days=1)
    ).isoformat()
    with duckdb.connect(str(db_path)) as con:
        con.execute("BEGIN TRANSACTION")
        for name, frame in model.items():
            con.register("incoming", frame)
            con.execute(f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM incoming')
            con.unregister("incoming")
        marts = {}
        for name in MARTS:
            sql = render_mart(name, "duckdb", reference_date)
            con.execute(f'CREATE OR REPLACE TABLE "{name}" AS {sql}')
            frame = query_frame(con, f'SELECT * FROM "{name}"')
            marts[name] = frame.sort_values(list(frame.columns), kind="stable").reset_index(
                drop=True
            )
        con.execute("COMMIT")
    return marts


def reconcile(model: dict[str, pd.DataFrame], marts: dict[str, pd.DataFrame]) -> dict:
    orders, items, payments = (model[n] for n in ("fct_orders", "fct_order_items", "fct_payments"))
    gmv = int(items.loc[items.is_eligible_gmv, "price_cents"].sum())
    checks = {
        "order_key_unique": not orders.order_id.duplicated().any(),
        "item_key_unique": not items.duplicated(["order_id", "order_item_id"]).any(),
        "items_to_orders": int(items.price_cents.sum())
        == int(orders.merchandise_value_cents.sum()),
        "freight_to_orders": int(items.freight_value_cents.sum())
        == int(orders.freight_value_cents.sum()),
        "payments_to_orders": int(payments.payment_value_cents.sum())
        == int(orders.payment_value_cents.sum()),
        "gmv_to_monthly": gmv == int(marts["mart_monthly_sales"].gmv_cents.sum()),
        "gmv_to_categories": gmv == int(marts["mart_category_sales"].gmv_cents.sum()),
        "gmv_to_states": gmv == int(marts["mart_state_sales"].gmv_cents.sum()),
        "gmv_to_rfm": gmv == int(marts["mart_customer_rfm"].monetary_cents.sum()),
        "delivered_to_monthly": int(orders.is_delivered.sum())
        == int(marts["mart_monthly_sales"].delivered_orders.sum()),
    }
    if not all(checks.values()):
        raise ValueError(f"Reconciliation failed: {[k for k, v in checks.items() if not v]}")
    return {
        "status": "passed",
        "checks": checks,
        "gmv_cents": gmv,
        "source_merchandise_cents": int(items.price_cents.sum()),
        "source_payments_cents": int(payments.payment_value_cents.sum()),
    }

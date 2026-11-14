"""Publish only aggregate evidence and precise, reproducible historical figures."""

import argparse
import json
from pathlib import Path

import duckdb
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from retail_analytics.pipeline import resolve_run, write_json
from retail_analytics.warehouse import query_frame, sql_root

ROOT = Path(__file__).resolve().parents[1]


def publish(processed_dir: Path, docs: Path) -> None:
    run = resolve_run(processed_dir)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if manifest["source_kind"] != "olist":
        raise ValueError("Public Olist evidence must not be generated from synthetic fixtures")
    evidence = docs / "evidence"
    images = docs / "images"
    evidence.mkdir(parents=True, exist_ok=True)
    images.mkdir(parents=True, exist_ok=True)
    for name in ["manifest", "summary", "quality", "reconciliation"]:
        write_json(
            evidence / f"{name}.json",
            json.loads((run / f"{name}.json").read_text(encoding="utf-8")),
        )
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    analysis = {}
    with duckdb.connect(str(run / "retail.duckdb"), read_only=True) as con:
        monthly = query_frame(con, "SELECT * FROM mart_monthly_sales ORDER BY purchase_month")
        states = query_frame(
            con,
            "SELECT customer_state, SUM(gmv_cents) AS gmv_cents "
            "FROM mart_state_sales GROUP BY customer_state "
            "ORDER BY gmv_cents DESC",
        )
        for path in sorted((sql_root() / "analysis").glob("*.sql")):
            frame = query_frame(con, path.read_text(encoding="utf-8"))
            analysis[path.stem] = json.loads(frame.to_json(orient="records"))
    write_json(evidence / "analysis.json", analysis)
    monthly.to_csv(evidence / "monthly_sales.csv", index=False)
    states.to_csv(evidence / "state_sales.csv", index=False)

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#4F6070",
            "text.color": "#172B3A",
            "axes.titleweight": "bold",
            "axes.edgecolor": "#CAD3DB",
        }
    )
    fig = plt.figure(figsize=(15, 9), facecolor="#F3F6F8")
    cards = [
        ("DELIVERED MERCHANDISE GMV", f"R$ {summary['gmv_cents'] / 100:,.2f}", "Excludes freight"),
        ("DELIVERED ORDERS", f"{summary['delivered_orders']:,}", "One row per order"),
        ("AVERAGE TICKET", f"R$ {summary['average_ticket_brl']:,.2f}", "GMV / delivered orders"),
        ("LATE DELIVERY RATE", f"{summary['late_delivery_rate']:.2%}", "Observed deliveries only"),
    ]
    for i, (label, value, detail) in enumerate(cards):
        ax = fig.add_axes([0.065 + i * 0.235, 0.755, 0.215, 0.15])
        ax.set_facecolor("white")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.text(0.06, 0.78, label, fontsize=9, color="#536777", transform=ax.transAxes)
        ax.text(
            0.06,
            0.43,
            value,
            fontsize=17 if i == 0 else 23,
            weight="bold",
            color="#176B87",
            transform=ax.transAxes,
        )
        ax.text(0.06, 0.16, detail, fontsize=9, color="#536777", transform=ax.transAxes)
    ax = fig.add_axes([0.065, 0.18, 0.42, 0.49])
    ax.set_title("Delivered merchandise by purchase month", loc="left", pad=18)
    x = pd.to_datetime(monthly.purchase_month)
    ax.plot(x, monthly.gmv_cents / 100, color="#176B87", lw=2.3, marker="o", markersize=3)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"R$ {value / 1000:,.0f}k"))
    ax.grid(axis="y", color="#E6ECF0")
    ax.tick_params(axis="x", rotation=35)
    ax.set_xlabel("Historical purchases · boundary months are sparse/incomplete")
    ax = fig.add_axes([0.56, 0.18, 0.42, 0.49])
    top = states.head(10).iloc[::-1]
    ax.set_title("Where delivered merchandise GMV is concentrated", loc="left", pad=18)
    ax.barh(top.customer_state, top.gmv_cents / 100, color="#176B87", height=0.65)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"R$ {value / 1e6:,.1f}m"))
    ax.set_xlabel("Customer state · top 10 · BRL")
    ax.grid(axis="x", color="#E6ECF0")
    ax.set_axisbelow(True)
    note = fig.add_axes([0.065, 0.025, 0.91, 0.035])
    note.axis("off")
    note.text(
        0,
        0.6,
        "Source: Olist / Kaggle · CC BY-NC-SA 4.0 · "
        "Noncommercial educational analysis · "
        "Figures are analytical output, not a Power BI screenshot.",
        fontsize=9,
        color="#536777",
        transform=note.transAxes,
    )
    fig.suptitle("RETAIL ANALYTICS  |  OLIST", fontsize=23, weight="bold", x=0.065, ha="left")
    fig.savefig(images / "olist-overview.png", dpi=150, facecolor=fig.get_facecolor())
    fig.savefig(images / "olist-overview.pdf", facecolor=fig.get_facecolor())
    plt.close(fig)

    # A second figure separates observed delivery outcomes from missing/ongoing observations.
    groups = pd.DataFrame(analysis["03_delivery_and_reviews"])
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained", facecolor="white")
    labels = ["On time", "Late"]
    groups = groups.sort_values("is_late")
    axes[0].bar(labels, groups.observed_deliveries, color=["#176B87", "#CC6B5A"])
    axes[0].set_title("Observed delivered orders")
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    axes[1].bar(labels, groups.average_review, color=["#176B87", "#CC6B5A"])
    axes[1].set_ylim(0, 5)
    axes[1].set_title("Latest average rating · among rated orders")
    for ax, col in zip(axes, ["observed_deliveries", "average_review"], strict=True):
        for i, value in enumerate(groups[col]):
            ax.text(
                i,
                value + (1000 if col == "observed_deliveries" else 0.08),
                f"{value:,.0f}" if col == "observed_deliveries" else f"{value:.2f}",
                ha="center",
                weight="bold",
            )
    fig.suptitle(
        "Delivery and satisfaction | association, not causation", fontsize=16, weight="bold"
    )
    fig.savefig(images / "delivery-and-reviews.png", dpi=150)
    plt.close(fig)

    # Machine-readable output dictionary with measured row counts, grain and units.
    grains = {
        "dim_customers": "One customer_id (order-linked identity; customer_unique_id can repeat)",
        "dim_products": "One product_id",
        "dim_sellers": "One seller_id",
        "dim_date": "One purchase calendar date",
        "fct_orders": "One order_id, all statuses",
        "fct_order_items": "One (order_id, order_item_id)",
        "fct_payments": "One (order_id, payment_sequential)",
        "mart_monthly_sales": "One purchase month",
        "mart_category_sales": "One purchase month and product category",
        "mart_state_sales": "One purchase month and customer state",
        "mart_customer_rfm": "One customer_unique_id with delivered orders",
    }
    lines = [
        "# Data dictionary",
        "",
        "Generated from the validated complete Olist run. "
        "Monetary `*_cents` fields are integer BRL cents. Timestamps have no inferred timezone. "
        "Source column names (including `lenght`) follow Olist.",
        "",
    ]
    for name, grain in grains.items():
        frame = pd.read_parquet(run / "parquet" / f"{name}.parquet")
        lines.extend(
            [
                f"## `{name}`",
                "",
                f"Grain: {grain}. Rows: {len(frame):,}.",
                "",
                "| Column | Pandas type | Nulls |",
                "| --- | --- | ---: |",
            ]
        )
        lines.extend(
            f"| `{col}` | `{frame[col].dtype}` | {int(frame[col].isna().sum()):,} |"
            for col in frame
        )
        lines.append("")
    (docs / "data-dictionary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Published aggregate evidence: {evidence}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--docs-dir", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    publish(args.processed_dir, args.docs_dir)

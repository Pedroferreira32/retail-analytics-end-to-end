"""Static design QA from PBIR geometry plus validated data; not a Desktop render."""

import io
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from build_powerbi import COLORS
from matplotlib.ticker import FuncFormatter, MaxNLocator
from PIL import Image, ImageDraw, ImageFont

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[1]

RUN = ROOT / "data/processed"
RUN = RUN / json.loads((RUN / "latest.json").read_text(encoding="utf-8"))["path"]
SUMMARY = json.loads((RUN / "summary.json").read_text(encoding="utf-8"))
FRAMES = {
    n: pd.read_parquet(RUN / "parquet" / (n + ".parquet"))
    for n in [
        "fct_orders",
        "fct_order_items",
        "fct_payments",
        "dim_customers",
        "dim_products",
        "dim_sellers",
    ]
}
ORDERS = FRAMES["fct_orders"]
ITEMS = FRAMES["fct_order_items"].loc[lambda d: d.is_eligible_gmv]
S = 2
FONTS = str(Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans")
CLIPPED = []


def val(v):
    if "solid" in v:
        return val(v["solid"]["color"])
    q = v["expr"]["Literal"]["Value"]
    if q.startswith("'"):
        return q[1:-1].replace("''", "'")
    if q in ("true", "false"):
        return q == "true"
    return float(q.rstrip("DL"))


def obj(v, group, prop, container=False, default=None):
    source = v["visual"].get("visualContainerObjects" if container else "objects", {})
    for e in source.get(group, []):
        if e.get("selector", {}).get("id", "default") == "default" and prop in e["properties"]:
            return val(e["properties"][prop])
    return default


def font(size, bold=False):
    return ImageFont.truetype(FONTS + ("-Bold.ttf" if bold else ".ttf"), round(size * S))


def text(draw, text, box, size=14, color=None, bold=False, align="left", key=""):
    x, y, w, h = box
    f = font(size, bold)
    lines = [""]
    for word in text.split():
        candidate = (lines[-1] + " " + word).strip()
        if draw.textlength(candidate, font=f) > w * S and lines[-1]:
            lines.append(word)
        else:
            lines[-1] = candidate
    line_h = size * 1.32
    if len(lines) * line_h > h + 4:
        CLIPPED.append((key, text, len(lines) * line_h, h))
    for i, line in enumerate(lines):
        xx = x * S
        if align == "center":
            xx += (w * S - draw.textlength(line, font=f)) / 2
        if align == "right":
            xx += w * S - draw.textlength(line, font=f)
        draw.text((xx, (y + i * line_h) * S), line, font=f, fill=color or COLORS["text"])


def metric(name):
    s = SUMMARY
    return {
        "GMV entregue": s["gmv_cents"] / 100,
        "Frete entregue": s["freight_cents"] / 100,
        "Pedidos entregues": s["delivered_orders"],
        "Ticket médio": s["average_ticket_brl"],
        "Taxa de atraso": s["late_delivery_rate"],
        "Itens entregues": len(ITEMS),
        "Prazo médio dias": s["average_delivery_days"],
        "Nota média": s["average_review_score"],
        "Cobertura de avaliação": s["reviewed_delivered_orders"] / s["delivered_orders"],
        "Pagamentos registrados": s["recorded_payments_cents"] / 100,
        "Diferença de pagamentos": ORDERS.payment_difference_cents.sum() / 100,
        "Pedidos com divergência": s["orders_payment_difference_over_one_cent"],
        "Taxa de cancelamento": s["canceled_orders"] / s["placed_orders"],
    }[name]


def br(n, decimals=0):
    return f"{n:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def chart_series(name):
    if name == "monthly_gmv":
        return ITEMS.groupby("purchase_month").price_cents.sum() / 100
    if name == "late_month":
        d = ORDERS.loc[ORDERS.delivery_observed]
        groups = d.groupby("purchase_month").is_late.agg(["mean", "size"])
        return groups.loc[groups["size"] >= 100, "mean"]
    if name == "state_sales":
        d = ITEMS.merge(
            FRAMES["dim_customers"][["customer_id", "customer_state"]], on="customer_id"
        )
        return (d.groupby("customer_state").price_cents.sum() / 100).nlargest(10)
    if name == "category_sales":
        d = ITEMS.merge(
            FRAMES["dim_products"][["product_id", "product_category_name"]], on="product_id"
        )
        return (d.groupby("product_category_name").price_cents.sum() / 100).nlargest(10)
    if name == "seller_sales":
        d = ITEMS.merge(FRAMES["dim_sellers"][["seller_id", "seller_state"]], on="seller_id")
        return (d.groupby("seller_state").price_cents.sum() / 100).nlargest(10)
    if name == "state_delivery":
        d = ORDERS.merge(
            FRAMES["dim_customers"][["customer_id", "customer_state"]], on="customer_id"
        )
        return d.groupby("customer_state").is_late.sum().nlargest(10)
    if name == "payment_types":
        return (
            FRAMES["fct_payments"].groupby("payment_type").payment_value_cents.sum() / 100
        ).sort_values(ascending=False)


def render_chart(image, draw, v):
    p = v["position"]
    x, y, w, h = [p[k] for k in ["x", "y", "width", "height"]]
    draw.rounded_rectangle(
        (x * S, y * S, (x + w) * S, (y + h) * S),
        radius=10 * S,
        fill="white",
        outline=COLORS["line"],
        width=S,
    )
    text(
        draw,
        obj(v, "title", "text", True),
        (x + 16, y + 16, w - 32, 26),
        17,
        COLORS["text"],
        True,
        key=v["name"] + " title",
    )
    text(
        draw,
        obj(v, "subTitle", "text", True),
        (x + 16, y + 43, w - 32, 32),
        13,
        COLORS["muted"],
        key=v["name"] + " subtitle",
    )
    if v["visual"]["visualType"] == "tableEx":
        d = (
            ORDERS.assign(divergent=ORDERS.payment_difference_cents.abs() > 1)
            .groupby("order_status")
            .agg(
                orders=("order_id", "size"),
                balance=("payment_difference_cents", "sum"),
                diff=("divergent", "sum"),
            )
            .sort_values("diff", ascending=False)
        )
        headers = ["Status", "Pedidos", "Saldo (R$)", "Divergências"]
        widths = [168, 110, 175, w - 32 - 453]
        yy = y + 83
        xx = x + 16
        draw.rectangle((xx * S, yy * S, (x + w - 16) * S, (yy + 26) * S), fill=COLORS["navy"])
        for label, ww in zip(headers, widths, strict=True):
            text(draw, label, (xx + 7, yy + 5, ww - 12, 23), 12, "white", True)
            xx += ww
        yy += 26
        for i, (status, row) in enumerate(d.iterrows()):
            draw.rectangle(
                ((x + 16) * S, yy * S, (x + w - 16) * S, (yy + 23) * S),
                fill="#F1F5F8" if i % 2 else "white",
            )
            xx = x + 16
            for value, ww in zip(
                [status, br(row.orders), br(row.balance / 100, 2), br(row["diff"])],
                widths,
                strict=True,
            ):
                text(draw, value, (xx + 7, yy + 4, ww - 12, 23), 12)
                xx += ww
            yy += 23
        draw.rectangle(((x + 16) * S, yy * S, (x + w - 16) * S, (yy + 23) * S), fill="#E5EFF1")
        xx = x + 16
        for value, ww in zip(
            ["Total", br(d.orders.sum()), br(d.balance.sum() / 100, 2), br(d["diff"].sum())],
            widths,
            strict=True,
        ):
            text(draw, value, (xx + 7, yy + 4, ww - 12, 23), 12, bold=True)
            xx += ww
        return
    data = chart_series(v["name"])
    line = v["visual"]["visualType"] == "lineChart"
    figure = plt.figure(figsize=(w / 100, h / 100), dpi=100 * S, facecolor="none")
    left = (
        0.11
        if line
        else 0.25
        if v["name"] == "category_sales"
        else 0.22
        if v["name"] == "payment_types"
        else 0.08
    )
    ax = figure.add_axes([left, 0.16, 0.94 - left, 0.56], facecolor="none")
    color = obj(v, "dataPoint", "defaultColor")
    units = obj(v, "valueAxis", "labelDisplayUnits", default=1)
    precision = int(obj(v, "valueAxis", "labelPrecision", default=0))
    is_pct = v["name"] == "late_month"

    def fmt(n, _=None):
        return br(n * 100, 1) + "%" if is_pct else br(n / units, precision)

    if line:
        ax.plot(range(len(data)), data.values, color=color, linewidth=2.3)
        ticks = list(range(0, len(data), 3))
        ax.set_xticks(ticks, [str(data.index[i])[:7] for i in ticks], rotation=28, ha="right")
        ax.yaxis.set_major_formatter(FuncFormatter(fmt))
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_locator(MaxNLocator(4))
        ax.grid(axis="y", color="#E5EBF0", lw=0.7)
    else:
        ax.barh(range(len(data)), data.values, color=color, height=0.64)
        ax.set_yticks(range(len(data)), data.index)
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(FuncFormatter(fmt))
        ax.xaxis.set_major_locator(MaxNLocator(3))
        ax.set_xlim(0, max(data.values) * 1.25)
        ax.grid(axis="x", color="#E5EBF0", lw=0.7)
        for i, n in enumerate(data.values):
            ax.text(
                n + max(data.values) * 0.02,
                i,
                fmt(n),
                va="center",
                fontsize=8,
                color=COLORS["text"],
            )
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="both", length=0, labelsize=8, colors=COLORS["muted"])
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", transparent=True, dpi=100 * S)
    plt.close(figure)
    buffer.seek(0)
    image.alpha_composite(Image.open(buffer).convert("RGBA"), (round(x * S), round(y * S)))


def render(page):
    image = Image.new("RGBA", (1440 * S, 932 * S), COLORS["canvas"])
    draw = ImageDraw.Draw(image)
    visuals = [
        json.loads(p.read_text(encoding="utf-8")) for p in (page / "visuals").glob("*/visual.json")
    ]
    for v in sorted(visuals, key=lambda v: v["position"]["z"]):
        p = v["position"]
        x, y, w, h = [p[k] for k in ["x", "y", "width", "height"]]
        kind = v["visual"]["visualType"]
        if kind == "shape":
            color = obj(v, "fill", "fillColor")
            radius = 10 if obj(v, "shape", "tileShape") == "rectangleRounded" else 0
            draw.rounded_rectangle(
                (x * S, y * S, (x + w) * S, (y + h) * S), radius=radius * S, fill=color
            )
        elif kind == "textbox":
            para = v["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]
            run = para["textRuns"][0]
            style = run["textStyle"]
            text(
                draw,
                run["value"],
                (x, y, w, h),
                float(style["fontSize"].rstrip("px")),
                style["color"],
                "Semibold" in style["fontFamily"],
                para["horizontalTextAlignment"],
                key=v["name"],
            )
        elif kind == "card":
            m = v["visual"]["query"]["queryState"]["Values"]["projections"][0]["field"]["Measure"][
                "Property"
            ]
            n = metric(m)
            units = obj(v, "labels", "labelDisplayUnits")
            dec = int(obj(v, "labels", "labelPrecision"))
            value = br(
                n * 100 if m.startswith("Taxa") or m == "Cobertura de avaliação" else n / units, dec
            )
            if m.startswith("Taxa") or m == "Cobertura de avaliação":
                value += "%"
            elif m in [
                "GMV entregue",
                "Frete entregue",
                "Ticket médio",
                "Pagamentos registrados",
                "Diferença de pagamentos",
            ]:
                value = "R$ " + value
            if units == 1000000:
                value += " Mi"
            if units == 1000:
                value += " mil"
            text(
                draw,
                value,
                (x, y + 4, w, h),
                35,
                obj(v, "labels", "color"),
                True,
                "center",
                key=v["name"],
            )
        elif kind == "actionButton":
            draw.rounded_rectangle(
                (x * S, y * S, (x + w) * S, (y + h) * S),
                radius=8 * S,
                fill=obj(v, "fill", "fillColor"),
            )
            text(
                draw,
                obj(v, "text", "text"),
                (x + 6, y + 14, w - 12, 26),
                14,
                obj(v, "text", "fontColor"),
                True,
                "center",
                key=v["name"],
            )
        elif kind == "slicer":
            draw.rounded_rectangle(
                (x * S, y * S, (x + w) * S, (y + h) * S),
                radius=10 * S,
                fill="white",
                outline=COLORS["line"],
                width=S,
            )
            text(draw, obj(v, "header", "text"), (x + 12, y + 11, w - 24, 24), 14, bold=True)
            text(draw, "Todos", (x + 12, y + 47, w - 35, 25), 14)
            draw.polygon(
                [
                    ((x + w - 26) * S, (y + 56) * S),
                    ((x + w - 16) * S, (y + 56) * S),
                    ((x + w - 21) * S, (y + 62) * S),
                ],
                fill=COLORS["muted"],
            )
        elif kind in ["lineChart", "barChart", "tableEx"]:
            render_chart(image, draw, v)
    draw.rectangle((0, 900 * S, 1440 * S, 932 * S), fill="#E3E8ED")
    text(
        draw,
        "PRÉVIA DE DESIGN • dados Olist validados • reconstrução estática, "
        "não é uma captura do Power BI Desktop",
        (32, 908, 1376, 20),
        11,
        COLORS["muted"],
    )
    path = ROOT / "docs/images" / ("powerbi-layout-" + page.name + ".png")
    image.convert("RGB").save(path, optimize=True)
    print(path.name)


if __name__ == "__main__":
    for page in sorted((ROOT / "powerbi/RetailAnalytics.Report/definition/pages").iterdir()):
        if page.is_dir():
            render(page)
    print("POSSIBLE CLIPPING", CLIPPED)

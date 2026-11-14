"""Conformed dimensions and facts with explicit grains and integer BRL cents."""

import pandas as pd


def build_model(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    customers, sellers, products = (tables[n].copy() for n in ("customers", "sellers", "products"))
    # ZIP prefixes are not unique in Olist geolocation. Collapse BEFORE joining.
    geo = (
        tables["geolocation"]
        .groupby("geolocation_zip_code_prefix", as_index=False)
        .agg(latitude=("geolocation_lat", "median"), longitude=("geolocation_lng", "median"))
    )
    for frame, prefix in [(customers, "customer"), (sellers, "seller")]:
        enriched = frame.merge(
            geo,
            left_on=f"{prefix}_zip_code_prefix",
            right_on="geolocation_zip_code_prefix",
            how="left",
            validate="m:1",
        )
        enriched = enriched.drop(columns="geolocation_zip_code_prefix")
        if prefix == "customer":
            customers = enriched
        else:
            sellers = enriched
    products = products.merge(
        tables["translation"], on="product_category_name", how="left", validate="m:1"
    )
    products["product_category_name_english"] = products.product_category_name_english.fillna(
        products.product_category_name
    ).fillna("unknown")
    products["product_category_name"] = products.product_category_name.fillna("unknown")

    orders = tables["orders"].copy()
    orders["purchase_date"] = orders.order_purchase_timestamp.dt.normalize()
    orders["purchase_month"] = orders.purchase_date.dt.strftime("%Y-%m")
    orders["date_key"] = orders.purchase_date.dt.strftime("%Y%m%d").astype("Int64")
    orders["is_delivered"] = orders.order_status.eq("delivered")
    orders["is_canceled"] = orders.order_status.eq("canceled")
    totals = (
        tables["items"]
        .groupby("order_id", as_index=False)
        .agg(
            item_count=("order_item_id", "size"),
            merchandise_value_cents=("price_cents", "sum"),
            freight_value_cents=("freight_value_cents", "sum"),
        )
    )
    payments = (
        tables["payments"]
        .groupby("order_id", as_index=False)
        .agg(
            payment_count=("payment_sequential", "size"),
            payment_value_cents=("payment_value_cents", "sum"),
        )
    )

    # Olist allows more than one review per order and review_id can be reused.
    # Latest answer wins; ties are broken by creation, review ID, score, then text.
    reviews = (
        tables["reviews"]
        .drop_duplicates()
        .sort_values(
            [
                "order_id",
                "review_answer_timestamp",
                "review_creation_date",
                "review_id",
                "review_score",
                "review_comment_title",
                "review_comment_message",
            ],
            na_position="first",
            kind="stable",
        )
        .drop_duplicates("order_id", keep="last")
    )
    review_count = tables["reviews"].groupby("order_id").size().rename("review_count")
    reviews = reviews.merge(review_count, on="order_id", validate="1:1")
    # Free text is never exported to the analytical layer.
    reviews = reviews[
        [
            "order_id",
            "review_id",
            "review_score",
            "review_count",
            "review_creation_date",
            "review_answer_timestamp",
        ]
    ]
    for frame in [totals, payments, reviews]:
        orders = orders.merge(frame, on="order_id", how="left", validate="1:1")
    for col in [
        "item_count",
        "merchandise_value_cents",
        "freight_value_cents",
        "payment_count",
        "payment_value_cents",
        "review_count",
    ]:
        orders[col] = orders[col].fillna(0).astype("Int64")
    orders["review_score"] = orders.review_score.astype("Int64")
    orders["order_value_cents"] = orders.merchandise_value_cents + orders.freight_value_cents
    orders["payment_difference_cents"] = orders.payment_value_cents - orders.order_value_cents
    elapsed = (
        orders.order_delivered_customer_date - orders.order_purchase_timestamp
    ).dt.total_seconds() / 86400
    valid_delivery = orders.is_delivered & elapsed.ge(0) & elapsed.notna()
    orders["delivery_days"] = elapsed.where(valid_delivery).astype("Float64")
    # Estimated delivery is a promised calendar DATE; 10:00 on that date is on time.
    orders["delivery_observed"] = valid_delivery
    orders["is_late"] = (
        orders.order_delivered_customer_date.dt.normalize()
        .gt(orders.order_estimated_delivery_date.dt.normalize())
        .where(valid_delivery, pd.NA)
        .astype("boolean")
    )
    orders["is_eligible_gmv"] = orders.is_delivered
    order_context = orders[
        [
            "order_id",
            "customer_id",
            "date_key",
            "purchase_date",
            "purchase_month",
            "order_status",
            "is_eligible_gmv",
        ]
    ]
    items = tables["items"].merge(order_context, on="order_id", how="left", validate="m:1")
    payment_facts = tables["payments"].merge(
        order_context, on="order_id", how="left", validate="m:1"
    )
    dates = pd.DataFrame(
        {"date": pd.date_range(orders.purchase_date.min(), orders.purchase_date.max(), freq="D")}
    )
    dates["date_key"] = dates.date.dt.strftime("%Y%m%d").astype("Int64")
    dates["year"] = dates.date.dt.year.astype("Int64")
    dates["month_number"] = dates.date.dt.month.astype("Int64")
    dates["year_month"] = dates.date.dt.strftime("%Y-%m")
    dates["quarter"] = dates.date.dt.quarter.astype("Int64")
    dates["weekday_number"] = (dates.date.dt.dayofweek + 1).astype("Int64")
    return {
        "dim_customers": customers.sort_values("customer_id").reset_index(drop=True),
        "dim_sellers": sellers.sort_values("seller_id").reset_index(drop=True),
        "dim_products": products.sort_values("product_id").reset_index(drop=True),
        "dim_date": dates,
        "fct_orders": orders.sort_values("order_id").reset_index(drop=True),
        "fct_order_items": items.sort_values(["order_id", "order_item_id"]).reset_index(drop=True),
        "fct_payments": payment_facts.sort_values(["order_id", "payment_sequential"]).reset_index(
            drop=True
        ),
    }

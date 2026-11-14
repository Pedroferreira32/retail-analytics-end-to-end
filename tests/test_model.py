import pandas as pd

from retail_analytics.transform import build_model


def test_no_join_fanout(model):
    orders = model["fct_orders"].set_index("order_id")
    assert len(orders) == 6
    assert orders.loc["o1", "merchandise_value_cents"] == 3030
    assert orders.loc["o1", "payment_value_cents"] == 3330
    assert orders.loc["o1", "review_score"] == 5
    assert orders.loc["o1", "review_count"] == 2
    assert orders.loc["o1", "item_count"] == 2
    assert orders.loc["o1", "payment_count"] == 2


def test_gmv_excludes_canceled_and_pending_orders(model):
    items = model["fct_order_items"]
    assert items.loc[items.is_eligible_gmv, "price_cents"].sum() == 13031
    assert items.price_cents.sum() > 13031


def test_calendar_delivery_and_censoring(model):
    orders = model["fct_orders"].set_index("order_id")
    assert not orders.loc["o1", "is_late"]  # delivered 18h on promised date
    assert orders.loc["o2", "is_late"]
    assert pd.isna(orders.loc["o4", "is_late"])  # shipped, not observed
    assert pd.isna(orders.loc["o4", "delivery_days"])
    assert orders.delivery_observed.sum() == 3


def test_invalid_delivery_duration_not_counted(normalized):
    normalized["orders"].loc[0, "order_delivered_customer_date"] = pd.Timestamp("2017-12-31")
    orders = build_model(normalized)["fct_orders"].set_index("order_id")
    assert not orders.loc["o1", "delivery_observed"]
    assert pd.isna(orders.loc["o1", "delivery_days"])


def test_geo_collapse_preserves_dimension_grain(model):
    assert len(model["dim_customers"]) == 6
    assert len(model["dim_sellers"]) == 2
    assert abs(model["dim_customers"].iloc[0].latitude - -23.55) < 1e-8


def test_unknown_category_retained(model):
    products = model["dim_products"].set_index("product_id")
    assert products.loc["p3", "product_category_name"] == "unknown"


def test_latest_review_deterministic(normalized):
    expected = build_model(normalized)["fct_orders"]
    normalized["reviews"] = normalized["reviews"].sample(frac=1, random_state=42)
    pd.testing.assert_frame_equal(build_model(normalized)["fct_orders"], expected)


def test_customer_unique_id_retained(model):
    assert model["dim_customers"].customer_unique_id.nunique() == 5
    assert model["dim_customers"].customer_id.nunique() == 6


def test_no_free_text_in_analytical_outputs(model):
    assert all("review_comment_message" not in f.columns for f in model.values())

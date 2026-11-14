from retail_analytics.quality import normalize_and_validate
from retail_analytics.transform import build_model
from retail_analytics.warehouse import build_warehouse, reconcile


def test_sql_sum_preserves_cents_above_float_precision(raw, tmp_path):
    # Multiple amounts cross 2**53 cents while remaining well inside INT64.
    raw["items"].loc[0, "price"] = "90071992547409.91"
    normalized, _ = normalize_and_validate(raw)
    model = build_model(normalized)
    marts = build_warehouse(model, tmp_path)
    expected = 9007199254740991 + 2020 + 10000 + 1
    assert expected > 2**53
    assert int(marts["mart_monthly_sales"].gmv_cents.sum()) == expected
    assert str(marts["mart_monthly_sales"].gmv_cents.dtype) == "Int64"
    assert reconcile(model, marts)["gmv_cents"] == expected

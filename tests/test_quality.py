import pandas as pd
import pytest

from retail_analytics.extract import DataQualityError, extract
from retail_analytics.quality import money_to_cents, normalize_and_validate


@pytest.mark.parametrize(
    "values,expected",
    [
        (["0.29", "10.10", "0", "1234567.89"], [29, 1010, 0, 123456789]),
        (["1.000", "1.20"], [100, 120]),
    ],
)
def test_money_exact(values, expected):
    assert money_to_cents(pd.Series(values, dtype="string"), "test").tolist() == expected


@pytest.mark.parametrize("value", ["-1", "0.001", "NaN", "Infinity", "oops", None, "1e30"])
def test_money_rejects_bad_values(value):
    with pytest.raises(DataQualityError):
        money_to_cents(pd.Series([value], dtype="string"), "test")


def test_extract_requires_every_file(tmp_path):
    with pytest.raises(DataQualityError, match="Missing source"):
        extract(tmp_path)


def test_extract_requires_columns(fixtures_dir, tmp_path):
    import shutil

    shutil.copytree(fixtures_dir, tmp_path / "raw")
    path = tmp_path / "raw" / "olist_customers_dataset.csv"
    pd.read_csv(path).drop(columns="customer_id").to_csv(path, index=False)
    with pytest.raises(DataQualityError, match="missing columns"):
        extract(tmp_path / "raw")


def test_duplicate_primary_key_fails(raw):
    raw["items"] = pd.concat([raw["items"], raw["items"].iloc[[0]]], ignore_index=True)
    with pytest.raises(DataQualityError, match="duplicate primary key"):
        normalize_and_validate(raw)


def test_orphan_fails(raw):
    raw["items"].loc[0, "product_id"] = "does-not-exist"
    with pytest.raises(DataQualityError, match="orphan foreign key"):
        normalize_and_validate(raw)


def test_required_missing_fails(raw):
    raw["orders"].loc[0, "customer_id"] = pd.NA
    with pytest.raises(DataQualityError, match="required value"):
        normalize_and_validate(raw)


@pytest.mark.parametrize(
    "table,column,value,message",
    [
        ("reviews", "review_score", "6", "1..5"),
        ("orders", "order_status", "other", "unknown order status"),
        ("orders", "order_purchase_timestamp", "bad-date", "malformed timestamp"),
        ("payments", "payment_installments", "1.5", "malformed integer"),
        ("payments", "payment_installments", "-1", "negative integer"),
        ("items", "order_item_id", "0", "sequence must start"),
        ("customers", "customer_state", "XX", "invalid Brazilian state"),
        ("customers", "customer_zip_code_prefix", "123456", "invalid ZIP"),
        ("geolocation", "geolocation_lat", "91", "out of range"),
        ("geolocation", "geolocation_lat", "abc", "invalid coordinate"),
    ],
)
def test_bad_contracts(raw, table, column, value, message):
    raw[table].loc[0, column] = value
    with pytest.raises(DataQualityError, match=message):
        normalize_and_validate(raw)


def test_zip_leading_zero_preserved(normalized):
    assert normalized["customers"].iloc[0].customer_zip_code_prefix == "01000"


def test_reviews_id_reuse_is_reported_not_wrongly_rejected(raw):
    _, quality = normalize_and_validate(raw)
    assert quality["warnings"]["orders_with_multiple_reviews"] == 1
    assert quality["warnings"]["orders_without_items"] == 1
    assert quality["warnings"]["zero_payment_installments"] == 1

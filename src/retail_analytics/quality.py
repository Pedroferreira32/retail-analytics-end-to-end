"""Fail closed on broken keys/types, preserve and report business anomalies."""

from decimal import Decimal, InvalidOperation

import pandas as pd

from retail_analytics.contracts import CONTRACTS, STATES, STATUSES
from retail_analytics.extract import DataQualityError


def money_to_cents(series: pd.Series, label: str) -> pd.Series:
    def convert(value):
        if pd.isna(value):
            raise DataQualityError(f"{label}: missing monetary amount")
        try:
            amount = Decimal(str(value))
            cents = amount * 100
            if not amount.is_finite() or cents != cents.to_integral_value() or amount < 0:
                raise DataQualityError(f"{label}: invalid nonnegative two-decimal amount")
            if cents > 2**63 - 1:
                raise DataQualityError(f"{label}: amount exceeds INT64 range")
            return int(cents)
        except (InvalidOperation, ValueError, OverflowError) as exc:
            raise DataQualityError(f"{label}: malformed monetary amount") from exc

    return series.map(convert).astype("Int64")


def normalize_and_validate(tables: dict[str, pd.DataFrame]) -> tuple[dict, dict]:
    normalized, stats = {}, {}
    for name, contract in CONTRACTS.items():
        frame = tables[name].copy()
        for col in frame.columns:
            frame[col] = frame[col].str.strip().replace("", pd.NA)
        for col in set(contract.required + contract.key):
            if frame[col].isna().any():
                raise DataQualityError(f"{name}.{col}: required value is null")
        for col in contract.dates:
            try:
                frame[col] = pd.to_datetime(frame[col], format="%Y-%m-%d %H:%M:%S", errors="raise")
            except (ValueError, TypeError) as exc:
                raise DataQualityError(f"{name}.{col}: malformed timestamp") from exc
        for col in contract.integers:
            try:
                values = pd.to_numeric(frame[col], errors="raise")
                if values.dropna().mod(1).ne(0).any():
                    raise DataQualityError(f"{name}.{col}: malformed integer")
                frame[col] = values.astype("Int64")
            except (ValueError, TypeError) as exc:
                raise DataQualityError(f"{name}.{col}: malformed integer") from exc
            if frame[col].dropna().lt(0).any():
                raise DataQualityError(f"{name}.{col}: negative integer")
        for col in contract.money:
            frame[f"{col}_cents"] = money_to_cents(frame[col], f"{name}.{col}")
            frame = frame.drop(columns=col)
        if contract.key and frame.duplicated(list(contract.key)).any():
            raise DataQualityError(f"{name}: duplicate primary key {contract.key}")
        stats[name] = {"rows": len(frame), "nulls": frame.isna().sum().astype(int).to_dict()}
        normalized[name] = frame

    for child, col, parent, parent_col in [
        ("orders", "customer_id", "customers", "customer_id"),
        ("items", "order_id", "orders", "order_id"),
        ("items", "product_id", "products", "product_id"),
        ("items", "seller_id", "sellers", "seller_id"),
        ("payments", "order_id", "orders", "order_id"),
        ("reviews", "order_id", "orders", "order_id"),
    ]:
        if not normalized[child][col].isin(normalized[parent][parent_col]).all():
            raise DataQualityError(f"{child}.{col}: orphan foreign key to {parent}")
    if not normalized["orders"]["order_status"].isin(STATUSES).all():
        raise DataQualityError("orders: unknown order status")
    for name, col in [("customers", "customer_state"), ("sellers", "seller_state")]:
        if not normalized[name][col].isin(STATES).all():
            raise DataQualityError(f"{name}: invalid Brazilian state")
    if not normalized["reviews"]["review_score"].between(1, 5).fillna(False).all():
        raise DataQualityError("reviews: review_score must be 1..5")
    for name, col in [("items", "order_item_id"), ("payments", "payment_sequential")]:
        if not normalized[name][col].ge(1).fillna(False).all():
            raise DataQualityError(f"{name}.{col}: sequence must start at 1")
    for name, prefix in [
        ("customers", "customer"),
        ("sellers", "seller"),
        ("geolocation", "geolocation"),
    ]:
        col = f"{prefix}_zip_code_prefix"
        if not normalized[name][col].str.fullmatch(r"\d{1,5}").fillna(False).all():
            raise DataQualityError(f"{name}.{col}: invalid ZIP prefix")
        normalized[name][col] = normalized[name][col].str.zfill(5)
    for col, low, high in [("geolocation_lat", -90, 90), ("geolocation_lng", -180, 180)]:
        try:
            normalized["geolocation"][col] = pd.to_numeric(normalized["geolocation"][col])
        except (ValueError, TypeError) as exc:
            raise DataQualityError(f"geolocation.{col}: invalid coordinate") from exc
        if not normalized["geolocation"][col].between(low, high).all():
            raise DataQualityError(f"geolocation.{col}: coordinate out of range")

    orders = normalized["orders"]
    warnings = {
        "orders_without_items": int((~orders.order_id.isin(normalized["items"].order_id)).sum()),
        "orders_without_payments": int(
            (~orders.order_id.isin(normalized["payments"].order_id)).sum()
        ),
        "orders_without_reviews": int(
            (~orders.order_id.isin(normalized["reviews"].order_id)).sum()
        ),
        "orders_with_multiple_reviews": int(
            normalized["reviews"].groupby("order_id").size().gt(1).sum()
        ),
        "exact_duplicate_reviews": int(normalized["reviews"].duplicated().sum()),
        "delivered_without_delivery_timestamp": int(
            (
                orders.order_status.eq("delivered") & orders.order_delivered_customer_date.isna()
            ).sum()
        ),
        "delivery_before_purchase": int(
            orders.order_delivered_customer_date.lt(orders.order_purchase_timestamp).sum()
        ),
        "zero_payment_installments": int(normalized["payments"].payment_installments.eq(0).sum()),
        "missing_product_category": int(normalized["products"].product_category_name.isna().sum()),
        "untranslated_categories": int(
            (
                normalized["products"].product_category_name.notna()
                & ~normalized["products"].product_category_name.isin(
                    normalized["translation"].product_category_name
                )
            ).sum()
        ),
        "geolocation_repeated_zip_rows": int(
            normalized["geolocation"].geolocation_zip_code_prefix.duplicated().sum()
        ),
    }
    return normalized, {"status": "passed", "tables": stats, "warnings": warnings}

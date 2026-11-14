"""Source contracts. Original Olist misspellings are intentionally preserved."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Contract:
    filename: str
    columns: tuple[str, ...]
    key: tuple[str, ...] = ()
    dates: tuple[str, ...] = ()
    integers: tuple[str, ...] = ()
    money: tuple[str, ...] = ()
    required: tuple[str, ...] = ()


CONTRACTS = {
    "customers": Contract(
        "olist_customers_dataset.csv",
        (
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ),
        key=("customer_id",),
        required=("customer_unique_id", "customer_state"),
    ),
    "orders": Contract(
        "olist_orders_dataset.csv",
        (
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
        key=("order_id",),
        dates=(
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
        required=(
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_estimated_delivery_date",
        ),
    ),
    "items": Contract(
        "olist_order_items_dataset.csv",
        (
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ),
        key=("order_id", "order_item_id"),
        dates=("shipping_limit_date",),
        integers=("order_item_id",),
        money=("price", "freight_value"),
        required=("product_id", "seller_id", "price", "freight_value"),
    ),
    "payments": Contract(
        "olist_order_payments_dataset.csv",
        ("order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"),
        key=("order_id", "payment_sequential"),
        integers=("payment_sequential", "payment_installments"),
        money=("payment_value",),
        required=("payment_type", "payment_installments", "payment_value"),
    ),
    "reviews": Contract(
        "olist_order_reviews_dataset.csv",
        (
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ),
        dates=("review_creation_date", "review_answer_timestamp"),
        integers=("review_score",),
        required=(
            "review_id",
            "order_id",
            "review_score",
            "review_creation_date",
            "review_answer_timestamp",
        ),
    ),
    "products": Contract(
        "olist_products_dataset.csv",
        (
            "product_id",
            "product_category_name",
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ),
        key=("product_id",),
        integers=(
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ),
    ),
    "sellers": Contract(
        "olist_sellers_dataset.csv",
        ("seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"),
        key=("seller_id",),
        required=("seller_state",),
    ),
    "translation": Contract(
        "product_category_name_translation.csv",
        ("product_category_name", "product_category_name_english"),
        key=("product_category_name",),
        required=("product_category_name_english",),
    ),
    "geolocation": Contract(
        "olist_geolocation_dataset.csv",
        (
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ),
        required=("geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"),
    ),
}

STATUSES = {
    "created",
    "approved",
    "invoiced",
    "processing",
    "shipped",
    "delivered",
    "unavailable",
    "canceled",
}
STATES = set(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)

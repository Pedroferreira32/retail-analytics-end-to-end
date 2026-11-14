# Data dictionary

Generated from the validated complete Olist run. Monetary `*_cents` fields are integer BRL cents. Timestamps have no inferred timezone. Source column names (including `lenght`) follow Olist.

## `dim_customers`

Grain: One customer_id (order-linked identity; customer_unique_id can repeat). Rows: 99,441.

| Column | Pandas type | Nulls |
| --- | --- | ---: |
| `customer_id` | `string` | 0 |
| `customer_unique_id` | `string` | 0 |
| `customer_zip_code_prefix` | `string` | 0 |
| `customer_city` | `string` | 0 |
| `customer_state` | `string` | 0 |
| `latitude` | `Float64` | 278 |
| `longitude` | `Float64` | 278 |

## `dim_products`

Grain: One product_id. Rows: 32,951.

| Column | Pandas type | Nulls |
| --- | --- | ---: |
| `product_id` | `string` | 0 |
| `product_category_name` | `string` | 0 |
| `product_name_lenght` | `Int64` | 610 |
| `product_description_lenght` | `Int64` | 610 |
| `product_photos_qty` | `Int64` | 610 |
| `product_weight_g` | `Int64` | 2 |
| `product_length_cm` | `Int64` | 2 |
| `product_height_cm` | `Int64` | 2 |
| `product_width_cm` | `Int64` | 2 |
| `product_category_name_english` | `string` | 0 |

## `dim_sellers`

Grain: One seller_id. Rows: 3,095.

| Column | Pandas type | Nulls |
| --- | --- | ---: |
| `seller_id` | `string` | 0 |
| `seller_zip_code_prefix` | `string` | 0 |
| `seller_city` | `string` | 0 |
| `seller_state` | `string` | 0 |
| `latitude` | `Float64` | 7 |
| `longitude` | `Float64` | 7 |

## `dim_date`

Grain: One purchase calendar date. Rows: 774.

| Column | Pandas type | Nulls |
| --- | --- | ---: |
| `date` | `datetime64[ns]` | 0 |
| `date_key` | `Int64` | 0 |
| `year` | `Int64` | 0 |
| `month_number` | `Int64` | 0 |
| `year_month` | `object` | 0 |
| `quarter` | `Int64` | 0 |
| `weekday_number` | `Int64` | 0 |

## `fct_orders`

Grain: One order_id, all statuses. Rows: 99,441.

| Column | Pandas type | Nulls |
| --- | --- | ---: |
| `order_id` | `string` | 0 |
| `customer_id` | `string` | 0 |
| `order_status` | `string` | 0 |
| `order_purchase_timestamp` | `datetime64[ns]` | 0 |
| `order_approved_at` | `datetime64[ns]` | 160 |
| `order_delivered_carrier_date` | `datetime64[ns]` | 1,783 |
| `order_delivered_customer_date` | `datetime64[ns]` | 2,965 |
| `order_estimated_delivery_date` | `datetime64[ns]` | 0 |
| `purchase_date` | `datetime64[ns]` | 0 |
| `purchase_month` | `object` | 0 |
| `date_key` | `Int64` | 0 |
| `is_delivered` | `boolean` | 0 |
| `is_canceled` | `boolean` | 0 |
| `item_count` | `Int64` | 0 |
| `merchandise_value_cents` | `Int64` | 0 |
| `freight_value_cents` | `Int64` | 0 |
| `payment_count` | `Int64` | 0 |
| `payment_value_cents` | `Int64` | 0 |
| `review_id` | `string` | 768 |
| `review_score` | `Int64` | 768 |
| `review_count` | `Int64` | 0 |
| `review_creation_date` | `datetime64[ns]` | 768 |
| `review_answer_timestamp` | `datetime64[ns]` | 768 |
| `order_value_cents` | `Int64` | 0 |
| `payment_difference_cents` | `Int64` | 0 |
| `delivery_days` | `Float64` | 2,971 |
| `delivery_observed` | `boolean` | 0 |
| `is_late` | `boolean` | 2,971 |
| `is_eligible_gmv` | `boolean` | 0 |

## `fct_order_items`

Grain: One (order_id, order_item_id). Rows: 112,650.

| Column | Pandas type | Nulls |
| --- | --- | ---: |
| `order_id` | `string` | 0 |
| `order_item_id` | `Int64` | 0 |
| `product_id` | `string` | 0 |
| `seller_id` | `string` | 0 |
| `shipping_limit_date` | `datetime64[ns]` | 0 |
| `price_cents` | `Int64` | 0 |
| `freight_value_cents` | `Int64` | 0 |
| `customer_id` | `string` | 0 |
| `date_key` | `Int64` | 0 |
| `purchase_date` | `datetime64[ns]` | 0 |
| `purchase_month` | `object` | 0 |
| `order_status` | `string` | 0 |
| `is_eligible_gmv` | `boolean` | 0 |

## `fct_payments`

Grain: One (order_id, payment_sequential). Rows: 103,886.

| Column | Pandas type | Nulls |
| --- | --- | ---: |
| `order_id` | `string` | 0 |
| `payment_sequential` | `Int64` | 0 |
| `payment_type` | `string` | 0 |
| `payment_installments` | `Int64` | 0 |
| `payment_value_cents` | `Int64` | 0 |
| `customer_id` | `string` | 0 |
| `date_key` | `Int64` | 0 |
| `purchase_date` | `datetime64[ns]` | 0 |
| `purchase_month` | `object` | 0 |
| `order_status` | `string` | 0 |
| `is_eligible_gmv` | `boolean` | 0 |

## `mart_monthly_sales`

Grain: One purchase month. Rows: 25.

| Column | Pandas type | Nulls |
| --- | --- | ---: |
| `purchase_month` | `object` | 0 |
| `placed_orders` | `int64` | 0 |
| `delivered_orders` | `Int64` | 0 |
| `canceled_orders` | `Int64` | 0 |
| `gmv_cents` | `Int64` | 0 |
| `freight_cents` | `Int64` | 0 |
| `recorded_payments_cents` | `Int64` | 0 |
| `delivery_observed_orders` | `Int64` | 0 |
| `late_orders` | `Int64` | 0 |
| `avg_delivery_days` | `float64` | 2 |
| `avg_review_score` | `float64` | 2 |
| `reviewed_delivered_orders` | `Int64` | 0 |
| `avg_ticket_cents` | `float64` | 2 |

## `mart_category_sales`

Grain: One purchase month and product category. Rows: 1,273.

| Column | Pandas type | Nulls |
| --- | --- | ---: |
| `purchase_month` | `object` | 0 |
| `product_category_name` | `object` | 0 |
| `product_category_name_english` | `object` | 0 |
| `delivered_orders` | `int64` | 0 |
| `sold_items` | `int64` | 0 |
| `gmv_cents` | `Int64` | 0 |
| `freight_cents` | `Int64` | 0 |

## `mart_state_sales`

Grain: One purchase month and customer state. Rows: 556.

| Column | Pandas type | Nulls |
| --- | --- | ---: |
| `purchase_month` | `object` | 0 |
| `customer_state` | `object` | 0 |
| `delivered_orders` | `int64` | 0 |
| `unique_customers` | `int64` | 0 |
| `gmv_cents` | `Int64` | 0 |
| `freight_cents` | `Int64` | 0 |
| `delivery_observed_orders` | `Int64` | 0 |
| `late_orders` | `Int64` | 0 |
| `avg_delivery_days` | `float64` | 0 |

## `mart_customer_rfm`

Grain: One customer_unique_id with delivered orders. Rows: 93,358.

| Column | Pandas type | Nulls |
| --- | --- | ---: |
| `customer_unique_id` | `object` | 0 |
| `frequency_orders` | `int64` | 0 |
| `monetary_cents` | `Int64` | 0 |
| `first_purchase_date` | `datetime64[ns]` | 0 |
| `last_purchase_date` | `datetime64[ns]` | 0 |
| `recency_days` | `int64` | 0 |


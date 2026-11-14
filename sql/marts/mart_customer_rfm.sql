-- Grain: customer_unique_id. RFM features, not predicted CLV or arbitrary scores.
-- reference_date is supplied by the pipeline: day after the last observed purchase.
SELECT
    c.customer_unique_id,
    COUNT(*) AS frequency_orders,
    SUM(o.merchandise_value_cents) AS monetary_cents,
    MIN(o.purchase_date) AS first_purchase_date,
    MAX(o.purchase_date) AS last_purchase_date,
    {{recency}} AS recency_days
FROM {{ref:fct_orders}} AS o
JOIN {{ref:dim_customers}} AS c ON o.customer_id = c.customer_id
WHERE o.is_eligible_gmv
GROUP BY c.customer_unique_id

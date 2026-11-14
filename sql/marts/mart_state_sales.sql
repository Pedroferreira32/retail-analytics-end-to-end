-- Grain: purchase month and CUSTOMER state, not seller state.
SELECT
    o.purchase_month,
    c.customer_state,
    COUNT(*) AS delivered_orders,
    COUNT(DISTINCT c.customer_unique_id) AS unique_customers,
    SUM(o.merchandise_value_cents) AS gmv_cents,
    SUM(o.freight_value_cents) AS freight_cents,
    SUM(CASE WHEN o.delivery_observed THEN 1 ELSE 0 END) AS delivery_observed_orders,
    SUM(CASE WHEN o.is_late THEN 1 ELSE 0 END) AS late_orders,
    AVG(o.delivery_days) AS avg_delivery_days
FROM {{ref:fct_orders}} AS o
JOIN {{ref:dim_customers}} AS c ON o.customer_id = c.customer_id
WHERE o.is_eligible_gmv
GROUP BY o.purchase_month, c.customer_state

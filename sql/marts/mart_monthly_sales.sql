-- Grain: one purchase month. Amounts are BRL cents, never binary floating currency.
SELECT
    purchase_month,
    COUNT(*) AS placed_orders,
    SUM(CASE WHEN is_eligible_gmv THEN 1 ELSE 0 END) AS delivered_orders,
    SUM(CASE WHEN is_canceled THEN 1 ELSE 0 END) AS canceled_orders,
    SUM(CASE WHEN is_eligible_gmv THEN merchandise_value_cents ELSE 0 END) AS gmv_cents,
    SUM(CASE WHEN is_eligible_gmv THEN freight_value_cents ELSE 0 END) AS freight_cents,
    SUM(payment_value_cents) AS recorded_payments_cents,
    SUM(CASE WHEN delivery_observed THEN 1 ELSE 0 END) AS delivery_observed_orders,
    SUM(CASE WHEN is_late THEN 1 ELSE 0 END) AS late_orders,
    AVG(delivery_days) AS avg_delivery_days,
    AVG(CASE WHEN is_eligible_gmv THEN review_score END) AS avg_review_score,
    SUM(CASE WHEN is_eligible_gmv AND review_score IS NOT NULL THEN 1 ELSE 0 END)
        AS reviewed_delivered_orders,
    SUM(CASE WHEN is_eligible_gmv THEN merchandise_value_cents ELSE 0 END) * 1.0
        / NULLIF(SUM(CASE WHEN is_eligible_gmv THEN 1 ELSE 0 END), 0) AS avg_ticket_cents
FROM {{ref:fct_orders}}
GROUP BY purchase_month
ORDER BY purchase_month

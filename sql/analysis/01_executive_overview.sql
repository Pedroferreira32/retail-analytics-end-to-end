SELECT
    COUNT(*) AS placed_orders,
    SUM(CASE WHEN is_eligible_gmv THEN 1 ELSE 0 END) AS delivered_orders,
    SUM(CASE WHEN is_eligible_gmv THEN merchandise_value_cents ELSE 0 END) / 100.0 AS gmv_brl,
    SUM(CASE WHEN is_eligible_gmv THEN merchandise_value_cents ELSE 0 END) / 100.0
        / NULLIF(SUM(CASE WHEN is_eligible_gmv THEN 1 ELSE 0 END), 0) AS avg_ticket_brl,
    AVG(CASE WHEN is_eligible_gmv THEN review_score END) AS average_review,
    SUM(CASE WHEN is_late THEN 1 ELSE 0 END) * 1.0
        / NULLIF(SUM(CASE WHEN delivery_observed THEN 1 ELSE 0 END), 0) AS late_delivery_rate
FROM fct_orders;

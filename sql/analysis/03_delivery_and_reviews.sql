-- Observational association only: this does not establish a causal effect.
SELECT is_late, COUNT(*) AS observed_deliveries,
    AVG(review_score) AS average_review,
    COUNT(review_score) AS reviewed_orders,
    AVG(delivery_days) AS average_delivery_days
FROM fct_orders
WHERE delivery_observed
GROUP BY is_late;

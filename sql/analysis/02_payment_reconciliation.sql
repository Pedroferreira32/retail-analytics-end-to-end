-- Differences are investigated, never silently forced to match.
SELECT order_status, COUNT(*) AS orders,
    SUM(order_value_cents) AS item_plus_freight_cents,
    SUM(payment_value_cents) AS recorded_payment_cents,
    SUM(payment_difference_cents) AS difference_cents,
    SUM(CASE WHEN ABS(payment_difference_cents) > 1 THEN 1 ELSE 0 END) AS orders_over_one_cent
FROM fct_orders
GROUP BY order_status
ORDER BY orders DESC;

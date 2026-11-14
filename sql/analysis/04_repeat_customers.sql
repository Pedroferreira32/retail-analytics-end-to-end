SELECT frequency_orders, COUNT(*) AS customers, SUM(monetary_cents) / 100.0 AS gmv_brl
FROM mart_customer_rfm
GROUP BY frequency_orders
ORDER BY frequency_orders;

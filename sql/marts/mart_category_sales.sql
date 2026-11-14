-- Grain: purchase month and category. Distinct orders are NOT additive across categories.
SELECT
    i.purchase_month,
    p.product_category_name,
    p.product_category_name_english,
    COUNT(DISTINCT i.order_id) AS delivered_orders,
    COUNT(*) AS sold_items,
    SUM(i.price_cents) AS gmv_cents,
    SUM(i.freight_value_cents) AS freight_cents
FROM {{ref:fct_order_items}} AS i
JOIN {{ref:dim_products}} AS p ON i.product_id = p.product_id
WHERE i.is_eligible_gmv
GROUP BY i.purchase_month, p.product_category_name, p.product_category_name_english

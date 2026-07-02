-- @model: customer_orders
-- @materialization: table
-- @description: One row per customer with lifetime order metrics.
-- @audits: not_null(customer_id), unique(customer_id), row_count_at_least(1)
-- @tags: mart, customer

SELECT
    c.customer_id,
    c.name,
    c.country,
    count(o.order_id)                               AS n_orders,
    coalesce(sum(o.amount) FILTER (WHERE o.status = 'paid'), 0) AS lifetime_value,
    max(o.order_date)                               AS last_order_date
FROM stg_customers c
LEFT JOIN stg_orders o USING (customer_id)
GROUP BY 1, 2, 3

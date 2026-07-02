-- @model: daily_revenue
-- @materialization: incremental
-- @unique_key: order_date
-- @description: Paid revenue per day. Incremental -- merged by order_date, so
--               re-running only rewrites the days that changed.
-- @audits: not_null(order_date), unique(order_date), expression(revenue >= 0)
-- @tags: mart, finance

SELECT
    order_date,
    count(*)        AS n_paid_orders,
    sum(amount)     AS revenue
FROM stg_orders
WHERE status = 'paid'
GROUP BY order_date

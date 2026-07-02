-- @model: stg_orders
-- @materialization: view
-- @description: Cleaned order rows; ephemeral (inlined into downstream models).
-- @audits: not_null(order_id), accepted_values(status, 'new', 'paid', 'cancelled')

SELECT
    order_id,
    customer_id,
    CAST(order_ts AS DATE)      AS order_date,
    lower(status)               AS status,
    CAST(amount AS DOUBLE)      AS amount
FROM raw_orders
WHERE order_id IS NOT NULL

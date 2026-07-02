-- @model: stg_customers
-- @materialization: view
-- @description: Cleaned customer rows; ephemeral.
-- @audits: not_null(customer_id), unique(customer_id)

SELECT
    customer_id,
    trim(name)      AS name,
    lower(country)  AS country
FROM raw_customers
WHERE customer_id IS NOT NULL

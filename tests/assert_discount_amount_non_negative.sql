-- Business rule: discount_amount must never be negative.
-- Returns rows that violate this rule; a passing test returns zero rows.
select *
from {{ ref('stg_orders') }}
where discount_amount < 0

-- Business rule: net_revenue must equal gross_revenue - refund_amount - discount_amount.
-- Tolerance of 0.01 to guard against floating-point drift.
-- Returns rows that violate this rule; a passing test returns zero rows.
select *
from {{ ref('fct_orders') }}
where abs(net_revenue - (gross_revenue - refund_amount - discount_amount)) > 0.01

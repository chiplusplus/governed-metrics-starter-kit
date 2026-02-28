with stg_orders as (
    select * from {{ ref('stg_orders') }}
),

order_items_agg as (
    select
        order_id,
        count(*)          as item_count,
        sum(item_revenue) as gross_revenue
    from {{ ref('fct_order_items') }}
    group by order_id
),

final as (
    select
        o.order_id,
        o.customer_id,
        o.order_date,
        o.status,
        o.discount_amount,
        o.refund_amount,
        oi.item_count,
        round(oi.gross_revenue, 2)                                          as gross_revenue,
        round(oi.gross_revenue - o.refund_amount - o.discount_amount, 2)   as net_revenue
    from stg_orders as o
    left join order_items_agg as oi
        on o.order_id = oi.order_id
)

select * from final

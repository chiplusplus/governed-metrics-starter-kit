with stg_order_items as (
    select * from {{ ref('stg_order_items') }}
),

final as (
    select
        order_item_id,
        order_id,
        product_name,
        quantity,
        unit_price,
        round(quantity * unit_price, 2) as item_revenue
    from stg_order_items
)

select * from final

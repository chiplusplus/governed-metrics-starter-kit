with source as (
    select * from {{ ref('orders') }}
),

renamed as (
    select
        order_id,
        customer_id,
        order_date::date                  as order_date,
        status,
        discount_amount::numeric(10, 2)   as discount_amount,
        refund_amount::numeric(10, 2)     as refund_amount
    from source
)

select * from renamed

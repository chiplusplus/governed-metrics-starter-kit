with stg_customers as (
    select * from {{ ref('stg_customers') }}
),

final as (
    select
        customer_id,
        first_name,
        last_name,
        email,
        country,
        marketing_channel,
        created_at
    from stg_customers
)

select * from final

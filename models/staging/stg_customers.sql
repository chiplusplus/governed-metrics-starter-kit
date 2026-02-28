with source as (
    select * from {{ ref('customers') }}
),

renamed as (
    select
        customer_id,
        first_name,
        last_name,
        email,
        country,
        marketing_channel,
        created_at::date as created_at
    from source
)

select * from renamed

with raw_source as (

    select * 
    from read_parquet('../data/aws_ec2_pricing.parquet')
),

renamed_and_cleaned as (

    select
        -- Identifiers & Keys
        sku,
        try_cast(offer_term_code as varchar) as offer_term_code,
        try_cast(rate_code as varchar) as rate_code,
        
        -- Instance Attributes
        lower(trim(instance_type)) as instance_type,
        lower(trim(instance_family)) as instance_family,
        lower(trim(processor_vendor)) as processor_vendor,
        try_cast(v_cpu as integer) as vcpu,
        try_cast(hardware_generation as integer) as hardware_generation,
        
        -- Extract numeric memory in GB (e.g., '16 GiB' -> 16.0)
        try_cast(regexp_extract(memory, '([0-9\.]+)', 1) as double) as memory_gb,
        
        -- OS & Tenancy
        lower(trim(operating_system)) as operating_system,
        lower(trim(tenancy)) as tenancy,
        lower(trim(usage_type)) as usage_type,
        
        -- Location / Region
        trim(location) as location_name,
        lower(trim(region_code)) as region_code,

        -- Pricing & Unit Mechanics
        try_cast(price_per_unit as double) as price_per_unit,
        trim(price_description) as price_description,
        lower(trim(unit)) as pricing_unit,
        coalesce(try_cast(left(lease_contract_length, 1) as integer), 0) as lease_year, 
        
        case
            when trim(term_type) = 'OnDemand' then 'on demand'
            else lower(trim(purchase_option))
        end as purchase_option,

        lower(trim(pre_installed_sw)) as pre_installed_sw,
        currency,
        concat(sku, '_', offer_term_code) as sku_offerterm,
        lower(trim(license_model)) as license_model,
        
        -- transform upfront fee in hourly rate
        case 
            when unit = 'Quantity' and coalesce(try_cast(left(lease_contract_length, 1) as integer), 0) > 0
                then price_per_unit / (coalesce(try_cast(left(lease_contract_length, 1) as integer), 0) * 365 * 24)
            when unit = 'Hrs' 
                then price_per_unit
            else 0
        end as price_per_hour,

        -- Metadata Flags
        trim(term_type) as term_type,
        trim(capacity_status) as capacity_status,
        
        -- Timestamps / Partition metadata if present
        current_timestamp as loaded_at

    from raw_source

),

filtered as (

    select *
    from renamed_and_cleaned
    where
        -- Exclude non-compute rows or rows missing crucial pricing
        price_per_unit is not null
        and price_per_unit > 0
        and instance_type is not null

)

select * from filtered
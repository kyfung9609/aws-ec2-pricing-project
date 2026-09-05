with staging as (
    -- Sourced from int_price_outliers, which is 1:1 with stg_aws_ec2_pricing
    -- plus an is_price_outlier flag. Excludes rows whose price disagrees with
    -- their peer group by >3x (first found via p5.4xlarge us-east-1 Windows
    -- OnDemand -- a $0.70/hr row next to the correct $7/hr row).
    select *
    from {{ ref('int_price_outliers') }}
    where not is_price_outlier
),

dim_instances as (
    select * 
    from {{ ref('dim_instances') }}
),

dim_locations as (
    select * 
    from {{ ref('dim_locations') }}
),

joined_facts as (
    select
        -- Primary Key for Fact Record
        sku_offerterm,
        
        -- Foreign Keys to Dimensions
        i.instance_sk, 
        loc.region_code,
        loc.location_sk, 

        -- Degenerate Attributes / Fact Filters
        s.sku,
        s.offer_term_code,
        s.tenancy,
        s.usage_type,
        s.currency,
        s.instance_type,

        -- Price factor
        s.term_type,
        max(s.lease_year) as lease_year, 
        s.purchase_option, 
        s.capacity_status,
        s.pre_installed_sw,
        s.operating_system,
        s.license_model, 

        -- Measures / Metrics
        sum(s.price_per_hour) as price_per_hour,
        sum(case when s.pricing_unit = 'hrs' then s.price_per_hour else 0 end) as hourly_recurring_fee,
        sum(case when s.pricing_unit = 'quantity' then s.price_per_hour else 0 end) as hourly_upfront_fee,
        sum(case when s.pricing_unit = 'quantity' then s.price_per_unit else 0 end) as total_upfront_fee,

        -- Audit Timestamps
        s.loaded_at

    from staging s
    left join dim_instances i
        on s.instance_type = i.instance_type
    left join dim_locations loc
        on md5(lower(trim(coalesce(s.region_code, s.location_name)))) = loc.location_sk
    group by all
)

select * 
from joined_facts

with staging as (

    select
        instance_type,
        instance_family,
        vcpu,
        memory_gb, 
        processor_vendor, 
        hardware_generation, 
        lower(regexp_extract(instance_type, '^([a-z0-9-]+?)[0-9]+', 1)) as family_code,
        regexp_extract(split_part(instance_type, '.', 1), '[0-9]+([a-z]+)$', 1) as feature_suffix
    from {{ ref('stg_aws_ec2_pricing') }}
    where instance_type is not null

),

deduplicated_instances as (

    select
        -- Primary Key
        md5(instance_type) as instance_sk,
        
        -- Instance Attributes
        instance_type,
        instance_family,
        vcpu,
        memory_gb,
        processor_vendor,
        hardware_generation,
        
        -- Derived Hardware Ratios & Metrics
        case 
            when vcpu > 0 then round(memory_gb / vcpu, 2)
            else null
        end as memory_to_vcpu_ratio,

        -- Hardware Category Classification
        case
            when memory_gb / nullif(vcpu, 0) >= 8 then 'Memory Optimized'
            when memory_gb / nullif(vcpu, 0) <= 2 then 'Compute Optimized'
            else 'General Purpose'
        end as instance_category,

        case 
        when instance_type like 'a1%' 
            or regexp_matches(instance_family, '^[a-z]+[0-9]+g')
            then 'aws graviton'
        when regexp_matches(instance_family, '^[a-z]+[0-9]+a')
            then 'amd'
        else processor_vendor
        end as revised_processor_vendor,

        -- Instance Family Category
        case 
            when instance_type like 'a1%'
                or family_code in ('m', 't')
            then 'General Purpose'

            when family_code  in ('c', 'hpc', 'cc') then 'Compute Optimized'

            when family_code in ('r', 'x', 'z', 'cr', 'u') 
                or family_code like 'u-%' 
                or family_code like 'u1%' 
            then 'Memory Optimized'

            when family_code in ('i', 'd', 'h', 'im', 'is', 'hs') then 'Storage Optimized'

            when family_code in ('f', 'g', 'p', 'dl', 'vt', 'inf', 'trn')
                or family_code like 'gr%'
            then 'Accelerated Computing'
        else 'Other / Special'
        end as instance_family_category, 
        

        -- Concatenates vendor and instance_type for clean display in Power BI
        concat(revised_processor_vendor, ' - ', instance_type) as vendor_instance_type

    from staging
    -- Group by attributes to collapse duplicates across regions, OS, and pricing terms
    group by all

)

select * 
from deduplicated_instances
order by instance_family, instance_type
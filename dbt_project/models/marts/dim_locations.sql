with aws_loc as (

    select distinct
        location_name,
        coalesce(region_code, lower(replace(location_name, ' ', '-'))) as region_code,
    from {{ ref('stg_aws_ec2_pricing') }}
    where location_name is not null
       or region_code is not null

)

select 
    md5(lower(trim(coalesce(region_code, location_name)))) as location_sk,
    location_name, 
    region_code,
    case 
        when location_name like '%Canada%' then 'Canada'
        when location_name like '%US%' then 'US'
        else 'Others'
    end as 'country' 
from aws_loc
-- Flags rows whose price_per_hour is a statistical outlier within its natural
-- pricing group (same instance_type, region, OS, tenancy, capacity_status,
-- term_type, purchase_option, lease_year, pre_installed_sw, license_model) --
-- i.e. rows that claim to be the "same spec" offer but disagree wildly on price
-- (e.g. the p5.4xlarge $7/hr vs $0.70/hr duplicate found in us-east-1).
--
-- REVIEW-FIRST, FILTER-LATER: this model does NOT drop anything yet. It carries
-- every staging row through unchanged, plus three new columns so the outliers
-- can be reviewed (see data_exports/price_outlier_review.csv after a run)
-- before any filtering logic gets written into fct_ec2_pricing.
--
-- Threshold is a dbt var so it can be tuned without editing this file:
--   dbt run --vars '{price_outlier_ratio: 3}'
-- Default is 3x: a row is flagged if its price is more than 3x its group's
-- median price, or less than 1/3 of it.

with staging as (

    select *
    from {{ ref('stg_aws_ec2_pricing') }}

),

flagged as (

    select
        *,
        median(price_per_hour) over (
            partition by
                instance_type, region_code, operating_system, tenancy,
                capacity_status, term_type, purchase_option, lease_year,
                pre_installed_sw, license_model
        ) as price_outlier_group_median,

        count(*) over (
            partition by
                instance_type, region_code, operating_system, tenancy,
                capacity_status, term_type, purchase_option, lease_year,
                pre_installed_sw, license_model
        ) as price_outlier_group_size

    from staging

),

scored as (

    select
        *,
        round(
            price_per_hour / nullif(price_outlier_group_median, 0), 4
        ) as price_outlier_ratio,

        -- Only flag groups with more than one row: a lone row has no peer to
        -- compare against, so it can't be an outlier by this definition.
        case
            when price_outlier_group_size > 1
                and (
                    price_per_hour > price_outlier_group_median * {{ var('price_outlier_ratio', 3) }}
                    or price_per_hour < price_outlier_group_median / {{ var('price_outlier_ratio', 3) }}
                )
            then true
            else false
        end as is_price_outlier

    from flagged

)

select * from scored

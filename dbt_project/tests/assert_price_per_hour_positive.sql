-- Fails if any row in fct_ec2_pricing has a non-positive hourly price.
-- Guards the pipeline's own filter assumption (PricePerUnit > 0 applied at
-- ingestion) at the mart layer too, rather than trusting the upstream step blindly.

select *
from {{ ref('fct_ec2_pricing') }}
where price_per_hour <= 0

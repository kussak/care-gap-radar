select
    Id                  as payer_id,
    NAME                as payer_name,
    lower(OWNERSHIP)    as ownership
from {{ source('synthea', 'payers') }}

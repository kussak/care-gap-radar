select
    PATIENT                                             as patient_id,
    ENCOUNTER                                           as encounter_id,
    strptime(DATE, '%Y-%m-%dT%H:%M:%SZ')                as observed_at,  -- UTC
    cast(strptime(DATE, '%Y-%m-%dT%H:%M:%SZ') as date)  as observation_date,
    lower(CATEGORY)                                     as category,
    CODE                                                as loinc_code,
    DESCRIPTION                                         as observation_description,
    VALUE                                               as value_text,
    case when TYPE = 'numeric' then try_cast(VALUE as double) end as value_numeric,
    UNITS                                               as units,
    lower(TYPE)                                         as value_type
from {{ source('synthea', 'observations') }}

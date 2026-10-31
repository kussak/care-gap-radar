select
    PATIENT                    as patient_id,
    ENCOUNTER                  as encounter_id,
    cast(START as date)        as start_date,
    cast(STOP as date)         as stop_date,  -- null while unresolved
    lower(SYSTEM)              as code_system,
    CODE                       as condition_code,
    DESCRIPTION                as condition_description
from {{ source('synthea', 'conditions') }}

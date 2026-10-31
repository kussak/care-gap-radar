select
    PATIENT                                             as patient_id,
    ENCOUNTER                                           as encounter_id,
    PAYER                                               as payer_id,
    strptime(START, '%Y-%m-%dT%H:%M:%SZ')               as started_at,  -- UTC
    strptime(STOP, '%Y-%m-%dT%H:%M:%SZ')                as stopped_at,  -- UTC, null while ongoing
    cast(strptime(START, '%Y-%m-%dT%H:%M:%SZ') as date) as start_date,
    cast(strptime(STOP, '%Y-%m-%dT%H:%M:%SZ') as date)  as stop_date,
    CODE                                                as rxnorm_code,
    DESCRIPTION                                         as medication_description,
    cast(BASE_COST as decimal(12, 2))                   as base_cost,
    cast(PAYER_COVERAGE as decimal(12, 2))              as payer_coverage,
    cast(DISPENSES as integer)                          as dispenses,
    cast(TOTALCOST as decimal(14, 2))                   as total_cost,
    REASONCODE                                          as reason_code,
    REASONDESCRIPTION                                   as reason_description
from {{ source('synthea', 'medications') }}

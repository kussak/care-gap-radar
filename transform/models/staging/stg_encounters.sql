select
    Id                                              as encounter_id,
    PATIENT                                         as patient_id,
    strptime(START, '%Y-%m-%dT%H:%M:%SZ')           as started_at,  -- UTC
    strptime(STOP, '%Y-%m-%dT%H:%M:%SZ')            as stopped_at,  -- UTC
    cast(strptime(START, '%Y-%m-%dT%H:%M:%SZ') as date) as encounter_date,
    ORGANIZATION                                    as organization_id,
    PROVIDER                                        as provider_id,
    PAYER                                           as payer_id,
    lower(ENCOUNTERCLASS)                           as encounter_class,
    CODE                                            as encounter_code,
    DESCRIPTION                                     as encounter_description,
    cast(BASE_ENCOUNTER_COST as decimal(12, 2))     as base_encounter_cost,
    cast(TOTAL_CLAIM_COST as decimal(12, 2))        as total_claim_cost,
    cast(PAYER_COVERAGE as decimal(12, 2))          as payer_coverage,
    REASONCODE                                      as reason_code,
    REASONDESCRIPTION                               as reason_description
from {{ source('synthea', 'encounters') }}

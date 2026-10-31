select
    Id                         as patient_id,
    cast(BIRTHDATE as date)    as birth_date,
    cast(DEATHDATE as date)    as death_date,
    FIRST                      as first_name,  -- UI only, never sent to the LLM
    LAST                       as last_name,   -- UI only, never sent to the LLM
    lower(GENDER)              as sex,
    lower(RACE)                as race,
    lower(ETHNICITY)           as ethnicity,
    CITY                       as city,
    STATE                      as state
from {{ source('synthea', 'patients') }}

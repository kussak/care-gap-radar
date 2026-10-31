-- Fails if any feature row draws on data dated on or after its index date, from any source:
-- encounters, conditions, medications, or the observations behind care-gap evidence.
select
    patient_id,
    index_name,
    index_date,
    last_encounter_date,
    last_condition_start_date,
    last_med_start_date,
    last_gap_evidence_date
from {{ ref('int_patient_features') }}
where last_encounter_date >= index_date
   or last_condition_start_date >= index_date
   or last_med_start_date >= index_date
   or last_gap_evidence_date >= index_date

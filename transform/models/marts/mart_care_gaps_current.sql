select
    patient_id,
    index_date,
    gap_code,
    gap_description,
    evidence,
    last_relevant_date
from {{ ref('int_care_gaps') }}
where index_name = 'current'

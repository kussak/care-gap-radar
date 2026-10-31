-- Features at the current index date plus display fields. first_name / last_name / display_name
-- are for the UI only and must never be sent to the LLM.
select
    f.* exclude (index_name),
    p.first_name,
    p.last_name,
    p.first_name || ' ' || p.last_name as display_name,
    p.race,
    p.ethnicity,
    coalesce(g.open_gap_codes, []) as open_gap_codes
from {{ ref('int_patient_features') }} f
join {{ ref('stg_patients') }} p using (patient_id)
left join (
    select patient_id, list(gap_code order by gap_code) as open_gap_codes
    from {{ ref('int_care_gaps') }}
    where index_name = 'current'
    group by 1
) g using (patient_id)
where f.index_name = 'current'

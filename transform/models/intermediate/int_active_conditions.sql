-- Patient x index date x condition group, for diagnoses active at the index date:
-- start < index_date and (stop is null or stop >= index_date).
-- Codes flagged requires_confirmation (diabetes complications) only count when the patient also
-- has a diabetes medication or a diagnostic HbA1c (>= 6.5%) before the index date. Any A1c is not
-- enough: a normal result is evidence against diabetes.
with confirmed_diabetes as (
    select distinct pop.patient_id, pop.index_name
    from {{ ref('int_population') }} pop
    join {{ ref('stg_observations') }} o
        on o.patient_id = pop.patient_id
       and o.loinc_code = '4548-4'
       and o.value_numeric >= 6.5
       and o.observation_date < pop.index_date
    union
    select distinct pop.patient_id, pop.index_name
    from {{ ref('int_population') }} pop
    join {{ ref('stg_medications') }} m
        on m.patient_id = pop.patient_id
       and m.start_date < pop.index_date
    join {{ ref('diabetes_medication_codes') }} d
        on d.rxnorm_code = m.rxnorm_code
)

select
    pop.patient_id,
    pop.index_name,
    pop.index_date,
    s.condition_group,
    min(c.start_date) as first_start_date,
    max(c.start_date) as last_start_date
from {{ ref('int_population') }} pop
join {{ ref('stg_conditions') }} c
    on c.patient_id = pop.patient_id
   and c.start_date < pop.index_date
   and (c.stop_date is null or c.stop_date >= pop.index_date)
join {{ ref('chronic_condition_codes') }} s
    on s.snomed_code = c.condition_code
left join confirmed_diabetes cd
    on cd.patient_id = pop.patient_id
   and cd.index_name = pop.index_name
where not s.requires_confirmation
   or cd.patient_id is not null
group by all

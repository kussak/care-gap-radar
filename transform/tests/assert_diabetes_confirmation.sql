-- Fails if a patient counts as diabetic only through complication codes (requires_confirmation)
-- without a diabetes medication or a diagnostic HbA1c (>= 6.5%) before the index date.
with dm as (
    select ac.patient_id, ac.index_name, ac.index_date
    from {{ ref('int_active_conditions') }} ac
    where ac.condition_group = 'diabetes'
),

core as (
    select distinct pop.patient_id, pop.index_name
    from {{ ref('int_population') }} pop
    join {{ ref('stg_conditions') }} c
        on c.patient_id = pop.patient_id
       and c.start_date < pop.index_date
       and (c.stop_date is null or c.stop_date >= pop.index_date)
    join {{ ref('chronic_condition_codes') }} s
        on s.snomed_code = c.condition_code
       and s.condition_group = 'diabetes'
       and not s.requires_confirmation
)

select dm.*
from dm
left join core using (patient_id, index_name)
where core.patient_id is null
  and not exists (
      select 1 from {{ ref('stg_medications') }} m
      join {{ ref('diabetes_medication_codes') }} d on d.rxnorm_code = m.rxnorm_code
      where m.patient_id = dm.patient_id and m.start_date < dm.index_date
  )
  and not exists (
      select 1 from {{ ref('stg_observations') }} o
      where o.patient_id = dm.patient_id and o.loinc_code = '4548-4'
        and o.value_numeric >= 6.5 and o.observation_date < dm.index_date
  )

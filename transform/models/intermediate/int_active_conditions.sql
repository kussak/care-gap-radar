-- Patient x index date x condition group, for diagnoses active at the index date:
-- start < index_date and (stop is null or stop >= index_date).
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
group by all

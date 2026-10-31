-- Patient x index date (train/test only). label_ed_6m = 1 if any ED encounter in (index_date, index_date + 6 months].
select
    pop.patient_id,
    pop.index_name,
    pop.index_date,
    coalesce(max(
        e.encounter_class = 'emergency'
        and e.encounter_date > pop.index_date
        and e.encounter_date <= pop.index_date + interval 6 month
    ), false)::int as label_ed_6m
from {{ ref('int_population') }} pop
left join {{ ref('stg_encounters') }} e
    on e.patient_id = pop.patient_id
   and e.encounter_date > pop.index_date
   and e.encounter_date <= pop.index_date + interval 6 month
where pop.index_name in ('train', 'test')
group by all

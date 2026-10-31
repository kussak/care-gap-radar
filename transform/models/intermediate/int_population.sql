-- Patient x index date. Included if alive on the index date, aged 18-99 on that date, and seen at
-- least once in the prior 24 months. A simple stand-in for attribution to an adult care-management
-- program; the age bounds drop pediatrics (the gaps are adult measures) and Synthea's implausibly
-- many centenarians.
with candidates as (
    select
        p.patient_id,
        i.index_name,
        i.index_date,
        floor(datediff('day', p.birth_date, i.index_date) / 365.25)::int as age_years
    from {{ ref('stg_patients') }} p
    cross join {{ ref('int_index_dates') }} i
    where p.birth_date < i.index_date
      and (p.death_date is null or p.death_date > i.index_date)
)

select distinct
    c.patient_id,
    c.index_name,
    c.index_date,
    c.age_years
from candidates c
join {{ ref('stg_encounters') }} e
    on e.patient_id = c.patient_id
   and e.encounter_date < c.index_date
   and e.encounter_date >= c.index_date - interval 24 month
where c.age_years between 18 and 99

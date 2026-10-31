-- Patient x index date. Included if alive on the index date and seen at least once in the prior
-- 24 months. A simple stand-in for attribution.
select distinct
    p.patient_id,
    i.index_name,
    i.index_date
from {{ ref('stg_patients') }} p
cross join {{ ref('int_index_dates') }} i
join {{ ref('stg_encounters') }} e
    on e.patient_id = p.patient_id
   and e.encounter_date < i.index_date
   and e.encounter_date >= i.index_date - interval 24 month
where p.birth_date < i.index_date
  and (p.death_date is null or p.death_date > i.index_date)

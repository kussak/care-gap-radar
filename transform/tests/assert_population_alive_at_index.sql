-- Fails if a patient is in the population at an index date on or after their death date.
select pop.patient_id, pop.index_name, pop.index_date, p.death_date
from {{ ref('int_population') }} pop
join {{ ref('stg_patients') }} p using (patient_id)
where p.death_date <= pop.index_date

-- Fails if anyone outside the 18-99 program age range made it into the population or features.
select patient_id, index_name, age_years
from {{ ref('int_patient_features') }}
where age_years not between 18 and 99

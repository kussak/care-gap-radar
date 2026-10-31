-- One row: the current population at a glance.
select
    max(index_date)                                         as data_as_of,
    count(*)                                                as patient_count,
    sum(gap_dm_a1c)::bigint                                 as gap_dm_a1c_count,
    sum(gap_htn_bp)::bigint                                 as gap_htn_bp_count,
    count(*) filter (where len(open_gap_codes) > 0)         as patients_with_open_gaps,
    count(*) filter (where payer_category = 'medicaid')     as payer_medicaid,
    count(*) filter (where payer_category = 'medicare')     as payer_medicare,
    count(*) filter (where payer_category = 'private')      as payer_private,
    count(*) filter (where payer_category = 'none_other')   as payer_none_other,
    sum(ed_visits_12m)::bigint                              as ed_visits_12m,
    sum(inpatient_visits_12m)::bigint                       as inpatient_visits_12m,
    sum(urgent_care_visits_12m)::bigint                     as urgent_care_visits_12m,
    sum(outpatient_visits_12m)::bigint                      as outpatient_visits_12m,
    sum(total_claim_cost_12m)                               as total_claim_cost_12m
from {{ ref('mart_patient_current') }}

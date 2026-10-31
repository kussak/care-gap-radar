-- Patient x index date. Every feature uses only data strictly before index_date; lookback is
-- 12 months unless the column name says otherwise. The last_*_date columns are audit columns for
-- the leakage test, not model features.
with pop as (
    select pop.*, p.sex
    from {{ ref('int_population') }} pop
    join {{ ref('stg_patients') }} p using (patient_id)
),

enc as (
    select
        pop.patient_id,
        pop.index_name,
        e.encounter_date,
        e.started_at,
        e.encounter_class,
        e.total_claim_cost,
        e.payer_id,
        e.encounter_date >= pop.index_date - interval 12 month as in_12m
    from pop
    join {{ ref('stg_encounters') }} e
        on e.patient_id = pop.patient_id
       and e.encounter_date < pop.index_date
       and e.encounter_date >= pop.index_date - interval 24 month
),

utilization as (
    select
        patient_id,
        index_name,
        count(*) filter (where in_12m and encounter_class = 'emergency')                            as ed_visits_12m,
        count(*) filter (where in_12m and encounter_class = 'inpatient')                            as inpatient_visits_12m,
        count(*) filter (where in_12m and encounter_class = 'urgentcare')                           as urgent_care_visits_12m,
        count(*) filter (where in_12m and encounter_class in ('ambulatory', 'wellness', 'outpatient')) as outpatient_visits_12m,
        count(*) filter (where encounter_class = 'emergency')                                       as ed_visits_24m,
        coalesce(sum(total_claim_cost) filter (where in_12m), 0)                                    as total_claim_cost_12m,
        max(encounter_date)                                                                         as last_encounter_date,
        arg_max(payer_id, started_at)                                                               as last_payer_id
    from enc
    group by all
),

payer as (
    select
        payer_id,
        case
            when payer_name = 'Medicaid' then 'medicaid'
            when payer_name in ('Medicare', 'Dual Eligible') then 'medicare'
            when ownership = 'private' then 'private'
            else 'none_other'
        end as payer_category
    from {{ ref('stg_payers') }}
),

conditions as (
    select
        patient_id,
        index_name,
        max(condition_group = 'diabetes')::int     as has_diabetes,
        max(condition_group = 'hypertension')::int as has_hypertension,
        max(condition_group = 'chf')::int          as has_chf,
        max(condition_group = 'copd')::int         as has_copd,
        max(condition_group = 'asthma')::int       as has_asthma,
        max(condition_group = 'ckd')::int          as has_ckd,
        max(condition_group = 'depression')::int   as has_depression,
        max(condition_group = 'obesity')::int      as has_obesity,
        max(last_start_date)                       as last_condition_start_date
    from {{ ref('int_active_conditions') }}
    group by all
),

meds as (
    select
        pop.patient_id,
        pop.index_name,
        count(distinct m.rxnorm_code) as active_med_count,
        max(m.start_date)             as last_med_start_date
    from pop
    join {{ ref('stg_medications') }} m
        on m.patient_id = pop.patient_id
       and m.start_date < pop.index_date
       and (m.stop_date is null or m.stop_date >= pop.index_date)
    group by all
),

gaps as (
    select
        patient_id,
        index_name,
        max(gap_code = 'DM_A1C')::int as gap_dm_a1c,
        max(gap_code = 'HTN_BP')::int as gap_htn_bp,
        max(last_relevant_date)       as last_gap_evidence_date
    from {{ ref('int_care_gaps') }}
    group by all
)

select
    pop.patient_id,
    pop.index_name,
    pop.index_date,
    pop.age_years,
    pop.sex,
    payer.payer_category,
    u.ed_visits_12m,
    u.inpatient_visits_12m,
    u.urgent_care_visits_12m,
    u.outpatient_visits_12m,
    u.ed_visits_24m,
    u.total_claim_cost_12m,
    datediff('day', u.last_encounter_date, pop.index_date)                as days_since_last_encounter,
    coalesce(c.has_diabetes, 0)     as has_diabetes,
    coalesce(c.has_hypertension, 0) as has_hypertension,
    coalesce(c.has_chf, 0)          as has_chf,
    coalesce(c.has_copd, 0)         as has_copd,
    coalesce(c.has_asthma, 0)       as has_asthma,
    coalesce(c.has_ckd, 0)          as has_ckd,
    coalesce(c.has_depression, 0)   as has_depression,
    coalesce(c.has_obesity, 0)      as has_obesity,
    coalesce(m.active_med_count, 0) as active_med_count,
    coalesce(g.gap_dm_a1c, 0)       as gap_dm_a1c,
    coalesce(g.gap_htn_bp, 0)       as gap_htn_bp,
    -- audit columns for the leakage test
    u.last_encounter_date,
    c.last_condition_start_date,
    m.last_med_start_date,
    g.last_gap_evidence_date
from pop
join utilization u using (patient_id, index_name)
join payer on payer.payer_id = u.last_payer_id
left join conditions c using (patient_id, index_name)
left join meds m using (patient_id, index_name)
left join gaps g using (patient_id, index_name)

-- Patient x index date x gap; one row per OPEN gap. Uses only observations strictly before index_date.
with a1c as (
    select
        pop.patient_id,
        pop.index_name,
        max(o.observation_date) as last_a1c_date,
        arg_max(o.value_numeric, o.observed_at) as last_a1c_value
    from {{ ref('int_population') }} pop
    join {{ ref('stg_observations') }} o
        on o.patient_id = pop.patient_id
       and o.loinc_code = '4548-4'
       and o.observation_date < pop.index_date
    group by all
),

systolic as (
    select
        pop.patient_id,
        pop.index_name,
        o.observed_at,
        o.observation_date,
        o.value_numeric as systolic,
        row_number() over (
            partition by pop.patient_id, pop.index_name order by o.observed_at desc
        ) as rn
    from {{ ref('int_population') }} pop
    join {{ ref('stg_observations') }} o
        on o.patient_id = pop.patient_id
       and o.loinc_code = '8480-6'
       and o.observation_date < pop.index_date
),

last_bp as (
    select
        s.patient_id,
        s.index_name,
        s.observation_date as last_bp_date,
        s.systolic,
        d.value_numeric as diastolic
    from systolic s
    left join {{ ref('stg_observations') }} d
        on d.patient_id = s.patient_id
       and d.observed_at = s.observed_at  -- systolic/diastolic pairs share a timestamp
       and d.loinc_code = '8462-4'
    where s.rn = 1
),

dm_a1c as (
    select
        dm.patient_id,
        dm.index_name,
        dm.index_date,
        'DM_A1C' as gap_code,
        'Diabetes: no HbA1c test in the past 12 months' as gap_description,
        case
            when a.last_a1c_date is null then 'no A1c on record'
            else 'last A1c ' || strftime(a.last_a1c_date, '%Y-%m-%d')
                 || ' (' || round(a.last_a1c_value, 1) || '%)'
        end as evidence,
        a.last_a1c_date as last_relevant_date
    from {{ ref('int_active_conditions') }} dm
    left join a1c a using (patient_id, index_name)
    where dm.condition_group = 'diabetes'
      and (a.last_a1c_date is null or a.last_a1c_date < dm.index_date - interval 12 month)
),

htn_bp as (
    select
        htn.patient_id,
        htn.index_name,
        htn.index_date,
        'HTN_BP' as gap_code,
        'Hypertension: blood pressure uncontrolled (systolic >= 140) or not measured in the past 12 months'
            as gap_description,
        case
            when b.last_bp_date is null then 'no BP on record'
            when b.last_bp_date < htn.index_date - interval 12 month
                then 'no BP in past 12 months (last ' || strftime(b.last_bp_date, '%Y-%m-%d') || ')'
            else 'last BP ' || cast(round(b.systolic) as integer) || '/'
                 || coalesce(cast(round(b.diastolic) as integer)::varchar, '?')
                 || ' on ' || strftime(b.last_bp_date, '%Y-%m-%d')
        end as evidence,
        b.last_bp_date as last_relevant_date
    from {{ ref('int_active_conditions') }} htn
    left join last_bp b using (patient_id, index_name)
    where htn.condition_group = 'hypertension'
      and (
          b.last_bp_date is null
          or b.last_bp_date < htn.index_date - interval 12 month
          or b.systolic >= 140
      )
)

select * from dm_a1c
union all
select * from htn_bp

-- One row per index date. current = date of the latest encounter in the data.
with current_date_ as (
    select max(encounter_date) as index_date from {{ ref('stg_encounters') }}
)

select 'current' as index_name, index_date from current_date_
union all
select 'test', cast(index_date - interval 6 month as date) from current_date_
union all
select 'train', cast(index_date - interval 12 month as date) from current_date_

-- One row per index date. current = date of the latest encounter in the data.
-- Labeled snapshots step back in 6-month windows, so their 6-month label windows never overlap:
-- test (-6 mo) is scored once, valid (-12 mo) picks the model type, train_* (-18 to -36 mo) fit it.
with current_date_ as (
    select max(encounter_date) as index_date from {{ ref('stg_encounters') }}
)

select 'current' as index_name, index_date from current_date_
union all
select 'test', cast(index_date - interval 6 month as date) from current_date_
union all
select 'valid', cast(index_date - interval 12 month as date) from current_date_
union all
select 'train_' || m || 'm', cast(index_date - to_months(m) as date)
from current_date_, unnest([18, 24, 30, 36]) as t(m)

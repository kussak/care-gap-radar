"""The test fixture must match the real dbt marts, or the API tests prove nothing."""

import duckdb
import pytest

from api.db import ROOT
from tests.conftest import PATIENT_COLUMNS

REAL_WAREHOUSE = ROOT / "data" / "warehouse.duckdb"


@pytest.mark.skipif(not REAL_WAREHOUSE.exists(), reason="run `make dbt` to build the warehouse")
def test_fixture_columns_exist_in_real_mart():
    with duckdb.connect(str(REAL_WAREHOUSE), read_only=True) as con:
        real = {
            name: dtype.lower()
            for name, dtype in con.execute(
                "select column_name, data_type from information_schema.columns "
                "where table_schema = 'marts' and table_name = 'mart_patient_current'"
            ).fetchall()
        }
    missing = set(PATIENT_COLUMNS) - set(real)
    assert not missing, f"fixture columns not in real mart: {missing}"
    mismatched = {c: (t, real[c]) for c, t in PATIENT_COLUMNS.items() if real[c] != t}
    assert not mismatched, f"type drift (fixture, real): {mismatched}"

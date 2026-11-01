"""API contracts against the fixture warehouse."""


def test_health(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "data_as_of": "2026-10-30", "model_version": "gbm-test"}


def test_summary_includes_gaps_payers_and_model_card(client):
    body = client.get("/api/summary").json()
    assert body["patient_count"] == 3
    assert body["gap_counts"] == {"DM_A1C": 1, "HTN_BP": 2}
    assert body["payer_mix"] == {"medicaid": 1, "medicare": 1, "private": 1, "none_other": 0}
    assert body["model"]["model"]["auroc"] == 0.56
    assert body["model"]["baseline_prior_ed"]["auroc"] == 0.54
    assert body["model"]["beats_baseline"] is False


def test_worklist_default_sort_puts_open_gaps_first(client):
    body = client.get("/api/patients").json()
    assert body["total"] == 3
    assert [p["patient_id"] for p in body["items"]] == ["aaaa-1111", "cccc-3333", "bbbb-2222"]
    first = body["items"][0]
    assert first["display_name"] == "Testy123 Patient456"
    assert first["open_gap_codes"] == ["DM_A1C", "HTN_BP"]
    assert first["risk_percentile"] == 97.5


def test_worklist_sort_by_risk_only(client):
    body = client.get("/api/patients?sort=risk").json()
    assert [p["patient_id"] for p in body["items"]] == ["aaaa-1111", "bbbb-2222", "cccc-3333"]
    assert client.get("/api/patients?sort=nope").status_code == 422


def test_worklist_filters_and_pagination(client):
    assert {p["patient_id"] for p in client.get("/api/patients?gap=HTN_BP").json()["items"]} == {
        "aaaa-1111", "cccc-3333"}
    assert [p["patient_id"] for p in client.get("/api/patients?min_risk=90").json()["items"]] == [
        "aaaa-1111"]
    page = client.get("/api/patients?limit=1&offset=1").json()
    assert page["total"] == 3 and [p["patient_id"] for p in page["items"]] == ["cccc-3333"]


def test_worklist_rejects_unknown_gap(client):
    assert client.get("/api/patients?gap=NOPE").status_code == 422


def test_patient_detail(client):
    body = client.get("/api/patients/aaaa-1111").json()
    assert body["conditions"] == ["Diabetes", "Hypertension"]
    assert [g["gap_code"] for g in body["open_gaps"]] == ["DM_A1C", "HTN_BP"]
    assert body["open_gaps"][0]["evidence"] == "last A1c 2025-03-14 (7.2%)"
    assert body["risk"]["percentile"] == 97.5
    assert body["risk"]["top_drivers"][0]["direction"] == "up"
    assert body["utilization"]["ed_visits_12m"] == 2


def test_unknown_patient_404(client):
    assert client.get("/api/patients/does-not-exist").status_code == 404
    assert client.post("/api/patients/does-not-exist/brief").status_code == 404

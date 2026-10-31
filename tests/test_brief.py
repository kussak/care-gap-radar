"""Brief generation: PHI exclusion, grounding validation, retry/502, caching, provider config."""

import json
import re
from types import SimpleNamespace

import pytest

from api.llm.brief import BRIEF_SCHEMA, PROMPT_VERSION, age_band, build_facts, build_user_prompt
from api.llm.fake_provider import FakeProvider
from api.queries import patient_detail
from tests.conftest import PATIENTS


def valid_brief(fact_ids=("F1",), outreach="Hi, this is your care team. Please call us back."):
    return {
        "summary": "s",
        "risk_explanation": "r",
        "priority_actions": [{"action": "a", "rationale": "b", "fact_ids": list(fact_ids)}],
        "outreach_message": outreach,
        "caveats": [],
    }


# --- minimum necessary / PHI exclusion -------------------------------------------------------


@pytest.mark.parametrize("p", PATIENTS, ids=lambda p: p["patient_id"])
def test_prompt_excludes_identifiers(p):
    patient = patient_detail(p["patient_id"])
    prompt = build_user_prompt(build_facts(patient))
    for forbidden in (p["first_name"], p["last_name"], p["patient_id"]):
        assert forbidden not in prompt
    assert not re.search(r"\d{4}-\d{2}-\d{2}", prompt), "exact dates must be made relative"
    assert not re.search(rf"\b{p['age_years']}\b", prompt), "exact age must not appear"
    for word in ("address", "ssn", "birth"):
        assert word not in prompt.lower()


def test_what_the_provider_receives_excludes_identifiers(client, fake_provider):
    client.post("/api/patients/aaaa-1111/brief")
    sent = fake_provider.calls[0]["system"] + fake_provider.calls[0]["user"]
    assert "Testy123" not in sent and "Patient456" not in sent and "aaaa-1111" not in sent


def test_age_bands():
    assert age_band(58) == "50–59"
    assert age_band(34) == "30–39"
    assert age_band(93) == "90+"


def test_facts_content():
    facts = build_facts(patient_detail("aaaa-1111"))
    texts = [f.text for f in facts]
    assert [f.id for f in facts] == [f"F{i}" for i in range(1, len(facts) + 1)]
    assert texts[0] == "Age 50–59, female, Medicaid"
    assert any("Open care gap: Diabetes" in t and "7.2%" in t and "months ago" in t for t in texts)
    assert any("Evidence: last BP 152/94 about 6 months ago" in t for t in texts)
    assert any("97th percentile" in t for t in texts)
    assert any("not clearly better than simply ranking by prior ED visits" in t for t in texts)


# --- validation, retry, 502 ------------------------------------------------------------------


def brief_with(client, provider):
    from api.llm.provider import get_provider
    from api.main import app

    app.dependency_overrides[get_provider] = lambda: provider
    return client.post("/api/patients/aaaa-1111/brief")


def test_unknown_fact_id_retries_once_then_succeeds(client):
    provider = FakeProvider(responses=[valid_brief(["F99"]), valid_brief(["F1", "F2"])])
    resp = brief_with(client, provider)
    assert resp.status_code == 200
    assert len(provider.calls) == 2
    assert "F99" in provider.calls[1]["user"], "retry prompt should explain the rejection"


def test_unknown_fact_id_twice_returns_502(client):
    provider = FakeProvider(responses=[valid_brief(["F99"]), valid_brief(["F42"])])
    resp = brief_with(client, provider)
    assert resp.status_code == 502
    assert "F42" in resp.json()["detail"]


def test_outreach_over_80_words_is_rejected(client):
    long_msg = " ".join(["word"] * 80)
    provider = FakeProvider(responses=[valid_brief(outreach=long_msg)] * 2)
    resp = brief_with(client, provider)
    assert resp.status_code == 502
    assert "80" in resp.json()["detail"]


def test_action_without_citations_is_rejected(client):
    provider = FakeProvider(responses=[valid_brief(fact_ids=[]), valid_brief()])
    assert brief_with(client, provider).status_code == 200
    assert len(provider.calls) == 2


# --- caching ---------------------------------------------------------------------------------


def test_brief_is_cached_and_refresh_regenerates(client, fake_provider):
    first = client.post("/api/patients/aaaa-1111/brief").json()
    second = client.post("/api/patients/aaaa-1111/brief").json()
    assert first["cached"] is False and second["cached"] is True
    assert second["generated_at"] == first["generated_at"]
    assert len(fake_provider.calls) == 1

    third = client.post("/api/patients/aaaa-1111/brief?refresh=true").json()
    assert third["cached"] is False
    assert len(fake_provider.calls) == 2
    assert third["model"] == "fake-provider" and third["prompt_version"] == PROMPT_VERSION
    assert {f["id"] for f in third["facts"]} >= {"F1", "F2"}


def test_cache_is_per_patient(client, fake_provider):
    client.post("/api/patients/aaaa-1111/brief")
    assert client.post("/api/patients/cccc-3333/brief").json()["cached"] is False
    assert len(fake_provider.calls) == 2


# --- Anthropic provider config (no network) --------------------------------------------------


def test_anthropic_model_from_env(monkeypatch):
    from api.llm.anthropic_provider import AnthropicProvider

    assert AnthropicProvider().model == "claude-haiku-5-5"
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    assert AnthropicProvider().model == "claude-sonnet-5-5"


def test_anthropic_request_shape_uses_structured_outputs():
    from api.llm.anthropic_provider import AnthropicProvider

    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(valid_brief()))],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            _request_id="req_test",
        )

    stub = SimpleNamespace(messages=SimpleNamespace(create=create))
    out = AnthropicProvider(client=stub).generate_json("sys", "user", BRIEF_SCHEMA)
    assert out["summary"] == "s"
    assert captured["output_config"]["format"] == {"type": "json_schema", "schema": BRIEF_SCHEMA}
    assert "temperature" not in captured and "tool_choice" not in captured

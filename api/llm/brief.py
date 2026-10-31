"""Care-manager brief: minimum-necessary facts, prompt, grounding validation, SQLite cache."""

import hashlib
import json
import logging
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone

from pydantic import ValidationError

from api.db import brief_cache_path
from api.llm.provider import LLMError, LLMProvider
from api.queries import load_metrics
from api.schemas import Brief, BriefResponse, Fact

log = logging.getLogger(__name__)

PROMPT_VERSION = "v1"  # bump whenever SYSTEM_PROMPT, the user template or BRIEF_SCHEMA changes

SYSTEM_PROMPT = """You are a care-management assistant at a Federally Qualified Health Center (FQHC).
You help a care manager decide how to reach out to one patient this week.

Rules:
- Use ONLY the numbered facts provided. Do not assume anything that is not stated in a fact.
- Do not make diagnoses, and do not suggest starting, stopping or changing any medication.
- Every priority action must cite the IDs of the facts that support it (for example "F2").
  Cite only IDs that appear in the facts list.
- Give 1 to 3 priority actions a care manager can do: outreach, scheduling, reminders,
  referrals to the care team, or addressing barriers.
- The outreach message is written to the patient: warm, plain language, about a 6th-grade
  reading level, under 80 words, with no medical jargon, no risk scores and no mention of a model.
- Keep the summary to 2-3 sentences.
- Use caveats for anything the care manager should double-check, including the limits of the
  risk model if a fact describes them."""

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "risk_explanation": {"type": "string"},
        "priority_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "rationale": {"type": "string"},
                    "fact_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["action", "rationale", "fact_ids"],
                "additionalProperties": False,
            },
        },
        "outreach_message": {"type": "string"},
        "caveats": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "risk_explanation", "priority_actions", "outreach_message", "caveats"],
    "additionalProperties": False,
}

PAYER_LABELS = {
    "medicaid": "Medicaid",
    "medicare": "Medicare",
    "private": "private insurance",
    "none_other": "uninsured or other coverage",
}
SEX_LABELS = {"f": "female", "m": "male"}
DATE_RE = re.compile(r"(?:\bon )?\b(\d{4}-\d{2}-\d{2})\b")  # swallow "on " so "on <date>" reads well


class BriefValidationError(Exception):
    pass


def age_band(age: int) -> str:
    if age >= 90:
        return "90+"  # HIPAA safe harbor: ages over 89 are aggregated
    low = age // 10 * 10
    return f"{low}–{low + 9}"


def ordinal(percentile: float) -> str:
    """97.5 -> '97th'; capped at 99th so 99.7 doesn't read as '100th'."""
    n = min(int(percentile), 99)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def relative_time(d: date, as_of: date) -> str:
    months = round((as_of - d).days / 30.44)
    if months < 1:
        return "within the past month"
    if months < 24:
        return f"about {months} month{'s' if months != 1 else ''} ago"
    return f"about {round(months / 12)} years ago"


def relative_dates(text: str, as_of: date) -> str:
    """Replace exact dates (a HIPAA identifier) with relative time, e.g. 'about 11 months ago'."""
    return DATE_RE.sub(lambda m: relative_time(date.fromisoformat(m.group(1)), as_of), text)


def build_facts(patient: dict) -> list[Fact]:
    """Minimum-necessary facts for one patient (a dict from queries.patient_detail).

    Never includes name, address, SSN, birthdate, exact age, exact dates or internal IDs.
    """
    as_of = patient["data_as_of"]
    u = patient["utilization"]
    last_visit = as_of - timedelta(days=u["days_since_last_encounter"])
    texts = [
        f"Age {age_band(patient['age'])}, {SEX_LABELS.get(patient['sex'], 'sex unknown')}, "
        f"{PAYER_LABELS.get(patient['payer_category'], 'unknown coverage')}",
        "Chronic conditions: " + (", ".join(patient["conditions"]) if patient["conditions"] else "none on record"),
        f"Past 12 months: {u['ed_visits_12m']} ED visit(s), {u['inpatient_visits_12m']} inpatient stay(s), "
        f"{u['urgent_care_visits_12m']} urgent care visit(s), {u['outpatient_visits_12m']} outpatient/primary care visit(s)",
        f"ED visits in the past 24 months: {u['ed_visits_24m']}; last visit of any kind "
        f"{relative_time(last_visit, as_of)}",
        f"Active medications: {patient['active_med_count']}",
    ]
    for gap in patient["open_gaps"]:
        texts.append(
            f"Open care gap: {gap['gap_description']}. Evidence: {relative_dates(gap['evidence'], as_of)}"
        )
    if not patient["open_gaps"]:
        texts.append("No open care gaps for diabetes A1c testing or blood pressure control")

    risk = patient.get("risk")
    if risk:
        texts.append(
            f"Predicted risk of an ED visit in the next 6 months: {ordinal(risk['percentile'])} "
            f"percentile of the clinic's patients"
        )
        for d in risk["top_drivers"]:
            effect = "raises" if d["direction"] == "up" else "lowers"
            # the age driver carries the exact age; show the band instead
            value = age_band(patient["age"]) if d["feature"] == "age_years" else d["display_value"]
            texts.append(f"Risk factor: {d['label']} = {value} ({effect} predicted risk)")
        metrics = load_metrics()
        if metrics:
            texts.append(
                f"The risk model is a modest predictor (AUROC {metrics['model']['auroc']:.2f}); "
                + ("it performs better than ranking by prior ED visits."
                   if metrics["beats_baseline"]
                   else "it is not clearly better than simply ranking by prior ED visits.")
            )
    return [Fact(id=f"F{i}", text=t) for i, t in enumerate(texts, start=1)]


def build_user_prompt(facts: list[Fact]) -> str:
    facts_json = json.dumps([f.model_dump() for f in facts], indent=2, ensure_ascii=False)
    return f"Facts about the patient:\n{facts_json}\n\nWrite the care-manager brief."


def validate_brief(raw: dict, facts: list[Fact]) -> Brief:
    """Parse and check the brief: schema, 80-word outreach limit, and that every cited fact exists."""
    try:
        brief = Brief.model_validate(raw)
    except ValidationError as e:
        raise BriefValidationError(f"Schema validation failed: {e.errors(include_url=False)}") from e
    known = {f.id for f in facts}
    unknown = sorted(
        {fid for a in brief.priority_actions for fid in a.fact_ids if fid not in known}
    )
    if unknown:
        raise BriefValidationError(f"Cited fact IDs that do not exist: {', '.join(unknown)}")
    return brief


def facts_hash(facts: list[Fact]) -> str:
    payload = json.dumps([f.model_dump() for f in facts], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# --- cache -----------------------------------------------------------------------------------


def _cache() -> sqlite3.Connection:
    path = brief_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("""
        create table if not exists briefs (
            patient_id text, facts_hash text, model text, prompt_version text,
            brief_json text not null, generated_at text not null,
            primary key (patient_id, facts_hash, model, prompt_version)
        )
    """)
    return con


def _cache_get(key: tuple) -> tuple[Brief, datetime] | None:
    with _cache() as con:
        row = con.execute(
            "select brief_json, generated_at from briefs "
            "where patient_id = ? and facts_hash = ? and model = ? and prompt_version = ?",
            key,
        ).fetchone()
    if row is None:
        return None
    return Brief.model_validate_json(row[0]), datetime.fromisoformat(row[1])


def _cache_put(key: tuple, brief: Brief, generated_at: datetime) -> None:
    with _cache() as con:
        con.execute(
            "insert or replace into briefs values (?, ?, ?, ?, ?, ?)",
            (*key, brief.model_dump_json(), generated_at.isoformat()),
        )


# --- orchestration ---------------------------------------------------------------------------


def generate_brief(patient: dict, provider: LLMProvider, refresh: bool = False) -> BriefResponse:
    """Return a cached brief, or generate one (retrying once if validation fails).

    Raises LLMError if the provider fails or the brief is still invalid after the retry.
    """
    facts = build_facts(patient)
    key = (patient["patient_id"], facts_hash(facts), provider.model, PROMPT_VERSION)

    if not refresh and (hit := _cache_get(key)):
        brief, generated_at = hit
        return _response(patient, brief, facts, True, generated_at, provider)

    user = build_user_prompt(facts)
    error = None
    for attempt in (1, 2):
        prompt = user if error is None else (
            f"{user}\n\nYour previous answer was rejected: {error}\nReturn a corrected brief."
        )
        raw = provider.generate_json(SYSTEM_PROMPT, prompt, BRIEF_SCHEMA)
        try:
            brief = validate_brief(raw, facts)
            break
        except BriefValidationError as e:
            error = str(e)
            log.warning("brief validation failed (attempt %d): %s", attempt, error)
    else:
        raise LLMError(f"The brief failed validation twice. Last error: {error}")

    generated_at = datetime.now(timezone.utc)
    _cache_put(key, brief, generated_at)
    return _response(patient, brief, facts, False, generated_at, provider)


def _response(patient, brief, facts, cached, generated_at, provider) -> BriefResponse:
    return BriefResponse(
        patient_id=patient["patient_id"],
        brief=brief,
        facts=facts,
        cached=cached,
        generated_at=generated_at,
        model=provider.model,
        prompt_version=PROMPT_VERSION,
    )

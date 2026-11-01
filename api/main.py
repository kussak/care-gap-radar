"""Care Gap Radar API."""

import logging
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api import queries  # noqa: E402  (load .env before anything reads the environment)
from api.llm.brief import generate_brief  # noqa: E402
from api.llm.provider import LLMError, LLMProvider, get_provider  # noqa: E402
from api.schemas import (  # noqa: E402
    BriefResponse,
    GapCode,
    Health,
    PatientDetail,
    Summary,
    Worklist,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Care Gap Radar", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=Health)
def health() -> Health:
    metrics = queries.load_metrics()
    return Health(
        status="ok",
        data_as_of=queries.data_as_of(),
        model_version=metrics["model_version"] if metrics else None,
    )


@app.get("/api/summary", response_model=Summary)
def summary() -> Summary:
    s = queries.population_summary()
    if s is None:
        raise HTTPException(503, "Population summary not built yet; run `make dbt`.")
    return Summary(
        data_as_of=s["data_as_of"],
        patient_count=s["patient_count"],
        patients_with_open_gaps=s["patients_with_open_gaps"],
        gap_counts={"DM_A1C": s["gap_dm_a1c_count"], "HTN_BP": s["gap_htn_bp_count"]},
        payer_mix={k: s[f"payer_{k}"] for k in ("medicaid", "medicare", "private", "none_other")},
        utilization_12m={
            k: s[k]
            for k in ("ed_visits_12m", "inpatient_visits_12m", "urgent_care_visits_12m",
                      "outpatient_visits_12m", "total_claim_cost_12m")
        },
        model=queries.load_metrics(),
    )


@app.get("/api/patients", response_model=Worklist)
def patients(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    gap: GapCode | None = None,
    min_risk: float | None = Query(None, ge=0, le=100, description="Minimum risk percentile"),
    sort: Literal["gaps", "risk"] = Query(
        "gaps", description="gaps: open gaps first, then risk; risk: risk only"
    ),
) -> Worklist:
    total, rows = queries.worklist(limit, offset, gap, min_risk, sort)
    return Worklist(total=total, limit=limit, offset=offset, items=rows)


def _patient_or_404(patient_id: str) -> dict:
    patient = queries.patient_detail(patient_id)
    if patient is None:
        raise HTTPException(404, f"Unknown patient: {patient_id}")
    return patient


@app.get("/api/patients/{patient_id}", response_model=PatientDetail)
def patient(patient_id: str) -> PatientDetail:
    return PatientDetail(**_patient_or_404(patient_id))


@app.post("/api/patients/{patient_id}/brief", response_model=BriefResponse)
def brief(
    patient_id: str,
    refresh: bool = False,
    provider: LLMProvider = Depends(get_provider),
) -> BriefResponse:
    patient = _patient_or_404(patient_id)
    try:
        return generate_brief(patient, provider, refresh=refresh)
    except LLMError as e:
        raise HTTPException(502, f"Could not generate a valid brief: {e}") from e

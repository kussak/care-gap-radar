"""Pydantic response models. The brief models double as the LLM output contract."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

GapCode = Literal["DM_A1C", "HTN_BP"]

OUTREACH_MAX_WORDS = 80


class Health(BaseModel):
    status: str
    data_as_of: date | None
    model_version: str | None


class ModelMetrics(BaseModel):
    auroc: float
    pr_auc: float
    top_decile_capture: float


class ModelCard(BaseModel):
    model_version: str
    trained_at: str
    train_index_date: date
    test_index_date: date
    n_train: int
    n_test: int
    base_rate_test: float
    model: ModelMetrics
    baseline_prior_ed: ModelMetrics
    auroc_delta_ci95: list[float]
    beats_baseline: bool


class Utilization(BaseModel):
    ed_visits_12m: int
    ed_visits_24m: int
    inpatient_visits_12m: int
    urgent_care_visits_12m: int
    outpatient_visits_12m: int
    total_claim_cost_12m: float
    days_since_last_encounter: int


class PopulationUtilization(BaseModel):
    ed_visits_12m: int
    inpatient_visits_12m: int
    urgent_care_visits_12m: int
    outpatient_visits_12m: int
    total_claim_cost_12m: float


class Summary(BaseModel):
    data_as_of: date
    patient_count: int
    patients_with_open_gaps: int
    gap_counts: dict[str, int]
    payer_mix: dict[str, int]
    utilization_12m: PopulationUtilization
    model: ModelCard | None


class WorklistItem(BaseModel):
    patient_id: str
    display_name: str
    age: int
    sex: str
    payer_category: str
    risk_score: float | None
    risk_percentile: float | None
    open_gap_codes: list[str]
    ed_visits_12m: int
    days_since_last_encounter: int


class Worklist(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[WorklistItem]


class Driver(BaseModel):
    feature: str
    label: str
    value: float
    display_value: str
    shap: float
    direction: Literal["up", "down"]


class Risk(BaseModel):
    score: float
    percentile: float
    model_version: str
    top_drivers: list[Driver]


class CareGap(BaseModel):
    gap_code: GapCode
    gap_description: str
    evidence: str
    last_relevant_date: date | None


class PatientDetail(BaseModel):
    patient_id: str
    display_name: str
    age: int
    sex: str
    payer_category: str
    race: str | None
    ethnicity: str | None
    data_as_of: date
    conditions: list[str]
    active_med_count: int
    utilization: Utilization
    open_gaps: list[CareGap]
    risk: Risk | None


# --- LLM brief -------------------------------------------------------------------------------


class Fact(BaseModel):
    id: str
    text: str


class PriorityAction(BaseModel):
    action: str
    rationale: str
    fact_ids: list[str] = Field(min_length=1)


class Brief(BaseModel):
    summary: str
    risk_explanation: str
    priority_actions: list[PriorityAction] = Field(min_length=1)
    outreach_message: str
    caveats: list[str]

    @field_validator("outreach_message")
    @classmethod
    def outreach_under_limit(cls, v: str) -> str:
        n = len(v.split())
        if n >= OUTREACH_MAX_WORDS:
            raise ValueError(f"outreach_message has {n} words; must be under {OUTREACH_MAX_WORDS}")
        return v


class BriefResponse(BaseModel):
    patient_id: str
    brief: Brief
    facts: list[Fact]
    cached: bool
    generated_at: datetime
    model: str
    prompt_version: str

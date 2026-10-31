// Types mirror api/schemas.py; keep them in sync when the API changes.

export type GapCode = "DM_A1C" | "HTN_BP";

export interface ModelMetrics {
  auroc: number;
  pr_auc: number;
  top_decile_capture: number;
}

export interface ModelCard {
  model_version: string;
  trained_at: string;
  train_index_date: string;
  test_index_date: string;
  n_train: number;
  n_test: number;
  base_rate_test: number;
  model: ModelMetrics;
  baseline_prior_ed: ModelMetrics;
  auroc_delta_ci95: [number, number];
  beats_baseline: boolean;
}

export interface Summary {
  data_as_of: string;
  patient_count: number;
  patients_with_open_gaps: number;
  gap_counts: Record<GapCode, number>;
  payer_mix: Record<string, number>;
  utilization_12m: {
    ed_visits_12m: number;
    inpatient_visits_12m: number;
    urgent_care_visits_12m: number;
    outpatient_visits_12m: number;
    total_claim_cost_12m: number;
  };
  model: ModelCard | null;
}

export interface WorklistItem {
  patient_id: string;
  display_name: string;
  age: number;
  sex: string;
  payer_category: string;
  risk_score: number | null;
  risk_percentile: number | null;
  open_gap_codes: GapCode[];
  ed_visits_12m: number;
}

export interface Worklist {
  total: number;
  limit: number;
  offset: number;
  items: WorklistItem[];
}

export interface Driver {
  feature: string;
  label: string;
  value: number;
  display_value: string;
  shap: number;
  direction: "up" | "down";
}

export interface CareGap {
  gap_code: GapCode;
  gap_description: string;
  evidence: string;
  last_relevant_date: string | null;
}

export interface PatientDetail {
  patient_id: string;
  display_name: string;
  age: number;
  sex: string;
  payer_category: string;
  race: string | null;
  ethnicity: string | null;
  data_as_of: string;
  conditions: string[];
  active_med_count: number;
  utilization: {
    ed_visits_12m: number;
    ed_visits_24m: number;
    inpatient_visits_12m: number;
    urgent_care_visits_12m: number;
    outpatient_visits_12m: number;
    total_claim_cost_12m: number;
    days_since_last_encounter: number;
  };
  open_gaps: CareGap[];
  risk: {
    score: number;
    percentile: number;
    model_version: string;
    top_drivers: Driver[];
  } | null;
}

export interface Fact {
  id: string;
  text: string;
}

export interface Brief {
  summary: string;
  risk_explanation: string;
  priority_actions: { action: string; rationale: string; fact_ids: string[] }[];
  outreach_message: string;
  caveats: string[];
}

export interface BriefResponse {
  patient_id: string;
  brief: Brief;
  facts: Fact[];
  cached: boolean;
  generated_at: string;
  model: string;
  prompt_version: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, init);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(resp.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return resp.json() as Promise<T>;
}

export interface WorklistParams {
  limit: number;
  offset: number;
  gap?: GapCode;
  minRisk?: number;
}

export const api = {
  summary: () => request<Summary>("/api/summary"),
  worklist: ({ limit, offset, gap, minRisk }: WorklistParams) => {
    const q = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (gap) q.set("gap", gap);
    if (minRisk !== undefined) q.set("min_risk", String(minRisk));
    return request<Worklist>(`/api/patients?${q}`);
  },
  patient: (id: string) => request<PatientDetail>(`/api/patients/${encodeURIComponent(id)}`),
  brief: (id: string, refresh: boolean) =>
    request<BriefResponse>(
      `/api/patients/${encodeURIComponent(id)}/brief?refresh=${refresh}`,
      { method: "POST" },
    ),
};

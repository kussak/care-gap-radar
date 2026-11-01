# CLAUDE.md — Care Gap Radar

## What this project is

A small, local, end-to-end **population-health analytics app** for a fictional Federally Qualified Health Center (FQHC) participating in value-based care.

It answers one question for a care manager: **"Which of my patients should I call this week, and what should I say?"**

The pipeline:

1. **Synthetic patients and claims** come from Synthea, as CSV.
2. **DuckDB** is the warehouse, standing in for Snowflake.
3. **dbt** transforms the raw data into staging and marts.
4. **ML** (scikit-learn gradient boosting with SHAP) predicts the risk of an ED visit in the next 6 months.
5. **Care gaps** flag diabetes without an A1c test and hypertension that is uncontrolled or unmeasured.
6. **An LLM (Claude)** writes a structured care-manager brief per patient, grounded only in provided facts.
7. **FastAPI** serves a JSON API.
8. **React** (Vite + TypeScript) shows a worklist and a patient detail page.

**This is a weekend demo project.** It must be finished by Sunday night, so prefer simple, readable, working code over completeness. All data is synthetic. Still, treat it as if it were PHI: that's the professional habit we're demonstrating.

## Hard constraints

- **Hardware:** a 2019 Intel MacBook Pro with 16 GB RAM. Use no GPU, no heavy frameworks, no Docker.
- **Python:** 3.11. Manage the environment with `uv` (or a plain venv if `uv` is unavailable).
- **Node:** LTS. The frontend is Vite + React + TypeScript.
- **Java:** 17+, needed only to run Synthea.
- **LLM:** Anthropic API only. The key lives in `.env` as `ANTHROPIC_API_KEY`, which must never be committed. The budget is $5, so cache every brief and never call the API in tests.
- **Allowed Python dependencies:** `duckdb`, `dbt-duckdb`, `pandas`, `scikit-learn`, `shap`, `fastapi`, `uvicorn`, `pydantic`, `anthropic`, `python-dotenv`, `pytest`, `httpx`. Ask before adding anything else. In particular, don't use LightGBM or XGBoost, because they need `libomp` on macOS.
- **Allowed frontend dependencies:** `react-router-dom` and `@tanstack/react-query`. Use plain CSS and no component library. Ask before adding anything else.

## Repository layout

```
care-gap-radar/
  CLAUDE.md
  README.md                 # architecture diagram (Mermaid), how to run, design decisions
  DEVLOG.md                 # human-written log of AI collaboration (see "Working agreements")
  Makefile
  pyproject.toml
  .env.example              # ANTHROPIC_API_KEY=, ANTHROPIC_MODEL=claude-haiku-5-5
  .gitignore                # data/, *.duckdb, *.sqlite, .env, node_modules, target/, models/*.joblib
  data/
    raw/                    # Synthea CSV output (gitignored)
    warehouse.duckdb        # dbt target (gitignored)
    app.sqlite              # LLM brief cache (gitignored)
  synthea/                  # synthea jar + run script (jar gitignored)
  transform/                # dbt project
    dbt_project.yml
    profiles.yml            # in-project profile, duckdb path ../data/warehouse.duckdb
    seeds/chronic_condition_codes.csv
    models/staging/
    models/intermediate/
    models/marts/
    tests/                  # singular data tests
  ml/
    train.py                # trains + evaluates, saves model artifact
    score.py                # scores current index date, writes ml.risk_scores to DuckDB
    features.py             # shared feature list / loading
  api/
    main.py
    db.py                   # read-only DuckDB connection helper
    schemas.py              # Pydantic response models
    llm/
      provider.py           # LLMProvider protocol
      anthropic_provider.py
      ollama_provider.py    # stub adapter showing the swap path for real PHI
      fake_provider.py      # used in tests
      brief.py              # fact building, prompt, validation, caching
  tests/                    # pytest: API, brief validation, fact grounding
  web/                      # Vite React TS app
```

## Data: Synthea

- Generate about 2,000 living patients in Illinois/Chicago with a fixed seed:
  `java -jar synthea-with-dependencies.jar -s 42 -p 2000 --exporter.csv.export true --exporter.fhir.export false Illinois Chicago`
- Copy the CSVs into `data/raw/`.
- **Before writing any SQL, inspect the actual CSV headers and a few rows.** Synthea column names vary between versions, so don't assume them. Document the columns you use in `models/staging/_sources.yml`.
- The files we need are `patients`, `encounters`, `conditions`, `observations`, `medications` and `payers`. `claims` is optional, used only if it adds value cheaply.
- Load the raw data via dbt-duckdb sources with `external_location` pointing at the CSVs, so no separate ingest script is needed.

## Data model (dbt)

### Staging (`stg_*`)

Staging models do only light cleanup: rename columns to snake_case, cast dates and timestamps, and lowercase enums. Create one per source: patients, encounters, conditions, observations, medications and payers.

### Index dates (`int_index_dates`)

These are the backbone of leak-free ML:

- `current_date_` is the date of the latest encounter in the data.
- `test_index` is `current_date_` minus 6 months.
- `train_index` is `current_date_` minus 12 months.

The grain is one row per index date, with the columns `index_name` and `index_date`.

### Population (`int_population`)

The grain is patient × index date. A patient is included at an index date if they are alive on that date, aged 18–99 on that date, and had at least one encounter in the prior 24 months. This is a simple stand-in for attribution to an adult care-management program, worth mentioning in the README. The age bounds drop pediatrics (both care gaps are adult measures; a 1-year-old ranked in the 99th risk percentile) and Synthea's implausibly many centenarians (18 of 1,967 patients, up to age 109, vs about 0.03% in the US).

### Features (`int_patient_features`)

The grain is patient × index date. **Every feature uses only data strictly before `index_date`.** The lookback is 12 months unless noted otherwise.

A diagnosis is **active** at an index date when `start < index_date AND (stop IS NULL OR stop >= index_date)`. This applies to the chronic condition flags and the care gaps.

- Age at the index date, and sex.
- Payer category from the most recent encounter: `medicaid`, `medicare`, `private`, or `none_other`. Synthea's "Dual Eligible" payer maps to `medicare` (Medicare is primary for dual-eligibles).
- Counts of ED (`encounterclass = 'emergency'`), inpatient, urgent care, and ambulatory/wellness/outpatient visits.
- ED visits in the prior 24 months.
- Total claim cost.
- Days since the last encounter.
- Chronic condition flags from the `chronic_condition_codes` seed: diabetes, hypertension, CHF, COPD, asthma, CKD, depression and obesity. Find the SNOMED codes by querying the actual condition descriptions in the data, and record them in the seed with descriptions.
- Number of distinct active medications.
- Care gap flags as of the index date (see below).

### Care gaps (`int_care_gaps`)

The grain is patient × index date × gap. The gap definitions:

- **`DM_A1C`:** The patient has an active diabetes diagnosis (SNOMED 44054006 or other diabetes codes from the seed), and there is no HbA1c observation (LOINC 4548-4) in the 12 months before the index date. Prediabetes (SNOMED 714628002) does **not** count as diabetes. Diabetes *complication* codes (seed column `requires_confirmation = true`) count only when the patient also has an HbA1c or a diabetes medication (`diabetes_medication_codes` seed) before the index date: Synthea attaches them to some hypertensive patients with no other sign of diabetes. Verify these codes exist in the data.
- **`HTN_BP`:** The patient has active hypertension (SNOMED 59621000), and either the most recent systolic BP (LOINC 8480-6) in the past 12 months is ≥ 140, or there is no systolic BP reading in that window.

Each gap row carries `gap_code`, `gap_description`, `evidence` (a short text such as "last A1c 2025-03-14" or "no A1c on record"), and `last_relevant_date`.

### Labels (`int_labels`)

The grain is patient × index date, for `train_index` and `test_index` only. `label_ed_6m` = 1 if the patient has an ED encounter in the window (index_date, index_date + 6 months]. Obstetric ED admissions (reason code 72892002 "Normal pregnancy") are excluded: Synthea records labor as an emergency encounter, and with them included 35 of the top 50 risk scores were pregnant patients.

**After building, check the base rate.** If it's below about 3%, tell me and propose broadening the label to ED or inpatient. Don't change it silently.

### Marts

- **`mart_patient_current`:** Features at the current index date, joined with demographics for display. Include the patient's name, but note that the name is for UI only and is never sent to the LLM.
- **`mart_care_gaps_current`:** Open gaps at the current index date.
- **`mart_population_summary`:** Patient count, gap counts, payer mix and utilization totals.

### dbt tests

- `not_null` and `unique` on primary keys.
- `accepted_values` on `gap_code`, `payer_category` and `index_name`.
- A singular test that no feature uses data on or after its index date. For example, `last_encounter_date < index_date`.

## ML

- **`ml/train.py`:**
  - Train a `GradientBoostingClassifier` on `train_index` rows and evaluate on `test_index` rows. This is a time-based split; never use a random split across index dates.
  - Report AUROC, PR-AUC and the base rate.
  - Compare against a simple baseline that ranks patients by prior-12-month ED count, and report both models side by side. If the model doesn't beat the baseline, say so honestly.
  - Save the model and the feature list to `ml/models/model.joblib`, and the metrics to `ml/models/metrics.json`.
- **`ml/score.py`:**
  - Score `current` rows.
  - Compute the SHAP values with `TreeExplainer`.
  - Write the table `ml.risk_scores (patient_id, risk_score, risk_percentile, top_drivers JSON, model_version, scored_at)`. `top_drivers` holds the top 3 features by |SHAP|, with a human-readable label, the feature value and the direction.
- Keep feature-name → human-label mapping in one place (`ml/features.py`).

## API (FastAPI)

The API runs on port 8000 and uses a **read-only** DuckDB connection, which avoids lock conflicts with dbt. The brief cache lives in `data/app.sqlite`, not in DuckDB.

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{status, data_as_of, model_version}` |
| GET | `/api/summary` | population summary, gap counts, model metrics (incl. baseline comparison) |
| GET | `/api/patients?limit=50&offset=0&gap=&min_risk=&min_days_since_visit=&sort=gaps` | worklist, by default patients with open gaps first, then risk_score desc (`sort=risk`: risk_score desc only): id, display name, age, sex, payer, risk_score, risk_percentile, open gap codes, ED visits 12m, days since last visit |
| GET | `/api/patients/{id}` | detail: demographics, chronic conditions, utilization, open gaps with evidence, risk score + top drivers |
| POST | `/api/patients/{id}/brief?refresh=false` | care-manager brief (cached unless refresh=true) |

All responses are Pydantic models. Return a 404 for an unknown patient. Enable CORS for `http://localhost:5173`; the Vite proxy is also fine.

## LLM brief

### Provider abstraction

Define a `LLMProvider` protocol with `generate_json(system: str, user: str, schema: dict) -> dict`. It has three implementations:

- `AnthropicProvider`: the real one. The model comes from `ANTHROPIC_MODEL`, defaulting to `claude-haiku-5-5`. Get JSON through **structured outputs** (`output_config.format` with the schema below), which works on every current model. Don't force `tool_choice` (it's a 400 on Opus 5.5 / Sonnet 5.5) and don't send `temperature` (non-default values are a 400 on Haiku 5.5). Use effort `low` and `max_tokens` ≈ 2000, leaving room for adaptive thinking.
- `OllamaProvider`: a minimal adapter. It doesn't need to be tested live, because it exists to show the swap path for real PHI (self-hosted model) without code changes elsewhere.
- `FakeProvider`: returns a deterministic brief for tests.

Select the provider via the `LLM_PROVIDER` environment variable, defaulting to `anthropic`.

### Minimum necessary data

`build_facts(patient_id)` returns a list of facts like `{id: "F1", text: "Age 55–64, female, Medicaid"}`. The facts cover a 10-year age band (never the exact age), sex, payer category, chronic conditions, utilization counts, open care gaps with evidence, and the risk percentile with its top drivers.

**Never include** name, address, SSN, exact birthdate, exact age, or internal IDs in the prompt. Add a test that asserts this.

### Prompt rules (system prompt)

The model plays a care-management assistant at an FQHC. It must use only the provided facts, make no diagnoses or medication changes, cite fact IDs for every action, and write the outreach message in plain language at about a 6th-grade reading level.

### Output schema (validated with Pydantic)

```json
{
  "summary": "2-3 sentences",
  "risk_explanation": "why this patient is high risk, in plain words",
  "priority_actions": [{"action": "...", "rationale": "...", "fact_ids": ["F2", "F5"]}],
  "outreach_message": "patient-facing text, under 80 words",
  "caveats": ["..."]
}
```

### Validation and caching

- **Validation:** Every cited `fact_id` must exist (grounding check), and `outreach_message` must be under 80 words. If validation fails, retry once; if it still fails, return a 502 with a clear error. Log token usage per call.
- **Caching:** Cache by `(patient_id, facts_hash, model, prompt_version)` in SQLite. `prompt_version` is a constant in `brief.py`; bump it whenever the prompt or schema changes. The response includes `cached: true/false` and `generated_at`.

## Frontend (React, Vite, TypeScript)

The frontend runs on port 5173 and proxies `/api` to 8000. Use TanStack Query for fetching and react-router for navigation. It has two screens:

1. **Worklist (`/`)**
   - A header with summary stats (patients, open gaps by type, data-as-of date) and a small model card showing AUROC vs the baseline.
   - Filters for gap type, minimum risk percentile and "not seen in" (any / 30+ / 90+ days, default any; recently seen patients may still need a post-discharge call or a missed test), and a sort choice (open gaps first, the default, or highest risk).
   - A table showing name, age/sex, payer, a risk bar or percentile, gap badges, ED visits in 12 months and last visit. Clicking a row opens the patient detail.
2. **Patient detail (`/patients/:id`)**
   - Demographics, conditions and utilization.
   - Open care gaps with evidence.
   - Risk drivers, each showing its label, value and an up/down arrow.
   - A **"Generate care brief"** button. It shows a loading state, then renders the brief with fact-ID chips that highlight the matching fact. Show a "cached" tag when the brief came from the cache, and add a "Regenerate" link.

Keep the styling clean and clinical: a neutral palette, one accent color, and readable tables. Show a visible "Synthetic data — not real patients" banner.

## Makefile targets

`make setup` · `make data` (run Synthea and copy CSVs) · `make dbt` (seed, run, test) · `make train` · `make score` · `make api` · `make web` · `make test` · `make all` (data → dbt → train → score)

## Build order (stop after each phase, show results, wait for my OK)

1. **Scaffold:** Create the repo layout, `pyproject.toml`, `.gitignore`, `.env.example`, Makefile and README skeleton. Make the initial commit.
2. **Data:** Run Synthea, inspect the headers, and write the staging models and sources. Run `dbt build`. Show row counts.
3. **Features, gaps and labels:** Build the seed, intermediates and marts, plus tests. Show the label base rate, the gap counts, and 5 sample patients.
4. **ML:** Train, evaluate and score. Show the metrics against the baseline and a few SHAP driver examples.
5. **API:** Implement the endpoints with the FakeProvider and write the pytest suite. Then wire up the Anthropic provider and generate **one** real brief for me to review.
6. **Frontend:** Build the worklist, then the detail page and the brief UI.
7. **Polish:** Write the README (Mermaid architecture diagram, run instructions, design decisions, "what I'd do in production") and run the full `make all` from clean.

## Working agreements

- Before coding each phase, state a short plan. Ask when something is ambiguous instead of guessing, especially clinical logic.
- Make small, focused commits with conventional commit messages, one per logical step.
- Don't silently change definitions in this file (gaps, labels, index dates). Propose the change, then update this file.
- Write tests for logic that matters: grounding validation, PHI exclusion from prompts, API contracts, and the dbt leakage test.
- Don't call the paid API in tests or loops. One real call at a time, and only when I ask.
- When you hit something surprising in the data (odd codes, missing values, low base rates), stop and report it. These are the interesting moments.
- `DEVLOG.md` is mine, but remind me at the end of each phase to jot down what worked, what you got wrong, and what I corrected.

## "What I'd do in production" (for the README)

- Replace DuckDB with Snowflake, and orchestrate with dbt Cloud or Airflow.
- Ingest FHIR R4 or claims feeds instead of CSV.
- Proper attribution logic and HEDIS/UDS measure specs.
- Real PHI handling: a BAA with the LLM vendor or a self-hosted model, audit logging of every prompt and response, RBAC, and minimum-necessary enforcement.
- Model monitoring for drift, calibration and fairness across payer, sex and age, plus a scheduled retrain.
- Human-in-the-loop: briefs are drafts for care managers, never auto-sent to patients.

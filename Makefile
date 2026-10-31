SHELL := /bin/bash
JAVA ?= $(shell /usr/libexec/java_home -v 17)/bin/java
export JAVA

.PHONY: help setup data dbt train score api web web-check test all clean java-version

help:  ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup:  ## Install Python (uv) and web (npm) dependencies
	uv sync
	@if [ -f web/package.json ]; then cd web && npm install; fi

java-version:  ## Show the Java used for Synthea
	@"$(JAVA)" -version

data:  ## Run Synthea into data/raw/ (skips if data exists; FORCE=1 regenerates)
	FORCE=$(FORCE) bash synthea/run.sh

dbt:  ## dbt seed, run, test (stop the API first: DuckDB file lock)
	cd transform && uv run dbt build --profiles-dir .

train:  ## Train and evaluate the ED-risk model
	uv run python -m ml.train

score:  ## Score current patients, write ml.risk_scores (stop the API first)
	uv run python -m ml.score

api:  ## Run FastAPI on :8000
	uv run uvicorn api.main:app --reload --port 8000

web:  ## Run Vite dev server on :5173 (proxies /api to :8000)
	cd web && npm run dev

web-check:  ## Typecheck and build the web app
	cd web && npm run build

test:  ## Run pytest
	uv run pytest

all: data dbt train score  ## data -> dbt -> train -> score

clean:  ## Remove derived artifacts (warehouse, model, dbt build); keeps raw CSVs and brief cache
	rm -f data/warehouse.duckdb data/warehouse.duckdb.wal ml/models/model.joblib
	rm -rf transform/target transform/logs web/dist

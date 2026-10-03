# Plan: CoCo Lifecycle Evidence Pack

## Context

- **Plan files:** 10 under `.snowflake/cortex/plans/`. 8 are committed; `fix-setup-skill-end-to-end` and `public-streamlit-url` are untracked.
- **Commits:** 26 in total; 3 carry the "Co-authored-by: Snowflake CoCo" trailer (`270464d`, `0771774`, `42e6040`).
- **Test scripts:** every validation script from this session sits in `%TEMP%` and is not in the repo. They are:
  - `dryrun_sv.py`
  - `probe_public.py`
  - `verify_cloud.py`
  - `verify_snowpark_binds.py`
  - `regress_zero.py`
  - `smoke_app.py`
  - `verify_copilot2.py`
- **Snowflake activity:**
  - `SNOWFLAKE.ACCOUNT_USAGE.SESSIONS` identifies CoCo by `CLIENT_ENVIRONMENT:APPLICATION`: `cortex_code_desktop` (20 sessions), `cortex_code_sandbox` (6), `Snowflake Web App (snowsight_cortex_code)`. Scripts CoCo ran appear as `PythonConnector` / `streamlit`.
  - `QUERY_HISTORY` for DIBUPIHU holds about 2,340 queries over 5 days, including 85 CREATE statements.

## Implementation steps

### 1. tests/ suite (rebuilt from the temp scripts, made repeatable)
- `tests/conftest.py`: a session-scoped connection helper. It uses the named connection by default and the service user when `.streamlit/secrets.toml` exists (the same logic as the app).
- `tests/test_deployment.py`: object inventory.
  - 9 RAW tables, 10 CURATED tables, 4 semantic views
  - `POLICY_SEARCH` ACTIVE with 6 rows, agent with 5 tools
  - Streamlit app has a live version; ingest task is `started`
- `tests/test_semantic_views.py`: `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML(..., TRUE)` dry-run of all 4 YAMLs, plus one Cortex Analyst question per view that must return SQL which then executes.
- `tests/test_data_quality.py`: business-rule checks.
  - The latest loan snapshot has exactly 1 row per loan.
  - Flagged count = 100, and flagged amount ≤ total.
  - No orphan fact keys against the current dimension rows.
  - The SCD2 rule holds: exactly 1 `IS_CURRENT` row per natural key.
- `tests/test_public_access.py`: the service user can read CURATED; RAW, CREATE and UPDATE are refused; bound COMPLETE and SEARCH_PREVIEW accept backslash and quote text. Skipped if no secrets file.
- `tests/test_app.py`: headless `AppTest` of all 4 pages.
  - zero-transaction regression (CUST-0002 renders 0 / $0, no exception)
  - one Copilot answer
  - 21st-call cap
  - Report Builder narrative
- Use `pytest`, add it as a dev dependency in `pyproject.toml`, and run it with `.venv\Scripts\python.exe -m pytest tests -v`.

### 2. docs/COCO_EVIDENCE.md
- One section per phase (Planning, Development, Execution, Testing). Each has a table: what CoCo did → artifact (plan file / commit / Snowflake object / test) → how a judge can verify it.
- Name the CoCo skills used: `setup`, `semantic-view`, `cortex-agent`, `developing-with-streamlit-in-snowflake`.
- Include a "Known gaps" section stating honestly that only 3 commits carry the CoCo trailer, and that the early build history lives in the CoCo conversation history and Snowflake query history.
- Add a screenshot/recording checklist for the four phases.

### 3. scripts/coco_activity_report.sql
- Query 1: sessions by client application, with CoCo apps flagged.
- Query 2: queries per day, split into CoCo-direct (session application `cortex_code%`) and CoCo-launched scripts (`PythonConnector` / `streamlit`), with CREATE counts.
- Query 3: the Snowflake objects created, with timestamps (CREATE statements ordered by time), mapped to phases by date.
- Run it once and paste the summary numbers into COCO_EVIDENCE.md.

### 4. Commit and push
- Commit the `tests/` folder, the evidence doc, the report SQL, the `pyproject.toml` change, and the 2 untracked plan files.
- Before committing, confirm that no secrets are staged.

## Verification
- `pytest tests -v` passes in full, or any failure is reported as-is (not silently skipped).
- The report SQL runs and returns non-empty results for CoCo applications.
- Every artifact path in COCO_EVIDENCE.md exists; check with a script that parses the doc's links.
- `git ls-remote` shows the new commit on GitHub, and `secrets.toml` is not tracked.

## Notes
- The tests only read data and run dry-runs; nothing is created or changed. The Analyst and COMPLETE calls cost a few cents of Cortex credit.
- ACCOUNT_USAGE views lag by up to about 45 minutes, so the newest activity may be missing from the report.

## Critical Files
- `tests/` (new) - repeatable validation suite
- `docs/COCO_EVIDENCE.md` (new) - phase-by-phase proof for judges
- `scripts/coco_activity_report.sql` (new) - Snowflake activity attributable to CoCo
- [pyproject.toml](pyproject.toml) - add pytest dev dependency

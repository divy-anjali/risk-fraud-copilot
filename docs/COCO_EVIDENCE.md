# CoCo Across the Lifecycle — Evidence

This document maps each hackathon phase (Planning, Development, Execution, Testing)
to the artifacts that show Cortex Code (CoCo) was used, and tells a judge how to
verify each one. Every claim below points at a file in this repo, a commit, a
Snowflake object, or a query anyone with account access can re-run.

**Headline numbers** (account `QBGIWTU-DK32675`, 2026-09-28 → 2026-10-03, from
[scripts/coco_activity_report.sql](../scripts/coco_activity_report.sql)):

| Measure | Value |
|---|---|
| Queries run through CoCo | 877 (331 by CoCo's SQL tool directly, 546 by scripts CoCo launched) |
| Project objects created through CoCo | **84 of 84** (75 by CoCo's SQL tool, 9 by scripts it launched; 0 created outside CoCo) |
| DDL statements through CoCo | 99 of 103 — the other 4 are Snowsight housekeeping (worksheet migration, default workspace), not project objects |
| CoCo plans written before building | 11 (in `.snowflake/cortex/plans/`) |
| Automated validation tests | 55, all passing |

---

## 1. Planning

CoCo explored the data, framed the problem, and wrote a plan before each build.
The three most recent plans (setup-skill repair, public hosting, this evidence pack)
were written in CoCo's read-only Plan mode and approved before any change was made.

| What CoCo did | Evidence | How to verify |
|---|---|---|
| Designed the end-to-end deployment on a fresh account | [deploy-risk-fraud-copilot-fresh-account.plan.md](../.snowflake/cortex/plans/deploy-risk-fraud-copilot-fresh-account.plan.md), [step-by-step-deploy.plan.md](../.snowflake/cortex/plans/step-by-step-deploy.plan.md) | Open the files |
| Designed the Cortex Agent: tools, routing, response style | [build-cortex-agent.plan.md](../.snowflake/cortex/plans/build-cortex-agent.plan.md), [cortex-agent-and-streamlit-consumption-layer.plan.md](../.snowflake/cortex/plans/cortex-agent-and-streamlit-consumption-layer.plan.md) | Open the files |
| Decided what a non-technical user needs to see, and scoped the 4 app pages | [streamlit-copilot-consumption-areas.plan.md](../.snowflake/cortex/plans/streamlit-copilot-consumption-areas.plan.md), [aml-customer360-dashboard.plan.md](../.snowflake/cortex/plans/aml-customer360-dashboard.plan.md) | Open the files |
| Planned branching and delivery of the consumption layer | [branch-workflow-and-consumption-layer.plan.md](../.snowflake/cortex/plans/branch-workflow-and-consumption-layer.plan.md), [branch-and-implement-consumption-layer.plan.md](../.snowflake/cortex/plans/branch-and-implement-consumption-layer.plan.md) | Open the files |
| Audited and repaired the deployment skill | [fix-setup-skill-end-to-end.plan.md](../.snowflake/cortex/plans/fix-setup-skill-end-to-end.plan.md) | Open the file |
| Designed safe public hosting: least-privilege user, cost caps, injection fix | [public-streamlit-url.plan.md](../.snowflake/cortex/plans/public-streamlit-url.plan.md) | Open the file |
| Planned this evidence pack | [coco-lifecycle-evidence.plan.md](../.snowflake/cortex/plans/coco-lifecycle-evidence.plan.md) | Open the file |
| Explored the data model before building (row counts, keys, distributions) | 94 read-only queries through CoCo on day 1 | Report query 2, `COCO_READS` column |

## 2. Development

CoCo wrote the pipelines, semantic views, search service, agent, and app, and fixed
its own errors along the way. It used these CoCo skills:

| Skill | What it built |
|---|---|
| `setup` (this project's own skill) | The 16-step deployment, from infrastructure to the Streamlit app |
| `semantic-view` | The 4 semantic views and their verified queries |
| `cortex-agent` | `RISK_FRAUD_COPILOT`: 4 Cortex Analyst tools + 1 Cortex Search tool |
| `developing-with-streamlit-in-snowflake` | The dual-mode Streamlit app (runs in Snowflake or hosted) |

| What CoCo built | Evidence | How to verify |
|---|---|---|
| RAW → CURATED → SEMANTICS pipeline (9 raw tables, SCD2 star schema, 12 procedures) | 73 project objects created through CoCo on 2026-09-28 | Report query 3 |
| 4 semantic views | [semantics/](../semantics) `*.sv.yaml` | `SHOW SEMANTIC VIEWS IN SCHEMA RISK_DB.SEMANTICS` |
| Policy search over AI-parsed PDFs | [semantics/policy_search.sql](../semantics/policy_search.sql) | `SHOW CORTEX SEARCH SERVICES IN SCHEMA RISK_DB.SEMANTICS` |
| Cortex Agent | [semantics/risk_fraud_copilot.agent.sql](../semantics/risk_fraud_copilot.agent.sql) | `DESCRIBE AGENT RISK_DB.SEMANTICS.RISK_FRAUD_COPILOT` |
| Streamlit app (4 pages) | [streamlit_app.py](../streamlit_app.py) | Run it, or open the public URL |
| Public hosting with least privilege | [cloud/app.py](../cloud/app.py), [scripts/public_app_access.sql](../scripts/public_app_access.sql) | Commit `42e6040` |
| Iterating on errors instead of fixing by hand | 25 CoCo queries failed during development and were corrected in later runs; examples include invalid semantic-view syntax, a reserved-word column alias, and a qualified name in the Search `ON` clause | Report query 2, `FAILED` column |
| Commits co-authored by CoCo | `270464d`, `0771774`, `42e6040` | `git log --grep="Snowflake CoCo"` |

## 3. Execution

The whole solution is deployed and run through CoCo, and it includes a scheduled
pipeline.

| What runs | Evidence | How to verify |
|---|---|---|
| One-command full deployment | [.cortex/skills/setup/SKILL.md](../.cortex/skills/setup/SKILL.md): type `/setup` in CoCo | Its 16 steps each end in a CHECKPOINT query |
| Streamlit deployment to Snowflake | [scripts/deploy_streamlit.py](../scripts/deploy_streamlit.py), run by CoCo | `SHOW STREAMLITS IN SCHEMA RISK_DB.SEMANTICS` |
| Scheduled incremental ingestion | `RISK_DATA_INGEST_TASK`, every 5 minutes, guarded by `SYSTEM$STREAM_HAS_DATA` on the stage stream; 9 CDC streams feed the curated layer | `SHOW TASKS IN SCHEMA RISK_DB.RAW` (state `started`) |
| Public deployment | Streamlit Community Cloud app, entrypoint `cloud/app.py` | Open the URL in a private window |

## 4. Testing and validation

CoCo validated outputs, checked accuracy against ground truth, and covered edge
cases and security, all in a suite anyone can re-run:

```
.venv\Scripts\python.exe -m pytest tests -v
```

| Test file | What it proves | Tests |
|---|---|---|
| [tests/test_deployment.py](../tests/test_deployment.py) | Every layer exists: 9 RAW + 10 CURATED tables, 10 non-stale streams, task scheduled, 4 semantic views, search service serving, agent wired to 5 tools, app live, public warehouse capped | 9 |
| [tests/test_data_quality.py](../tests/test_data_quality.py) | RAW reconciles to CURATED; SCD2 has exactly one current row per key; no orphan foreign keys; flags and values are consistent; every policy parsed | 19 |
| [tests/test_semantic_views.py](../tests/test_semantic_views.py) | All 4 YAML specs pass a dry-run validation, and **Cortex Analyst's answers match ground-truth SQL** for each view (within 0.5%) | 8 |
| [tests/test_public_access.py](../tests/test_public_access.py) | The public user can read CURATED only; RAW reads, CREATE, UPDATE, DELETE and role escalation are refused; bound Cortex SQL resists backslash/quote injection | 9 |
| [tests/test_app.py](../tests/test_app.py) | All 4 pages render headless; regression for the zero-transaction crash; customer with no flags; a live Copilot answer; the 20-call usage cap; narrative generation | 10 |

Edge cases found by testing and then fixed:
- **Customer 360 crash:** for a customer with no transactions, `SUM` returned NULL and `int(None)` crashed the page. Fixed in SQL and Python; locked in by `test_customer360_handles_customer_with_no_transactions`.
- **Loan performance is a monthly time series:** a global `MAX(REPORT_DATE)` filter returned 1 row instead of 60, so the app takes the latest snapshot per loan. Covered by `test_every_current_loan_has_performance_history`.
- **SQL injection:** quote-doubling could be bypassed with a backslash, so Cortex calls were switched to bind parameters. Covered by the `*_binds_hostile_text_safely` tests.
- **Setup skill defects:** invalid semantic-view syntax, a CLI that doesn't exist, and a missing `policy_documents.sql`. All 4 YAMLs were then dry-run validated (`test_semantic_view_yaml_validates`).

---

## Known gaps (stated plainly)

- **The scheduled task has not yet loaded a file on its own.** It is `started`, but all 9 recorded runs are `SKIPPED`, because every load so far was a direct procedure call and the stream guard never fired. To record an automated run:
  ```sql
  CALL RISK_DB.RAW.SP_GENERATE_RISK_DATA();
  ALTER STAGE RISK_DB.RAW.RISK_FRAUD_DATA_STAGE REFRESH;
  -- wait up to 5 minutes, then:
  SELECT STATE, SCHEDULED_TIME, COMPLETED_TIME
  FROM TABLE(RISK_DB.INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME => 'RISK_DATA_INGEST_TASK'))
  ORDER BY SCHEDULED_TIME DESC LIMIT 5;
  ```
  This adds a new batch of synthetic data; re-run the test suite afterwards.
- **Query history covers this account only, from 2026-09-28.** Work committed in August was done in an earlier account and by more than one contributor; this report does not cover it.
- **Only 3 of 26 commits carry the CoCo co-author trailer.** Earlier commits were made without it, so for that period the plan files and Snowflake history are the evidence.
- **"Launched by CoCo" is inferred.** Queries from `PythonConnector` / `streamlit` sessions come from scripts CoCo ran in its terminal, but those client names alone cannot prove who started them.
- **ACCOUNT_USAGE lags by up to ~45 minutes**, so the most recent activity may not appear yet.

## Capture checklist for the demo video

- [ ] **Planning:** ask CoCo to explore `RISK_DB` in Plan mode; open one plan card.
- [ ] **Development:** make one small change live, e.g. add a verified query to a semantic view, and let CoCo validate and deploy it.
- [ ] **Execution:** run `/setup` (or one of its steps) and show `SHOW TASKS`; trigger the task as described above.
- [ ] **Testing:** have CoCo run `pytest tests -v` and show 55 passing.
- [ ] Open the public app in a private window.

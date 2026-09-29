---
name: "deploy risk fraud copilot fresh account"
created: "2026-09-29T03:48:38.944Z"
status: pending
---

## Context

Repo at `c:\Users\DYANJ\risk-fraud-copilot` contains a complete medallion-architecture project (previously deployed once on a different trial account, `HMXHRPH-KH35929`, per project memory). That account is no longer the active connection — the current connection is a **fresh** account (`QBGIWTU-DK32675`) with no `RISK_DB` at all (confirmed via `SHOW DATABASES LIKE 'RISK_DB'` returning zero rows).

The repo's own `.cortex/skills/setup/SKILL.md` documents the exact, dependency-ordered workflow to stand this up from zero, matching `scripts/deploy.sql`'s ordering:

```
Infrastructure -> RAW (tables, procs, generate+load data, streams/task) -> CURATED (sequences, views, dim/fact tables, load procs, refresh, CDC streams) -> SEMANTICS (4 semantic views)
```

This is effectively a repeat of the same successful deployment done earlier in the project (see memory: `deployment.md`), just targeting a new account. Two known gotchas from that prior run, already captured in memory, will be applied directly this time to avoid re-discovering them:

- `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('RISK_DB.SEMANTICS', <yaml>)` — first arg is the schema path only, not the full view name.
- Policy document stage may need `ALTER STAGE ... REFRESH` before `AI_PARSE_DOCUMENT` picks up new files.

## Implementation steps

1. **Infrastructure** — Execute in order: `infrastructure/warehouses.sql`, `database.sql`, `schemas.sql`, `file_formats.sql`, `stages.sql`. Creates `COMPUTE_WH`, `RISK_DB` with `RAW`/`CURATED`/`SEMANTICS` schemas, `CSV_FORMAT`, and the two stages (`POLICIES_STAGE`, `RISK_FRAUD_DATA_STAGE`).

2. **RAW tables + procedures** — Execute the 9 table DDLs in `raw/tables/` (customer\_master, account\_master, loan\_master, loan\_performance, transaction\_fact, deposit\_balances, pep\_list, sanctions\_watchlist, policy\_documents), then `raw/procedures/sp_generate_risk_data.sql` (Python SP synthesizing CSVs/PDFs) and `sp_load_raw_data.sql` (SQL SP loading CSVs + parsing policy PDFs into RAW tables).

3. **Generate + load data** — `CALL RISK_DB.RAW.SP_GENERATE_RISK_DATA();` then verify files landed on both stages, then `CALL RISK_DB.RAW.SP_LOAD_RAW_DATA();`. Verify row counts match expected volumes (\~100/150/60/200/1000/150/15/20/6).

4. **RAW automation** — Create the stage stream (`risk_data_stage_stream.sql`) and ingestion task (`risk_data_ingest.sql`), then resume the task.

5. **CURATED layer build** — Sequences (`sequences.sql`), then all 9 intermediate views in `curated/views/`, then all 10 dim/fact/ref tables in `curated/tables/`, then all 10 load procedures in `curated/procedures/`.

6. **Populate + CDC** — `CALL RISK_DB.CURATED.SP_REFRESH_CURATED_LAYER();`, verify dimension/fact row counts (DIM\_DATE \~1461 rows), then create the 9 CDC streams from `curated/streams/streams.sql`.

7. **Semantics layer** — For each of the 4 `.sv.yaml` files in `semantics/`, read the YAML and deploy via `CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('RISK_DB.SEMANTICS', $$<yaml_content>$$);`. Verify with `SHOW SEMANTIC VIEWS IN SCHEMA RISK_DB.SEMANTICS` (expect 4).

8. **End-to-end verification** — Row count checks across RAW/CURATED, `SHOW STREAMS`/`SHOW TASKS` (task state = started), and a sample query against one semantic view to confirm it resolves correctly.

Note: this plan intentionally stops at the 4 semantic views (matching the original scope of `scripts/deploy.sql`/setup skill). The Cortex Search Service and Cortex Agent built later in the project are not part of this repo's tracked deployment scripts — happy to add those as a follow-on once the base platform is verified, if wanted.

## Verification

- `SHOW TABLES IN SCHEMA RISK_DB.RAW` -> 9 tables
- Row-count UNION query across all RAW tables -> nonzero, matches expected volumes
- `SHOW TABLES IN SCHEMA RISK_DB.CURATED` -> 10 tables (5 dims + 3 facts + DIM\_DATE + REF\_POLICY\_DOCUMENTS)
- Row-count UNION query across all CURATED tables -> nonzero
- `SHOW STREAMS IN SCHEMA RISK_DB.RAW` -> 10 (9 table + 1 stage), `SHOW TASKS` -> started
- `SHOW SEMANTIC VIEWS IN SCHEMA RISK_DB.SEMANTICS` -> 4
- Sample `SELECT * FROM SEMANTIC_VIEW(RISK_DB.SEMANTICS.RISK_FRAUD_SIGNALS ...)` or Cortex Analyst-style query executes without error

## Critical Files

- scripts/deploy.sql - canonical dependency order for every object
- .cortex/skills/setup/SKILL.md - step-by-step workflow with checkpoints, used as the execution script
- raw/procedures/sp\_generate\_risk\_data.sql - synthetic data generator (Python SP)
- curated/procedures/sp\_refresh\_curated\_layer.sql - orchestrates all curated loads
- semantics/risk-fraud-copilot.yaml - manifest referencing the 4 semantic view YAMLs

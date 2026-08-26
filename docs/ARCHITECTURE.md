# Risk Fraud Copilot — Architecture

## Overview

A Snowflake-native banking risk and fraud data platform using a medallion architecture (RAW → Silver → Gold). The RAW layer is an append-only replica of staged files with full audit lineage.

## Quick Start

To deploy from scratch, use the Cortex Code skill:

```
/setup
```

This provisions all infrastructure, tables, procedures, sample data, and the live ingestion pipeline automatically.

---

## Pipeline Architecture

```
                         ┌─────────────────────────────────┐
                         │  CALL GENERATE_RISK_DATA()      │
                         │  (produces CSVs + PDFs)         │
                         └──────────────┬──────────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────────┐
                         │  @RISK_FRAUD_DATA_STAGE         │
                         │  (directory-enabled)            │
                         └──────────────┬──────────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────────┐
                         │  RISK_DATA_STAGE_STREAM         │
                         │  (detects new files)            │
                         └──────────────┬──────────────────┘
                                        │ triggers
                                        ▼
                         ┌─────────────────────────────────┐
                         │  RISK_DATA_INGEST_TASK          │
                         │  (every 5 min if stream has     │
                         │   data)                         │
                         └──────────────┬──────────────────┘
                                        │ calls
                                        ▼
                         ┌─────────────────────────────────┐
                         │  LOAD_NEW_CSV_FILES()           │
                         │  (routes CSVs → tables via      │
                         │   COPY INTO with audit cols)    │
                         └──────────────┬──────────────────┘
                                        │
                                        ▼
               ┌────────────────────────────────────────────────┐
               │              RISK_DB.RAW Tables                 │
               │                                                │
               │  CUSTOMER_MASTER    ACCOUNT_MASTER             │
               │  LOAN_MASTER        LOAN_PERFORMANCE           │
               │  TRANSACTION_FACT   DEPOSIT_BALANCES           │
               │  PEP_LIST           SANCTIONS_WATCHLIST         │
               │                                                │
               │  (each row has _SOURCE_FILE + _LOADED_AT)      │
               └────────────────────────────────────────────────┘
```

---

## Data Relationships

```
CUSTOMER_MASTER (1)──┬──(N) ACCOUNT_MASTER
                     │         │
                     │         ├──(N) TRANSACTION_FACT
                     │         │
                     │         └──(N) DEPOSIT_BALANCES
                     │
                     ├──(N) LOAN_MASTER
                     │         │
                     │         └──(N) LOAN_PERFORMANCE
                     │
                     ├── matched against ── SANCTIONS_WATCHLIST
                     │
                     └── screened against ── PEP_LIST
```

---

## Medallion Layers

| Layer | Schema | Purpose | Dedup Strategy |
|-------|--------|---------|----------------|
| **RAW** | `RISK_DB.RAW` | Append-only replica of stage files | `COPY INTO ... FORCE = FALSE` (file-level, 64-day cache). Same data in a different filename appends — RAW is an immutable audit log. |
| **Silver** | `RISK_DB.SILVER` (planned) | Deduped, typed, business-keyed | `QUALIFY ROW_NUMBER() OVER (PARTITION BY <pk> ORDER BY _LOADED_AT DESC) = 1` |
| **Gold** | `RISK_DB.GOLD` (planned) | Business aggregates, metrics, views | Inherits deduped silver |

---

## Repo Structure

```
risk-fraud-copilot/
├── .cortex/skills/setup/    # /setup skill for automated deployment
├── infrastructure/          # Shared infra (warehouse, database, schemas, formats, stages)
├── raw/                     # Bronze layer
│   ├── tables/             # 8 tables with _SOURCE_FILE, _LOADED_AT
│   ├── streams/            # Stage stream for change detection
│   ├── tasks/              # 5-min ingestion task
│   └── procedures/         # Data generator + CSV loader
├── silver/                  # Curated layer (planned)
│   ├── dynamic_tables/
│   └── procedures/
├── gold/                    # Business-ready layer (planned)
│   ├── views/
│   └── dynamic_tables/
└── scripts/
    └── deploy.sql          # Ordered execution manifest
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| RAW as append-only | Preserves full history; dedup happens at silver layer where business logic lives |
| `_SOURCE_FILE` + `_LOADED_AT` on every table | Enables lineage tracking, dedup, and debugging without external tooling |
| Stream + Task (not scheduled COPY) | Event-driven — only runs when new files land, no wasted compute |
| `FORCE = FALSE` | Snowflake's 64-day file metadata cache prevents re-loading the same file |
| Procedure-based routing | Single task handles all 8 table targets via filename pattern matching |
| Timestamped stage folders | Multiple generator runs don't overwrite; each batch is traceable |

---

## Troubleshooting

| Issue | Check |
|-------|-------|
| Task not firing | `SHOW TASKS` — verify state is `started`. Run `SELECT SYSTEM$STREAM_HAS_DATA('RISK_DB.RAW.RISK_DATA_STAGE_STREAM');` — if FALSE, no new files since stream creation. |
| Data not loading after GENERATE_RISK_DATA | Run `ALTER STAGE RISK_DB.RAW.RISK_FRAUD_DATA_STAGE REFRESH;` to refresh the directory, then check the stream again. |
| COPY skips files | Expected if files were already loaded (`FORCE = FALSE`). Check with `INFORMATION_SCHEMA.COPY_HISTORY(...)`. |
| Tables empty after setup | Ensure data was generated before loading. Verify stage has files: `SELECT COUNT(*) FROM DIRECTORY(@RISK_DB.RAW.RISK_FRAUD_DATA_STAGE);` |
| Task SKIPPED in history | Normal when stream is empty. `error_code = 0040003` means "no data" — not an error. |

---

## Teardown

```sql
ALTER TASK RISK_DB.RAW.RISK_DATA_INGEST_TASK SUSPEND;
DROP TASK RISK_DB.RAW.RISK_DATA_INGEST_TASK;
DROP STREAM RISK_DB.RAW.RISK_DATA_STAGE_STREAM;
DROP PROCEDURE RISK_DB.RAW.LOAD_NEW_CSV_FILES();
DROP PROCEDURE RISK_DB.RAW.GENERATE_RISK_DATA();
DROP SCHEMA RISK_DB.RAW CASCADE;
DROP DATABASE RISK_DB;
DROP WAREHOUSE COMPUTE_WH;
```

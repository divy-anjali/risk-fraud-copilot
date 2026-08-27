---
name: setup
description: "Run initial setup of the Risk Fraud Copilot project from scratch or update an existing deployment. Creates warehouse, database, schemas, file formats, stages, raw tables, stored procedures, generates sample data, loads it, builds the curated star schema (sequences, views, dimension/fact tables, SCD2 load procedures), populates the curated layer, sets up the incremental ingestion pipeline (stream + task), and deploys semantic views for Cortex Analyst. Handles migrations from older naming conventions and schema changes. Use when: setting up the project in a new Snowflake account, re-deploying from scratch, updating an existing environment, or onboarding a new environment."
user_invocable: true
---

# Initial Setup

Provision the entire Risk Fraud Copilot environment from zero to a fully operational analytics platform with semantic views — or update an existing deployment to the latest state.

## Architecture

```
Infrastructure → RAW (Landing) → CURATED (Star Schema) → SEMANTICS (Semantic Views)
```

## Pre-flight: Detect Existing State

Before running the workflow, determine if this is a **fresh install** or an **update to an existing deployment**.

```sql
SELECT COUNT(*) AS DB_EXISTS FROM INFORMATION_SCHEMA.DATABASES WHERE DATABASE_NAME = 'RISK_DB';
```

### If updating an existing deployment:

1. **Suspend active tasks** before making changes:
```sql
ALTER TASK IF EXISTS RISK_DB.RAW.RISK_DATA_INGEST_TASK SUSPEND;
```

2. **Drop deprecated/renamed objects** (from older naming conventions):
```sql
-- Old procedure names (pre-SP_ prefix convention)
DROP PROCEDURE IF EXISTS RISK_DB.RAW.GENERATE_RISK_DATA();
DROP PROCEDURE IF EXISTS RISK_DB.RAW.LOAD_RAW_DATA();
DROP PROCEDURE IF EXISTS RISK_DB.RAW.LOAD_NEW_CSV_FILES();
```

3. **Compare local SQL definitions against deployed objects** to detect drift:
   - For each file in `raw/tables/`, `curated/tables/`, `curated/views/`, and `curated/procedures/`:
     - Read the local SQL file
     - Compare columns/logic with what's deployed using `DESCRIBE TABLE`, `SHOW COLUMNS`, or `GET_DDL('PROCEDURE', ...)`
     - If schema has changed (new columns, type changes), generate and execute `ALTER TABLE ... ADD COLUMN` or recreate as needed
   - For procedures and views: always re-execute `CREATE OR REPLACE` — these are safe to overwrite

4. **Handle table schema evolution** — if a raw or curated table has new columns added in the local DDL that don't exist in Snowflake:
```sql
-- Pattern for adding missing columns:
-- ALTER TABLE RISK_DB.RAW.<table_name> ADD COLUMN <col_name> <data_type>;
-- ALTER TABLE RISK_DB.CURATED.<table_name> ADD COLUMN <col_name> <data_type>;
```
   - NEVER drop and recreate tables that contain data unless explicitly confirmed by the user
   - For dimension tables (SCD2): adding columns requires also updating the corresponding `SP_LOAD_DIM_*` procedure and the intermediate view

5. **Re-deploy all procedures and views** (idempotent — always safe):
   - All `CREATE OR REPLACE PROCEDURE` statements
   - All `CREATE OR REPLACE VIEW` statements
   - All `CREATE OR REPLACE STREAM` statements
   - Semantic views via `CREATE OR REPLACE SEMANTIC VIEW`

6. **Resume tasks** after changes are complete:
```sql
ALTER TASK RISK_DB.RAW.RISK_DATA_INGEST_TASK RESUME;
```

### If fresh install:

Proceed with the full workflow below from Step 1.

---

## Workflow

Follow these steps **in exact order** — each depends on the previous.

---

### Step 1: Infrastructure

```sql
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
    WAREHOUSE_SIZE = 'X-Small'
    AUTO_SUSPEND = 300
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    ENABLE_QUERY_ACCELERATION = TRUE
    QUERY_ACCELERATION_MAX_SCALE_FACTOR = 2
    COMMENT = 'General-purpose compute warehouse for risk-fraud pipelines';

CREATE DATABASE IF NOT EXISTS RISK_DB;
CREATE SCHEMA IF NOT EXISTS RISK_DB.RAW;
CREATE SCHEMA IF NOT EXISTS RISK_DB.CURATED;
CREATE SCHEMA IF NOT EXISTS RISK_DB.SEMANTICS;

CREATE FILE FORMAT IF NOT EXISTS RISK_DB.RAW.CSV_FORMAT
    TYPE = 'CSV'
    FIELD_DELIMITER = ','
    RECORD_DELIMITER = '\n'
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    TRIM_SPACE = TRUE
    NULL_IF = ('', 'NULL', 'null')
    COMMENT = 'Standard CSV format for risk data files';

CREATE STAGE IF NOT EXISTS RISK_DB.RAW.POLICIES_STAGE
    DIRECTORY = (ENABLE = TRUE)
    COMMENT = 'Risk and compliance policy documents';

CREATE STAGE IF NOT EXISTS RISK_DB.RAW.RISK_FRAUD_DATA_STAGE
    DIRECTORY = (ENABLE = TRUE)
    COMMENT = 'Banking risk sample data CSVs';
```

**CHECKPOINT**: Verify all infrastructure objects exist before proceeding.

---

### Step 2: Create Raw Tables

Execute all 8 table DDLs from `raw/tables/`:
- `customer_master.sql`
- `account_master.sql`
- `loan_master.sql`
- `loan_performance.sql`
- `transaction_fact.sql`
- `deposit_balances.sql`
- `pep_list.sql`
- `sanctions_watchlist.sql`

Read each file and execute the SQL. All tables include `_SOURCE_FILE STRING` and `_LOADED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()` audit columns.

**CHECKPOINT**: `SHOW TABLES IN SCHEMA RISK_DB.RAW` should return 8 tables.

---

### Step 3: Deploy Raw Layer Stored Procedures

Execute the contents of:
1. `raw/procedures/sp_generate_risk_data.sql` — Python procedure that generates synthetic CSVs + PDFs
2. `raw/procedures/sp_load_raw_data.sql` — SQL procedure that loads CSVs into raw tables with audit columns

**CHECKPOINT**: `SHOW PROCEDURES IN SCHEMA RISK_DB.RAW` should show both procedures.

---

### Step 4: Generate Sample Data

```sql
CALL RISK_DB.RAW.SP_GENERATE_RISK_DATA();
```

Verify files landed:
```sql
SELECT COUNT(*) FROM DIRECTORY(@RISK_DB.RAW.RISK_FRAUD_DATA_STAGE);
-- Expected: 8 CSV files
SELECT COUNT(*) FROM DIRECTORY(@RISK_DB.RAW.POLICIES_STAGE);
-- Expected: 6 PDF files
```

---

### Step 5: Load Data into Raw Tables

```sql
CALL RISK_DB.RAW.SP_LOAD_RAW_DATA();
```

Verify row counts:
```sql
SELECT 'CUSTOMER_MASTER' AS TABLE_NAME, COUNT(*) AS ROW_COUNT FROM RISK_DB.RAW.CUSTOMER_MASTER
UNION ALL SELECT 'ACCOUNT_MASTER', COUNT(*) FROM RISK_DB.RAW.ACCOUNT_MASTER
UNION ALL SELECT 'LOAN_MASTER', COUNT(*) FROM RISK_DB.RAW.LOAN_MASTER
UNION ALL SELECT 'LOAN_PERFORMANCE', COUNT(*) FROM RISK_DB.RAW.LOAN_PERFORMANCE
UNION ALL SELECT 'TRANSACTION_FACT', COUNT(*) FROM RISK_DB.RAW.TRANSACTION_FACT
UNION ALL SELECT 'DEPOSIT_BALANCES', COUNT(*) FROM RISK_DB.RAW.DEPOSIT_BALANCES
UNION ALL SELECT 'PEP_LIST', COUNT(*) FROM RISK_DB.RAW.PEP_LIST
UNION ALL SELECT 'SANCTIONS_WATCHLIST', COUNT(*) FROM RISK_DB.RAW.SANCTIONS_WATCHLIST;
```

**CHECKPOINT**: All tables should have rows. Expected per batch: ~100/150/60/200/1000/150/15/20.

---

### Step 6: Create Curated Layer — Sequences

Execute the contents of `curated/sequences/sequences.sql`:

```sql
CREATE SEQUENCE IF NOT EXISTS RISK_DB.CURATED.SEQ_DIM_CUSTOMER START = 1 INCREMENT = 1;
CREATE SEQUENCE IF NOT EXISTS RISK_DB.CURATED.SEQ_DIM_ACCOUNT START = 1 INCREMENT = 1;
CREATE SEQUENCE IF NOT EXISTS RISK_DB.CURATED.SEQ_DIM_LOAN START = 1 INCREMENT = 1;
CREATE SEQUENCE IF NOT EXISTS RISK_DB.CURATED.SEQ_DIM_PEP START = 1 INCREMENT = 1;
CREATE SEQUENCE IF NOT EXISTS RISK_DB.CURATED.SEQ_DIM_SANCTIONS START = 1 INCREMENT = 1;
```

**CHECKPOINT**: `SHOW SEQUENCES IN SCHEMA RISK_DB.CURATED` should return 5 sequences.

---

### Step 7: Create Curated Layer — Intermediate Views

Execute all 9 view DDLs from `curated/views/`:
- `int_customer.sql` — dedup + IS_HIGH_RISK, AGE_YEARS, DAYS_SINCE_ONBOARDING
- `int_account.sql` — dedup + type casting
- `int_loan.sql` — dedup + Basel parameter casting
- `int_loan_performance.sql` — dedup + IFRS9 casting
- `int_transaction.sql` — dedup + IS_CROSS_BORDER, IS_LARGE_TRANSACTION, boolean casts
- `int_deposit_balance.sql` — dedup + LCR/NSFR casting
- `int_pep.sql` — dedup + type casting
- `int_sanctions.sql` — dedup + type casting
- `int_policy_documents.sql` — parsed policy content

Read each file and execute the SQL. These views perform deduplication, type casting, and add derived business columns on top of raw tables.

**CHECKPOINT**: `SHOW VIEWS IN SCHEMA RISK_DB.CURATED` should return 9 views.

---

### Step 8: Create Curated Layer — Dimension and Fact Tables

Execute all 10 table DDLs from `curated/tables/`:

**Dimension tables** (SCD2 with surrogate keys, EFFECTIVE_FROM/TO, IS_CURRENT, RECORD_HASH):
- `dim_customer.sql`
- `dim_account.sql`
- `dim_loan.sql`
- `dim_pep.sql`
- `dim_sanctions.sql`
- `dim_date.sql` — CTAS generating calendar dates 2023-2026

**Fact tables** (surrogate key references to dimensions):
- `fct_transaction.sql`
- `fct_loan_performance.sql`
- `fct_deposit_balance.sql`

**Reference table**:
- `ref_policy_documents.sql`

Read each file and execute the SQL.

**CHECKPOINT**: `SHOW TABLES IN SCHEMA RISK_DB.CURATED` should return 10 tables.

---

### Step 9: Deploy Curated Layer Load Procedures

Execute all 10 procedure DDLs from `curated/procedures/`:

**Dimension loaders** (SCD2 MERGE — expire changed records, insert new versions via MD5 hash):
- `sp_load_dim_customer.sql`
- `sp_load_dim_account.sql`
- `sp_load_dim_loan.sql`
- `sp_load_dim_pep.sql`
- `sp_load_dim_sanctions.sql`

**Fact loaders** (INSERT from intermediate views, join to dimensions for surrogate keys):
- `sp_load_fct_transaction.sql`
- `sp_load_fct_loan_performance.sql`
- `sp_load_fct_deposit_balance.sql`

**Reference loader**:
- `sp_load_ref_policy_documents.sql`

**Orchestrator** (calls all above in dependency order):
- `sp_refresh_curated_layer.sql`

Read each file and execute the SQL.

**CHECKPOINT**: `SHOW PROCEDURES IN SCHEMA RISK_DB.CURATED` should return 10 procedures.

---

### Step 10: Populate the Curated Layer

```sql
CALL RISK_DB.CURATED.SP_REFRESH_CURATED_LAYER();
```

Verify dimension and fact tables have data:
```sql
SELECT 'DIM_CUSTOMER' AS TABLE_NAME, COUNT(*) AS ROW_COUNT FROM RISK_DB.CURATED.DIM_CUSTOMER
UNION ALL SELECT 'DIM_ACCOUNT', COUNT(*) FROM RISK_DB.CURATED.DIM_ACCOUNT
UNION ALL SELECT 'DIM_LOAN', COUNT(*) FROM RISK_DB.CURATED.DIM_LOAN
UNION ALL SELECT 'DIM_PEP', COUNT(*) FROM RISK_DB.CURATED.DIM_PEP
UNION ALL SELECT 'DIM_SANCTIONS', COUNT(*) FROM RISK_DB.CURATED.DIM_SANCTIONS
UNION ALL SELECT 'DIM_DATE', COUNT(*) FROM RISK_DB.CURATED.DIM_DATE
UNION ALL SELECT 'FCT_TRANSACTION', COUNT(*) FROM RISK_DB.CURATED.FCT_TRANSACTION
UNION ALL SELECT 'FCT_LOAN_PERFORMANCE', COUNT(*) FROM RISK_DB.CURATED.FCT_LOAN_PERFORMANCE
UNION ALL SELECT 'FCT_DEPOSIT_BALANCE', COUNT(*) FROM RISK_DB.CURATED.FCT_DEPOSIT_BALANCE
UNION ALL SELECT 'REF_POLICY_DOCUMENTS', COUNT(*) FROM RISK_DB.CURATED.REF_POLICY_DOCUMENTS;
```

**CHECKPOINT**: All curated tables should have rows. DIM_DATE should have ~1461 rows (4 years).

---

### Step 11: Create CDC Streams (Raw → Curated Incremental)

Execute the contents of `curated/streams/streams.sql`:

```sql
CREATE OR REPLACE STREAM RISK_DB.RAW.STM_CUSTOMER_MASTER ON TABLE RISK_DB.RAW.CUSTOMER_MASTER APPEND_ONLY = FALSE;
CREATE OR REPLACE STREAM RISK_DB.RAW.STM_ACCOUNT_MASTER ON TABLE RISK_DB.RAW.ACCOUNT_MASTER APPEND_ONLY = FALSE;
CREATE OR REPLACE STREAM RISK_DB.RAW.STM_LOAN_MASTER ON TABLE RISK_DB.RAW.LOAN_MASTER APPEND_ONLY = FALSE;
CREATE OR REPLACE STREAM RISK_DB.RAW.STM_PEP_LIST ON TABLE RISK_DB.RAW.PEP_LIST APPEND_ONLY = FALSE;
CREATE OR REPLACE STREAM RISK_DB.RAW.STM_SANCTIONS_WATCHLIST ON TABLE RISK_DB.RAW.SANCTIONS_WATCHLIST APPEND_ONLY = FALSE;
CREATE OR REPLACE STREAM RISK_DB.RAW.STM_TRANSACTION_FACT ON TABLE RISK_DB.RAW.TRANSACTION_FACT APPEND_ONLY = TRUE;
CREATE OR REPLACE STREAM RISK_DB.RAW.STM_LOAN_PERFORMANCE ON TABLE RISK_DB.RAW.LOAN_PERFORMANCE APPEND_ONLY = TRUE;
CREATE OR REPLACE STREAM RISK_DB.RAW.STM_DEPOSIT_BALANCES ON TABLE RISK_DB.RAW.DEPOSIT_BALANCES APPEND_ONLY = TRUE;
CREATE OR REPLACE STREAM RISK_DB.RAW.STM_POLICY_DOCUMENTS ON TABLE RISK_DB.RAW.POLICY_DOCUMENTS APPEND_ONLY = FALSE;
```

These streams enable CDC-based incremental refresh of the curated layer on subsequent data loads.

**CHECKPOINT**: `SHOW STREAMS IN SCHEMA RISK_DB.RAW` should return 10 streams (9 table streams + 1 stage stream from Step 12).

---

### Step 12: Create Stage Stream and Ingestion Task

```sql
CREATE OR REPLACE STREAM RISK_DB.RAW.RISK_DATA_STAGE_STREAM
  ON STAGE RISK_DB.RAW.RISK_FRAUD_DATA_STAGE;

CREATE OR REPLACE TASK RISK_DB.RAW.RISK_DATA_INGEST_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = '5 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('RISK_DB.RAW.RISK_DATA_STAGE_STREAM')
AS
  CALL RISK_DB.RAW.SP_LOAD_RAW_DATA();

ALTER TASK RISK_DB.RAW.RISK_DATA_INGEST_TASK RESUME;
```

**CHECKPOINT**:
```sql
SHOW TASKS IN SCHEMA RISK_DB.RAW;
-- state should be 'started'
```

---

### Step 13: Deploy Semantic Views

Deploy all 4 semantic views from the `semantics/` directory using the manifest at `semantics/risk-fraud-copilot.yaml`.

Run:
```bash
cortex semantic-views deploy --manifest semantics/risk-fraud-copilot.yaml
```

If the CLI deploy is not available, read each `.sv.yaml` file and deploy using `CREATE OR REPLACE SEMANTIC VIEW` DDL:

| Semantic View File | Target Object |
|--------------------|---------------|
| `risk_fraud_signals.sv.yaml` | `RISK_DB.SEMANTICS.RISK_FRAUD_SIGNALS` |
| `regulatory_reporting.sv.yaml` | `RISK_DB.SEMANTICS.REGULATORY_REPORTING` |
| `transaction_account_360.sv.yaml` | `RISK_DB.SEMANTICS.TRANSACTION_ACCOUNT_360` |
| `investigation_facts.sv.yaml` | `RISK_DB.SEMANTICS.INVESTIGATION_FACTS` |

For each file, read the YAML content and execute:
```sql
CREATE OR REPLACE SEMANTIC VIEW <target_object>
  AS $$
  <yaml_content>
  $$;
```

**CHECKPOINT**: Verify all 4 semantic views exist:
```sql
SHOW SEMANTIC VIEWS IN SCHEMA RISK_DB.SEMANTICS;
```

---

## Done

The full Risk Fraud Copilot platform is live:

- **RAW layer**: 8 tables with sample data, auto-ingestion pipeline (stage stream + task)
- **CURATED layer**: Star schema with 5 SCD2 dimensions, 3 fact tables, 1 reference table, 1 date dimension
- **SEMANTICS layer**: 4 semantic views for Cortex Analyst covering risk/fraud signals, regulatory reporting, transaction/account 360, and investigation facts

### Ongoing Operations

To generate and ingest another batch of data:
```sql
CALL RISK_DB.RAW.SP_GENERATE_RISK_DATA();
ALTER STAGE RISK_DB.RAW.RISK_FRAUD_DATA_STAGE REFRESH;
-- Task auto-loads raw tables within 5 minutes
-- Then refresh curated layer:
CALL RISK_DB.CURATED.SP_REFRESH_CURATED_LAYER();
```

To query via Cortex Analyst:
```bash
cortex analyst query "Show me high-risk transactions from the last 30 days" --view=RISK_DB.SEMANTICS.RISK_FRAUD_SIGNALS
```

---

## Object Naming Conventions

All Snowflake objects follow these conventions. When adding new objects, follow the same patterns:

| Object Type | Snowflake Name Pattern | File Name Pattern | Examples |
|-------------|----------------------|-------------------|----------|
| Procedures | `SP_<action>_<target>` | `sp_<action>_<target>.sql` | `SP_LOAD_RAW_DATA`, `SP_GENERATE_RISK_DATA`, `SP_LOAD_DIM_CUSTOMER` |
| Raw Tables | `<ENTITY_NAME>` | `<entity_name>.sql` | `CUSTOMER_MASTER`, `TRANSACTION_FACT` |
| Dimensions | `DIM_<entity>` | `dim_<entity>.sql` | `DIM_CUSTOMER`, `DIM_ACCOUNT` |
| Facts | `FCT_<entity>` | `fct_<entity>.sql` | `FCT_TRANSACTION`, `FCT_LOAN_PERFORMANCE` |
| Reference | `REF_<entity>` | `ref_<entity>.sql` | `REF_POLICY_DOCUMENTS` |
| Int. Views | `INT_<entity>` | `int_<entity>.sql` | `INT_CUSTOMER`, `INT_TRANSACTION` |
| Sequences | `SEQ_DIM_<entity>` | (in `sequences.sql`) | `SEQ_DIM_CUSTOMER`, `SEQ_DIM_ACCOUNT` |
| Table Streams | `STM_<source_table>` | (in `streams.sql`) | `STM_CUSTOMER_MASTER`, `STM_TRANSACTION_FACT` |
| Stage Streams | `<purpose>_STREAM` | `<purpose>_stream.sql` | `RISK_DATA_STAGE_STREAM` |
| Tasks | `<purpose>_TASK` | `<purpose>.sql` | `RISK_DATA_INGEST_TASK` |
| Semantic Views | `<DOMAIN_NAME>` | `<domain_name>.sv.yaml` | `RISK_FRAUD_SIGNALS`, `REGULATORY_REPORTING` |

### When modifying objects:

1. **Renaming an object**: Add the old name to the "Drop deprecated" section in Pre-flight. Create the new object with `CREATE OR REPLACE`.
2. **Adding columns to a table**: Use `ALTER TABLE ADD COLUMN`. Update the corresponding intermediate view and load procedure.
3. **Changing procedure logic**: Just re-execute `CREATE OR REPLACE PROCEDURE` — it's idempotent.
4. **Adding a new semantic view**: Add the `.sv.yaml` file to `semantics/`, add an entry to `semantics/risk-fraud-copilot.yaml`, and deploy.
5. **Adding a new dimension**: Create the sequence, intermediate view, table, and load procedure. Add it to `SP_REFRESH_CURATED_LAYER`. Update any semantic views that reference it.

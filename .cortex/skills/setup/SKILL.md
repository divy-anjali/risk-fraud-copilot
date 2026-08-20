---
name: setup
description: "Run initial setup of the Risk Fraud Copilot project from scratch. Creates warehouse, database, schema, file formats, stages, tables, procedures, generates sample data, loads it, and sets up the incremental ingestion pipeline (stream + task). Use when: setting up the project in a new Snowflake account, re-deploying from scratch, or onboarding a new environment."
user_invocable: true
---

# Initial Setup

Provision the entire Risk Fraud Copilot environment from zero to a live incremental pipeline.

## Workflow

Follow these steps **in exact order** — each depends on the previous.

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

**⚠️ CHECKPOINT**: Verify all infrastructure objects exist before proceeding.

### Step 2: Create Tables

Execute all 8 table DDLs from `raw/tables/`:
- `table_customer_master.sql`
- `table_account_master.sql`
- `table_loan_master.sql`
- `table_loan_performance.sql`
- `table_transaction_fact.sql`
- `table_deposit_balances.sql`
- `table_pep_list.sql`
- `table_sanctions_watchlist.sql`

Read each file and execute the SQL. All tables include `_SOURCE_FILE STRING` and `_LOADED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()` audit columns.

**⚠️ CHECKPOINT**: `SHOW TABLES IN SCHEMA RISK_DB.RAW` should return 8 tables.

### Step 3: Deploy Stored Procedures

Execute the contents of:
1. `raw/procedures/stored_procedure_generate_risk_data.sql` — Python procedure that generates synthetic CSVs + PDFs
2. `raw/procedures/stored_procedure_load_new_csv_files.sql` — SQL procedure that routes CSVs to tables with audit columns

**⚠️ CHECKPOINT**: `SHOW PROCEDURES IN SCHEMA RISK_DB.RAW` should show both procedures.

### Step 4: Generate Sample Data

```sql
CALL RISK_DB.RAW.GENERATE_RISK_DATA();
```

Verify files landed:
```sql
SELECT COUNT(*) FROM DIRECTORY(@RISK_DB.RAW.RISK_FRAUD_DATA_STAGE);
-- Expected: 8 CSV files
SELECT COUNT(*) FROM DIRECTORY(@RISK_DB.RAW.POLICIES_STAGE);
-- Expected: 6 PDF files
```

### Step 5: Load Data into Tables

```sql
CALL RISK_DB.RAW.LOAD_NEW_CSV_FILES();
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

**⚠️ CHECKPOINT**: All tables should have rows. Expected per batch: 100/150/60/200/1000/150/15/20.

### Step 6: Create Stream

```sql
CREATE OR REPLACE STREAM RISK_DB.RAW.RISK_DATA_STAGE_STREAM
  ON STAGE RISK_DB.RAW.RISK_FRAUD_DATA_STAGE;
```

The stream captures files added **after** this point. The initial load (Step 5) was a one-time manual run.

### Step 7: Create and Resume Task

```sql
CREATE OR REPLACE TASK RISK_DB.RAW.RISK_DATA_INGEST_TASK
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = '5 MINUTE'
  WHEN SYSTEM$STREAM_HAS_DATA('RISK_DB.RAW.RISK_DATA_STAGE_STREAM')
AS
  CALL RISK_DB.RAW.LOAD_NEW_CSV_FILES();

ALTER TASK RISK_DB.RAW.RISK_DATA_INGEST_TASK RESUME;
```

**⚠️ FINAL CHECK**:
```sql
SHOW TASKS IN SCHEMA RISK_DB.RAW;
-- state should be 'started'
```

## Done

The pipeline is live. New CSV files landing on `@RISK_DB.RAW.RISK_FRAUD_DATA_STAGE` will be automatically detected and loaded within 5 minutes.

To generate another batch of data:
```sql
CALL RISK_DB.RAW.GENERATE_RISK_DATA();
ALTER STAGE RISK_DB.RAW.RISK_FRAUD_DATA_STAGE REFRESH;
```

The task will pick it up on its next scheduled run.

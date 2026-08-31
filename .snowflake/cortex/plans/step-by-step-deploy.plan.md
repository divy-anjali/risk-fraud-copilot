---
name: "step-by-step-deploy"
created: "2026-08-31T04:40:20.847Z"
status: pending
---

# Step-by-Step Deployment Plan

## What We Are Building

The Risk Fraud Copilot platform, deployed one layer at a time so you can see each piece as it comes together.

## Steps

### Step 1: Build the Foundation (Infrastructure)

Creates the basic building blocks everything else depends on:

- **RISK\_DB** database
- **RAW**, **CURATED**, **SEMANTICS** schemas (the three layers)
- **COMPUTE\_WH** warehouse (X-Small, auto-suspends after 5 min of inactivity)
- **CSV\_FORMAT** file format (tells Snowflake how to read the data files)
- **POLICIES\_STAGE** and **RISK\_FRAUD\_DATA\_STAGE** (storage areas for files)

Files: infrastructure/database.sql, infrastructure/schemas.sql, infrastructure/warehouses.sql, infrastructure/file\_formats.sql, infrastructure/stages.sql

### Step 2: Create the RAW Landing Tables

Creates 9 empty tables that will receive the data files:

- CUSTOMER\_MASTER, ACCOUNT\_MASTER, LOAN\_MASTER, LOAN\_PERFORMANCE, TRANSACTION\_FACT, DEPOSIT\_BALANCES, PEP\_LIST, SANCTIONS\_WATCHLIST, POLICY\_DOCUMENTS

Files: All files under raw/tables/

### Step 3: Create Data Generation and Loading Procedures

Creates 2 stored procedures:

- **SP\_GENERATE\_RISK\_DATA** -- a Python procedure that generates 8 CSVs and 6 PDFs of realistic banking data with embedded fraud scenarios
- **SP\_LOAD\_RAW\_DATA** -- a SQL procedure that loads those files into the raw tables

Files: raw/procedures/sp\_generate\_risk\_data.sql, raw/procedures/sp\_load\_raw\_data.sql

### Step 4: Generate and Load the Sample Data

Runs the two procedures from Step 3. After this step, the raw tables will be filled with data -- 100 customers, 150 accounts, 60 loans, 1000 transactions, etc.

### Step 5: Build the Curated Layer Structure

Creates the entire curated layer without populating it:

- 5 sequences (number generators for surrogate keys)
- 9 intermediate views (cleaning, dedup, derived fields)
- 10 tables (5 SCD2 dimensions, 3 facts, 1 date calendar, 1 policy reference)
- 10 load procedures (SCD2 merge logic, fact inserts, orchestrator)

Files: Everything under curated/

### Step 6: Populate the Curated Layer

Runs SP\_REFRESH\_CURATED\_LAYER, which loads dimensions first, then facts, then the reference table. After this, the full star schema is populated and query-ready.

### Step 7: Set Up Automation

Creates the event-driven pipeline pieces:

- Stage stream (watches for new files arriving)
- Ingest task (auto-triggers loading every 5 minutes)
- 9 CDC streams on raw tables (change detection for future curated-layer automation)

Files: raw/streams/risk\_data\_stage\_stream.sql, raw/tasks/risk\_data\_ingest.sql, curated/streams/streams.sql

### Step 8: Deploy Semantic Views

Deploys 4 semantic views to RISK\_DB.SEMANTICS using the manifest file. These enable plain-English questions via Cortex Analyst.

Files: All files under semantics/

## Verification

After each step, we will run a quick check (SHOW TABLES, SELECT COUNT, etc.) to confirm everything was created correctly before moving on.

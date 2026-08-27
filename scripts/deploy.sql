-- ============================================================
-- Deploy script for risk-fraud-copilot
-- Run in dependency order: infrastructure → raw → silver → gold
-- ============================================================

-- 1. Infrastructure
-- !source infrastructure/database.sql
-- !source infrastructure/schemas.sql
-- !source infrastructure/file_formats.sql
-- !source infrastructure/stages.sql

-- 2. Raw layer - Tables
-- !source raw/tables/table_customer_master.sql
-- !source raw/tables/table_account_master.sql
-- !source raw/tables/table_loan_master.sql
-- !source raw/tables/table_loan_performance.sql
-- !source raw/tables/table_transaction_fact.sql
-- !source raw/tables/table_deposit_balances.sql
-- !source raw/tables/table_pep_list.sql
-- !source raw/tables/table_sanctions_watchlist.sql
-- !source raw/tables/table_policy_documents.sql

-- 3. Raw layer - Procedures
-- !source raw/procedures/stored_procedure_generate_risk_data.sql
-- !source raw/procedures/stored_procedure_load_raw_data.sql

-- 4. Raw layer - Streams
-- !source raw/streams/stream_risk_data_stage.sql

-- 5. Raw layer - Tasks (must come after streams + procedures)
-- !source raw/tasks/task_risk_data_ingest.sql

-- 6. Silver layer - Dynamic Tables (deduplication, type casting, business keys)
-- TODO: Add silver layer objects here

-- 7. Gold layer - Views and aggregates (business-ready)
-- TODO: Add gold layer objects here

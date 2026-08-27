-- ============================================================
-- Deploy script for risk-fraud-copilot
-- Run in dependency order: infrastructure → raw → curated → semantics
-- ============================================================

-- 1. Infrastructure
-- !source infrastructure/database.sql
-- !source infrastructure/schemas.sql
-- !source infrastructure/file_formats.sql
-- !source infrastructure/stages.sql

-- 2. Raw layer - Tables
-- !source raw/tables/customer_master.sql
-- !source raw/tables/account_master.sql
-- !source raw/tables/loan_master.sql
-- !source raw/tables/loan_performance.sql
-- !source raw/tables/transaction_fact.sql
-- !source raw/tables/deposit_balances.sql
-- !source raw/tables/pep_list.sql
-- !source raw/tables/sanctions_watchlist.sql
-- !source raw/tables/policy_documents.sql

-- 3. Raw layer - Procedures
-- !source raw/procedures/sp_generate_risk_data.sql
-- !source raw/procedures/sp_load_raw_data.sql

-- 4. Raw layer - Streams
-- !source raw/streams/risk_data_stage_stream.sql

-- 5. Raw layer - Tasks (must come after streams + procedures)
-- !source raw/tasks/risk_data_ingest.sql

-- 6. Curated layer - Sequences (surrogate keys for dimensions)
-- !source curated/sequences/sequences.sql

-- 7. Curated layer - Intermediate Views (dedup, type casting, derived columns)
-- !source curated/views/int_customer.sql
-- !source curated/views/int_account.sql
-- !source curated/views/int_loan.sql
-- !source curated/views/int_loan_performance.sql
-- !source curated/views/int_transaction.sql
-- !source curated/views/int_deposit_balance.sql
-- !source curated/views/int_pep.sql
-- !source curated/views/int_sanctions.sql
-- !source curated/views/int_policy_documents.sql

-- 8. Curated layer - Dimension and Fact Tables (star schema)
-- !source curated/tables/dim_customer.sql
-- !source curated/tables/dim_account.sql
-- !source curated/tables/dim_loan.sql
-- !source curated/tables/dim_pep.sql
-- !source curated/tables/dim_sanctions.sql
-- !source curated/tables/dim_date.sql
-- !source curated/tables/fct_transaction.sql
-- !source curated/tables/fct_loan_performance.sql
-- !source curated/tables/fct_deposit_balance.sql
-- !source curated/tables/ref_policy_documents.sql

-- 9. Curated layer - Load Procedures (SCD2 merge + fact inserts)
-- !source curated/procedures/sp_load_dim_customer.sql
-- !source curated/procedures/sp_load_dim_account.sql
-- !source curated/procedures/sp_load_dim_loan.sql
-- !source curated/procedures/sp_load_dim_pep.sql
-- !source curated/procedures/sp_load_dim_sanctions.sql
-- !source curated/procedures/sp_load_fct_transaction.sql
-- !source curated/procedures/sp_load_fct_loan_performance.sql
-- !source curated/procedures/sp_load_fct_deposit_balance.sql
-- !source curated/procedures/sp_load_ref_policy_documents.sql
-- !source curated/procedures/sp_refresh_curated_layer.sql

-- 10. Curated layer - CDC Streams (raw table change capture)
-- !source curated/streams/streams.sql

-- 11. Semantics layer - Semantic Views (deploy via cortex CLI or CREATE SEMANTIC VIEW)
-- cortex semantic-views deploy --manifest semantics/risk-fraud-copilot.yaml

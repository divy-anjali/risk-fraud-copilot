-- Cortex Search Service over risk & compliance policy documents.
-- Indexes REF_POLICY_DOCUMENTS.FULL_CONTENT for semantic retrieval by the
-- RISK_FRAUD_COPILOT agent (policy_search tool).
--
-- Note: the ON clause takes a bare column name (FULL_CONTENT), not a qualified
-- table reference. Run USE SCHEMA first, or a qualified name in ON fails with
-- "unexpected '.'". The source table is specified in the AS (<query>) clause.

USE SCHEMA RISK_DB.SEMANTICS;

CREATE OR REPLACE CORTEX SEARCH SERVICE POLICY_SEARCH
  ON FULL_CONTENT
  ATTRIBUTES POLICY_NAME, CLASSIFICATION
  WAREHOUSE = COMPUTE_WH
  TARGET_LAG = '1 hour'
  AS (
    SELECT POLICY_ID, POLICY_NAME, CLASSIFICATION, PURPOSE, FULL_CONTENT
    FROM RISK_DB.CURATED.REF_POLICY_DOCUMENTS
  );

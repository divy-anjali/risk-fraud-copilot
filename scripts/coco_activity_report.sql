-- =============================================================================
-- CoCo activity report: how much of the Snowflake work was done through
-- Cortex Code (CoCo).
--
-- Each query is attributed to the client application of its session
-- (SNOWFLAKE.ACCOUNT_USAGE.SESSIONS.CLIENT_ENVIRONMENT:APPLICATION):
--   COCO_DIRECT    - CoCo's own SQL tool: cortex_code_desktop, cortex_code_sandbox,
--                    and Snowsight's embedded Cortex Code (snowsight_cortex_code)
--   COCO_LAUNCHED  - Python run by CoCo from the terminal: deploy scripts, tests,
--                    local Streamlit (PythonConnector / streamlit / PythonSnowpark)
--   SNOWSIGHT      - the Snowsight web UI, including the deployed Streamlit app
--   OTHER          - anything else
--
-- COCO_LAUNCHED is an inference: these clients are what CoCo's terminal commands
-- use in this project, but a person could also run them by hand.
--
-- ACCOUNT_USAGE views lag by up to ~45 minutes. Run as ACCOUNTADMIN.
-- =============================================================================
SET PROJECT_USER = 'DIBUPIHU';

-- 1. Sessions by client --------------------------------------------------------
WITH s AS (
    SELECT SESSION_ID, CREATED_ON,
           COALESCE(NULLIF(PARSE_JSON(CLIENT_ENVIRONMENT):APPLICATION::STRING, ''), NULLIF(CLIENT_APPLICATION_ID, ''), 'unknown') AS APP
    FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS
    WHERE USER_NAME = $PROJECT_USER
)
SELECT CASE
         WHEN APP ILIKE 'cortex_code%' OR APP ILIKE '%snowsight_cortex_code%' THEN 'COCO_DIRECT'
         WHEN APP IN ('PythonConnector', 'streamlit') OR APP ILIKE 'PythonSnowpark%' THEN 'COCO_LAUNCHED'
         WHEN APP ILIKE 'Snowflake Web App%' OR APP = 'Snowsight' THEN 'SNOWSIGHT'
         ELSE 'OTHER'
       END AS CHANNEL,
       APP,
       COUNT(*) AS SESSIONS,
       MIN(CREATED_ON) AS FIRST_SEEN,
       MAX(CREATED_ON) AS LAST_SEEN
FROM s
GROUP BY 1, 2
ORDER BY CHANNEL, SESSIONS DESC;

-- 2. Queries per day by channel, with DDL counts ---------------------------------
WITH s AS (
    SELECT SESSION_ID,
           COALESCE(NULLIF(PARSE_JSON(CLIENT_ENVIRONMENT):APPLICATION::STRING, ''), NULLIF(CLIENT_APPLICATION_ID, ''), 'unknown') AS APP
    FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS
    WHERE USER_NAME = $PROJECT_USER
),
q AS (
    SELECT DATE(h.START_TIME) AS DAY, h.QUERY_TYPE, h.EXECUTION_STATUS,
           CASE
             WHEN s.APP ILIKE 'cortex_code%' OR s.APP ILIKE '%snowsight_cortex_code%' THEN 'COCO_DIRECT'
             WHEN s.APP IN ('PythonConnector', 'streamlit') OR s.APP ILIKE 'PythonSnowpark%' THEN 'COCO_LAUNCHED'
             WHEN s.APP ILIKE 'Snowflake Web App%' OR s.APP = 'Snowsight' THEN 'SNOWSIGHT'
             ELSE 'OTHER'
           END AS CHANNEL
    FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY h
    LEFT JOIN s ON s.SESSION_ID = h.SESSION_ID
    WHERE h.USER_NAME = $PROJECT_USER
)
SELECT DAY, CHANNEL,
       COUNT(*) AS QUERIES,
       COUNT_IF(QUERY_TYPE LIKE 'CREATE%' OR QUERY_TYPE LIKE 'ALTER%') AS DDL,
       COUNT_IF(QUERY_TYPE IN ('INSERT', 'MERGE', 'COPY', 'UPDATE', 'DELETE')) AS DML,
       COUNT_IF(QUERY_TYPE = 'CALL') AS PROCEDURE_CALLS,
       COUNT_IF(EXECUTION_STATUS = 'FAIL') AS FAILED
FROM q
GROUP BY 1, 2
ORDER BY 1, 2;

-- 3. Project objects created, in order, with the channel that created them -------
--    Semantic-view CALLs with a trailing TRUE (verify_only dry-runs) create
--    nothing, so they are excluded.
WITH s AS (
    SELECT SESSION_ID,
           COALESCE(NULLIF(PARSE_JSON(CLIENT_ENVIRONMENT):APPLICATION::STRING, ''), NULLIF(CLIENT_APPLICATION_ID, ''), 'unknown') AS APP
    FROM SNOWFLAKE.ACCOUNT_USAGE.SESSIONS
    WHERE USER_NAME = $PROJECT_USER
)
SELECT h.START_TIME,
       CASE
         WHEN s.APP ILIKE 'cortex_code%' OR s.APP ILIKE '%snowsight_cortex_code%' THEN 'COCO_DIRECT'
         WHEN s.APP IN ('PythonConnector', 'streamlit') OR s.APP ILIKE 'PythonSnowpark%' THEN 'COCO_LAUNCHED'
         WHEN s.APP ILIKE 'Snowflake Web App%' OR s.APP = 'Snowsight' THEN 'SNOWSIGHT'
         ELSE 'OTHER'
       END AS CHANNEL,
       h.QUERY_TYPE,
       LEFT(REGEXP_REPLACE(h.QUERY_TEXT, '\\s+', ' '), 140) AS STATEMENT
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY h
LEFT JOIN s ON s.SESSION_ID = h.SESSION_ID
WHERE h.USER_NAME = $PROJECT_USER
  AND h.EXECUTION_STATUS = 'SUCCESS'
  AND (h.QUERY_TYPE LIKE 'CREATE%'
       OR (h.QUERY_TYPE = 'CALL' AND h.QUERY_TEXT ILIKE '%SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML%'
           AND NOT REGEXP_LIKE(h.QUERY_TEXT, '.*,\\s*TRUE\\s*\\)\\s*;?\\s*', 'is')))
  AND (h.QUERY_TEXT ILIKE '%RISK_DB%' OR h.QUERY_TEXT ILIKE '%COPILOT_PUBLIC%'
       OR h.DATABASE_NAME = 'RISK_DB')
ORDER BY h.START_TIME;

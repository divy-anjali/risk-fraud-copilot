## Context

Repo state verified read-only:
- On `main`, up to date with `origin/main`, remote is `https://github.com/divy-anjali/risk-fraud-copilot.git`.
- Working tree is clean. The policy-generator edit from earlier in this session **did not persist** (rolled back on mode switch), so there is nothing half-done to rescue.
- Two untracked files: the plan `.md` files from this session. Plan files are a tracked convention here (3 already committed under `.snowflake/cortex/plans/`), so they belong in the commit.
- No `.gitignore`; `.venv/` is already excluded by some other mechanism so it will not pollute the commit.
- Existing branch naming convention: `feat/<snake_case>` (`feat/build_sematic_views`, `feat/populate_synthetic_data`, `feat/update_setup_skill`) and `fix/<snake_case>`.

**Blocker:** the read-only Restricted Session Scope is currently active, so every `CREATE` will fail. Turn off the read-only toggle in CoCo Desktop before step 3 begins. Steps 1-2 and the file edits in steps 4-5 work regardless; only the Snowflake object creation and verification need it off.

## Implementation steps

1. **Create the feature branch off current `main`.**
   ```
   git checkout -b feat/add_cortex_agent_and_streamlit_app
   ```
   No stash needed since the tree is clean. All subsequent work lands on this branch.

2. **Confirm the branch and clean base.** `git status` should report the new branch with only the two untracked plan files.

3. **Re-apply and deploy the enriched policy generator.** Rewrite the `POLICIES` dict in [raw/procedures/sp_generate_risk_data.sql](raw/procedures/sp_generate_risk_data.sql) so each of the 6 policies carries several substantive paragraphs (concrete thresholds, escalation rules, regulatory references) plus the `Classification: <LEVEL>` line the loader regex in [raw/procedures/sp_load_raw_data.sql](raw/procedures/sp_load_raw_data.sql) already expects but never finds. Then redeploy the procedure, regenerate, `ALTER STAGE ... REFRESH` both stages, reload RAW, and refresh the curated layer. Requires the read-only toggle off.

4. **Create the Cortex Search Service.** `USE SCHEMA RISK_DB.SEMANTICS` first, then `CREATE OR REPLACE CORTEX SEARCH SERVICE POLICY_SEARCH ON FULL_CONTENT ATTRIBUTES POLICY_NAME, CLASSIFICATION WAREHOUSE = COMPUTE_WH TARGET_LAG = '1 hour' AS (SELECT ...)`. `CLASSIFICATION` becomes a usable facet once step 3 populates it. The `ON` clause takes a bare column name, not a qualified table, or it fails with `unexpected '.'`.

5. **Create the Cortex Agent** `RISK_DB.SEMANTICS.RISK_FRAUD_COPILOT` via `CREATE OR REPLACE AGENT ... FROM SPECIFICATION $$ <json> $$` (plain `$$`, not the labelled `$spec$` form which fails to parse). Five tools: four `cortex_analyst_text_to_sql` tools, one per semantic view, plus one `cortex_search` tool over `POLICY_SEARCH`. Orchestration instructions encode Signal -> Evidence -> Finding.

6. **Codify both objects in the repo** as `semantics/policy_search.sql` and `semantics/risk_fraud_copilot.agent.sql`, register them in [scripts/deploy.sql](scripts/deploy.sql) as sections 12-13, and extend [.cortex/skills/setup/SKILL.md](.cortex/skills/setup/SKILL.md) with matching steps. These lived only as ad-hoc SQL on the previous account, which is exactly why they were lost in the account move.

7. **Make [streamlit_app.py](streamlit_app.py) dual-mode.** Replace the hardcoded `connection_name="hmxhrph-kh35929"` with a helper preferring `get_active_session()` (works inside Snowflake) and falling back to `snowflake.connector.connect(connection_name="qbgiwtu-dk32675", ...)` locally. Rework `run_query` accordingly. All pages, filters, KPIs, and charts stay as-is.

8. **Deploy as Streamlit-in-Snowflake.** Add `environment.yml` (streamlit, snowflake-snowpark-python, pandas), create `RISK_DB.SEMANTICS.STREAMLIT_STAGE`, PUT the app files via a short Snowpark script run from the local `.venv` (no `snow` CLI on this machine), then `CREATE OR REPLACE STREAMLIT ... FROM '@...STREAMLIT_STAGE' MAIN_FILE = 'streamlit_app.py' QUERY_WAREHOUSE = COMPUTE_WH` followed by `ALTER STREAMLIT ... ADD LIVE VERSION FROM LAST` (required: per the docs the app is not live until this runs).

9. **Commit in logical chunks** so the PR reads cleanly:
   ```
   git add raw/procedures/sp_generate_risk_data.sql
   git commit -m "Enrich policy documents with substantive regulatory content"

   git add semantics/policy_search.sql semantics/risk_fraud_copilot.agent.sql scripts/deploy.sql .cortex/skills/setup/SKILL.md
   git commit -m "Add Cortex Search Service and Cortex Agent as tracked artifacts"

   git add streamlit_app.py environment.yml
   git commit -m "Make Streamlit app dual-mode for Streamlit-in-Snowflake deployment"

   git add .snowflake/cortex/plans/
   git commit -m "Add session plan artifacts"
   ```

10. **Push and open the pull request.**
    ```
    git push -u origin feat/add_cortex_agent_and_streamlit_app
    gh pr create --title "Add Cortex Agent, policy search, and SiS dashboard deployment" --body "..."
    ```
    If `gh` is unavailable, the push output prints a GitHub URL that opens the PR form directly.

## Verification

Snowflake objects:
- `SHOW CORTEX SEARCH SERVICES IN SCHEMA RISK_DB.SEMANTICS` -> `POLICY_SEARCH`, serving and indexing state ACTIVE, 6 rows.
- `SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW('RISK_DB.SEMANTICS.POLICY_SEARCH', '{"query":"structuring threshold","limit":3}')` -> returns the Transaction Monitoring policy with the seven-day / USD 9,000-9,999 language.
- `SELECT POLICY_NAME, CLASSIFICATION, CONTENT_LENGTH_CHARS FROM RISK_DB.CURATED.REF_POLICY_DOCUMENTS` -> `CLASSIFICATION` populated (INTERNAL / CONFIDENTIAL) and content length in the thousands, not 133-176.
- `DESCRIBE AGENT RISK_DB.SEMANTICS.RISK_FRAUD_COPILOT` -> spec parses, 5 tools, `tool_resources` referencing real semantic views and the search service.
- `SHOW STREAMLITS IN SCHEMA RISK_DB.SEMANTICS` -> app present with a live version.

Application:
- Local smoke test: `.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.port 8505` renders both pages against this account, confirming the fallback branch still works.
- SiS: open the app in Snowsight under Projects > Streamlit and confirm both pages render on the `get_active_session()` path.

Agent conversation (yours to run, not mine):
- Snowsight > AI & ML > Agents > `RISK_FRAUD_COPILOT`. There is no SQL invocation path for agents (no `INVOKE_AGENT` function, and `<agent>!RUN(...)` does not exist), so I can verify configuration but cannot exercise a conversational round-trip. Test questions spanning signal, evidence, finding, regulatory, and combined retrieval will be handed over.

Git:
- `git log --oneline origin/main..HEAD` -> the four commits.
- `git status` -> clean after push.

## Critical Files

- [raw/procedures/sp_generate_risk_data.sql](raw/procedures/sp_generate_risk_data.sql) - `POLICIES` dict is the source of the thin policy text and the missing `Classification:` line
- [streamlit_app.py](streamlit_app.py) - connection layer must become dual-mode; currently hardcoded to the old account
- [scripts/deploy.sql](scripts/deploy.sql) - deployment manifest to extend with search service and agent
- [.cortex/skills/setup/SKILL.md](.cortex/skills/setup/SKILL.md) - setup skill so a future account move recreates the full stack
- [curated/tables/ref_policy_documents.sql](curated/tables/ref_policy_documents.sql) - defines `FULL_CONTENT` and `CLASSIFICATION` that the Search Service indexes
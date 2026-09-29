## Context

### Git state (verified)
- On `main`, up to date with `origin/main` at commit `76a306a`. Remote is `https://github.com/divy-anjali/risk-fraud-copilot.git`.
- Working tree is clean apart from two untracked files: `.snowflake/cortex/plans/cortex-agent-and-streamlit-consumption-layer.plan.md` and `.snowflake/cortex/plans/deploy-risk-fraud-copilot-fresh-account.plan.md`.
- Existing branch convention is `feat/<snake_case>` and `fix/<snake_case>` (`feat/build_sematic_views`, `fix/add_missing_objects`), so the new branch should be `feat/add_cortex_agent_and_streamlit_app`.
- Plan files **are** tracked in this repo (3 already committed under `.snowflake/cortex/plans/`), so committing the 2 new ones matches convention.

### Correction on earlier work
My edit to the `POLICIES` dict in [raw/procedures/sp_generate_risk_data.sql](raw/procedures/sp_generate_risk_data.sql) **did not persist** — the file is back to its original 285 lines and `git diff` is empty. Nothing has been implemented yet, on disk or in Snowflake. Starting the branch from a genuinely clean tree.

### Two repo hygiene issues found
1. **There is no `.gitignore` at all.** The `.venv/` directory escapes tracking only because `uv` wrote `.venv/.gitignore` containing `*`. Nothing stops `__pycache__/`, `*.pyc`, or stray artifacts from being committed.
2. **`.streamlit/secrets.toml` is tracked and committed.** Its current content is just `connection_name = "hmxhrph-kh35929"` — not an actual credential, so there is nothing to rotate. But a file named `secrets.toml` committed to a GitHub repo is a bad pattern to leave in place, and this one is now stale (it points at the retired account). Step 5 of the implementation removes Streamlit's `st.connection` dependency entirely, which makes the file dead weight.

### Blocker: session is read-only again
`SYS_CONTEXT('SNOWFLAKE$SESSION','ACTIVE_RESTRICTED_SESSION_SCOPES')` shows the runtime-managed scope is back to `data read` / `usage` / `object discovery` only. A `CREATE OR REPLACE PROCEDURE` attempt just failed with `Insufficient privileges ... does not include OWNERSHIP access`. **All Snowflake DDL steps (1, 2, 3, 7) are blocked until you turn the read-only toggle off again.** Steps 4, 5, 6a and the git steps are pure file edits and can proceed regardless.

```mermaid
flowchart LR
  A[Create branch] --> B[Repo hygiene: gitignore, drop secrets.toml]
  B --> C[Enrich policies + reload]
  C --> D[POLICY_SEARCH service]
  D --> E[RISK_FRAUD_COPILOT agent]
  E --> F[Codify DDL in repo]
  F --> G[Dual-mode streamlit_app.py]
  G --> H[Deploy as SiS]
  H --> I[Commit, push, open PR]
```

## Implementation steps

1. **Create the feature branch.**
   ```bash
   git checkout -b feat/add_cortex_agent_and_streamlit_app
   ```
   No stash needed — the tree is clean. The 2 untracked plan files carry over to the new branch automatically.

2. **Add repo hygiene.** Create a `.gitignore` covering `__pycache__/`, `*.pyc`, `.venv/`, `.streamlit/secrets.toml`, and `*.egg-info/`. Remove the tracked stale secrets file with `git rm --cached .streamlit/secrets.toml` so it stops being published but stays on disk.

3. **Enrich the policy documents** (requires write access). Rewrite the `POLICIES` dict in [raw/procedures/sp_generate_risk_data.sql](raw/procedures/sp_generate_risk_data.sql) so each of the 6 policies emits 4-6 substantive sections with concrete thresholds, escalation steps and regulatory references, and emits the `Classification: <LEVEL>` line the loader regex in [raw/procedures/sp_load_raw_data.sql](raw/procedures/sp_load_raw_data.sql) already expects (currently `CLASSIFICATION` is NULL for all 6 rows because that line is never written). Redeploy the procedure, regenerate, `ALTER STAGE ... REFRESH` both stages, truncate and reload `POLICY_DOCUMENTS`, refresh the curated layer.

4. **Create the Cortex Search Service** `RISK_DB.SEMANTICS.POLICY_SEARCH` (requires write access). `USE SCHEMA RISK_DB.SEMANTICS` first — the `ON` clause takes a bare column name, and a qualified table there fails with `unexpected '.'`. Index `FULL_CONTENT`, attribute `POLICY_NAME`, `WAREHOUSE = COMPUTE_WH`, `TARGET_LAG = '1 hour'`.

5. **Create the Cortex Agent** `RISK_DB.SEMANTICS.RISK_FRAUD_COPILOT` (requires write access) via `CREATE OR REPLACE AGENT ... FROM SPECIFICATION $$ <json> $$` — plain `$$`, since the labelled `$spec$` form fails to parse. Four `cortex_analyst_text_to_sql` tools (one per semantic view) plus one `cortex_search` tool, with orchestration instructions encoding Signal -> Evidence -> Finding.

6. **Codify both objects in the repo.** Add `semantics/policy_search.sql` and `semantics/risk_fraud_copilot.agent.sql`, register them as sections 12-13 in [scripts/deploy.sql](scripts/deploy.sql), and extend [.cortex/skills/setup/SKILL.md](.cortex/skills/setup/SKILL.md) with matching steps. These objects previously existed only as ad-hoc SQL, which is exactly why they were lost in the account move.

7. **Make [streamlit_app.py](streamlit_app.py) dual-mode.** Replace the hardcoded `connection_name="hmxhrph-kh35929"` with a helper preferring `get_active_session()` (works inside Snowflake) and falling back to `snowflake.connector.connect(connection_name="qbgiwtu-dk32675", ...)` locally. Add `environment.yml` for the SiS warehouse runtime. All pages, filters, KPIs and charts unchanged.

8. **Deploy as Streamlit-in-Snowflake** (requires write access). No `snow` CLI on this machine, so: create `RISK_DB.SEMANTICS.STREAMLIT_STAGE`, PUT the app files via a short Snowpark script run from the local `.venv` (snowpark 1.54 confirmed working), then `CREATE OR REPLACE STREAMLIT ... FROM '@...STREAMLIT_STAGE' MAIN_FILE = 'streamlit_app.py' QUERY_WAREHOUSE = COMPUTE_WH`, followed by `ALTER STREAMLIT ... ADD LIVE VERSION FROM LAST` — the docs are explicit that the app is not live without it.

9. **Commit and push.** One commit per logical unit (hygiene / policy enrichment / search+agent / streamlit), then:
   ```bash
   git push -u origin feat/add_cortex_agent_and_streamlit_app
   gh pr create --title "..." --body "..."
   ```
   I will not push or open the PR without your explicit go-ahead.

## Verification

Full verification guide will be handed over at the end. Summary of what gets checked:

| What | How |
|---|---|
| Policy enrichment | `SELECT POLICY_NAME, CLASSIFICATION, CONTENT_LENGTH_CHARS FROM RISK_DB.CURATED.REF_POLICY_DOCUMENTS` -> `CLASSIFICATION` populated, lengths in the thousands not ~150 |
| Search service | `SHOW CORTEX SEARCH SERVICES IN SCHEMA RISK_DB.SEMANTICS` -> ACTIVE/ACTIVE, 6 rows indexed |
| Search relevance | `SNOWFLAKE.CORTEX.SEARCH_PREVIEW('RISK_DB.SEMANTICS.POLICY_SEARCH', '{"query":"structuring threshold","limit":3}')` returns the Transaction Monitoring policy |
| Agent config | `DESCRIBE AGENT RISK_DB.SEMANTICS.RISK_FRAUD_COPILOT` -> spec parses, 5 tools with valid `tool_resources` |
| Agent behaviour | **You must do this in Snowsight** (AI & ML > Agents). There is no SQL invocation path for agents — no `INVOKE_AGENT`, no `<agent>!RUN(...)`. I will supply test questions but cannot run the conversation myself. |
| Streamlit (SiS) | `SHOW STREAMLITS IN SCHEMA RISK_DB.SEMANTICS` -> live version set; open the Snowsight URL |
| Streamlit (local) | `.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.port 8505` -> both pages render, confirming the fallback path survived the refactor |
| Git | `git log --oneline origin/main..HEAD` and `git diff --stat origin/main...HEAD` before pushing |

## Critical Files

- [streamlit_app.py](streamlit_app.py) - connection layer must become dual-mode; currently pinned to the retired account
- [raw/procedures/sp_generate_risk_data.sql](raw/procedures/sp_generate_risk_data.sql) - `POLICIES` dict is the source of the thin policy text and the missing `Classification:` line
- [scripts/deploy.sql](scripts/deploy.sql) - manifest to extend with the search service and agent
- [.cortex/skills/setup/SKILL.md](.cortex/skills/setup/SKILL.md) - setup skill to extend so a future account move recreates the whole stack
- `.gitignore` - does not exist yet; needed to stop `secrets.toml` and Python artifacts being published
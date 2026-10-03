# Plan: Public URL for the Streamlit App

## Context

**How the app connects today** ([streamlit_app.py](streamlit_app.py)):
- Inside Snowflake, it uses `get_active_session()`.
- Locally, `get_local_connection()` (lines 67-75) connects with `connection_name="qbgiwtu-dk32675"`. That relies on your browser OAuth login and a `connections.toml` on your machine. Neither exists on a hosted server, so the connection must change.
- Cortex Analyst REST already authenticates with the connector's session token (`con.rest.token`, line 253). That token works with any login method, so key-pair auth needs no change there.

**What the app accesses:**
- It only reads. It queries `RISK_DB.CURATED.*` tables, the 4 semantic views in `RISK_DB.SEMANTICS`, `POLICY_SEARCH` (via `SEARCH_PREVIEW`) and `SNOWFLAKE.CORTEX.COMPLETE`.
- It never writes, so a read-only role is enough.

**Findings that matter once the app is public:**
1. **SQL injection risk.** `_sql_literal` (line 200) only doubles single quotes. Snowflake also treats backslash as an escape character inside quoted strings. Input like `\'` therefore breaks out of the literal in `cortex_complete` and `search_policies`. Both take free text from the user. That is acceptable while only you use the app, but not on a public URL. Fix: use bind parameters instead of string interpolation.
2. **Dependency-file conflict.** The repo root has `environment.yml`, which the Snowflake-hosted app needs, and `pyproject.toml` with `requires-python >=3.14`. Community Cloud may pick one of these over a root `requirements.txt`, and may not offer Python 3.14. Fix: give the cloud deployment its own folder with its own `requirements.txt`, which Community Cloud checks before the repo root. I'll confirm this order against the Streamlit docs before building.
3. **Credentials.** `.streamlit/secrets.toml` is already in `.gitignore`. The private key never goes into the repo; it is pasted into the Community Cloud secrets settings.
4. **MFA.** A `TYPE = SERVICE` user with key-pair auth is not affected by the MFA enforcement rollout.

## Implementation steps

### 1. Snowflake objects for the public app (run as ACCOUNTADMIN)
- `COPILOT_PUBLIC_WH`: XSMALL, `AUTO_SUSPEND = 60`, `INITIALLY_SUSPENDED = TRUE`.
- Resource monitor `COPILOT_PUBLIC_RM`: `CREDIT_QUOTA = 10`, monthly, notify at 75%, `SUSPEND_IMMEDIATE` at 100%. It is assigned to this warehouse only, so `COMPUTE_WH` and your own work are unaffected.
- Role `COPILOT_PUBLIC_ROLE` with:
  - USAGE on the warehouse, `RISK_DB`, `RISK_DB.CURATED` and `RISK_DB.SEMANTICS`
  - SELECT on all tables and views in CURATED
  - SELECT on the 4 semantic views
  - USAGE on `POLICY_SEARCH`
  - database role `SNOWFLAKE.CORTEX_USER`
  - no access to RAW and no write privileges
- User `COPILOT_PUBLIC_SVC`: `TYPE = SERVICE`, `RSA_PUBLIC_KEY = <public key>`, `DEFAULT_ROLE = COPILOT_PUBLIC_ROLE`, `DEFAULT_WAREHOUSE = COPILOT_PUBLIC_WH`.
- Save the DDL as `scripts/public_app_access.sql` so it can be repeated and reviewed.

### 2. Generate the key pair locally
- Generate an RSA 2048 key pair with Python `cryptography` in `.venv`.
- Write the private key to `.streamlit/secrets.toml`, which is gitignored, for local testing.
- Put only the public key into the `CREATE USER` statement.
- Never print the private key in chat or commit it.

### 3. App changes in [streamlit_app.py](streamlit_app.py)
- `get_local_connection()`: if `st.secrets` contains a `[snowflake]` section, connect with key-pair auth (load the PEM with `cryptography` and pass `private_key` as DER bytes). Otherwise fall back to the current `connection_name`, so your local workflow keeps working. Wrap the `st.secrets` lookup in try/except, because it raises an error when no secrets file exists.
- `run_query(sql, params=None)`: pass `params` to `cursor.execute(sql, params)` locally and to `session.sql(sql, params=...)` in Snowflake.
- `cortex_complete` and `search_policies`: replace the `'{_sql_literal(...)}'` interpolation with `?` / `%s` binds. Remove `_sql_literal` if nothing else uses it.
- Usage cap: allow 20 Copilot / Report Builder calls per browser session (tracked in `st.session_state`) and show a friendly message once reached. Cortex AI is billed separately from warehouse compute, so the resource monitor does not cover it; this cap is the guard for that cost.

### 4. Cloud entrypoint
- `cloud/app.py`: a thin wrapper that runs the root `streamlit_app.py` via `runpy.run_path`, so there is still one source of truth.
- `cloud/requirements.txt`: `streamlit`, `pandas`, `altair`, `snowflake-connector-python`, `cryptography`, `requests`.
- `.streamlit/secrets.toml.example`: shows the expected `[snowflake]` keys (account, user, private_key, role, warehouse, database) with placeholder values.
- The Snowflake-hosted app's files (`environment.yml`, `scripts/deploy_streamlit.py`) are not changed.

### 5. Deploy on Community Cloud (you do this; it needs your GitHub login)
- Go to share.streamlit.io, choose New app, select repo `divy-anjali/risk-fraud-copilot`, branch `main`, main file `cloud/app.py`.
- Under Advanced settings, choose Python 3.12 and paste the contents of `secrets.toml`.
- Deploy, then copy the `*.streamlit.app` URL for the submission form.

### 6. Commit and push
- Push the code, the SQL script and the example secrets file. Confirm `secrets.toml` and the key files are not staged before committing.

## Verification
- **Grants:** connect as `COPILOT_PUBLIC_SVC` and check that SELECT on a CURATED table works, SELECT on a RAW table is denied, and `CREATE TABLE` is denied.
- **Local run with key-pair secrets:** run headless `AppTest` (the same harness as earlier) through all 4 pages. Expect no exceptions, 1 live Cortex Analyst answer and 1 policy search result.
- **Injection regression:** submit `\' OR 1=1 --` and a string containing `'` through Report Builder and policy search. Expect normal handling and no SQL error.
- **Usage cap:** the 21st call shows the limit message.
- **Snowflake-hosted app:** after redeploying, it still renders, and the bind-parameter changes work in the warehouse runtime.
- **Public URL:** open it in a private browser window with no Snowflake session.

## Risks and assumptions
- The dependency-file lookup order on Community Cloud will be confirmed against the docs before building. If it differs, the fallback is a separate branch for the cloud build.
- A credit cap of 10 per month on the public warehouse is my default; change it if you prefer.
- Anyone with the URL can use the app until you delete it or drop `COPILOT_PUBLIC_SVC`. Teardown is one statement: `DROP USER COPILOT_PUBLIC_SVC`.

## Critical Files
- [streamlit_app.py](streamlit_app.py) - connection logic, bind parameters, usage cap
- `scripts/public_app_access.sql` (new) - warehouse, monitor, role, service user
- `cloud/app.py`, `cloud/requirements.txt` (new) - Community Cloud entrypoint and dependencies
- [.gitignore](.gitignore) - already excludes `secrets.toml`; add key-file patterns

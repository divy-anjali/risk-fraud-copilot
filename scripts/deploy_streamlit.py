"""Deploy streamlit_app.py as a Streamlit-in-Snowflake app.

Run locally from the project root:
    .venv\\Scripts\\python.exe scripts\\deploy_streamlit.py

Uploads streamlit_app.py and environment.yml to RISK_DB.SEMANTICS.STREAMLIT_STAGE,
creates (or replaces) the AML_CUSTOMER_360 Streamlit object, and adds a live version.
Requires the 'qbgiwtu-dk32675' connection in connections.toml.
"""
import os
import snowflake.connector

CONNECTION_NAME = "qbgiwtu-dk32675"
STAGE = "RISK_DB.SEMANTICS.STREAMLIT_STAGE"
APP = "RISK_DB.SEMANTICS.AML_CUSTOMER_360"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["streamlit_app.py", "environment.yml"]

con = snowflake.connector.connect(
    connection_name=CONNECTION_NAME,
    client_store_temporary_credential=True,
)
cur = con.cursor()
try:
    for f in FILES:
        local = os.path.join(ROOT, f).replace("\\", "/")
        cur.execute(
            f"PUT 'file://{local}' @{STAGE} AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
        )
        print(f"PUT {f}: {cur.fetchone()}")

    cur.execute(f"ALTER STAGE {STAGE} REFRESH")

    cur.execute(
        f"""
        CREATE OR REPLACE STREAMLIT {APP}
          FROM '@{STAGE}'
          MAIN_FILE = 'streamlit_app.py'
          QUERY_WAREHOUSE = COMPUTE_WH
          TITLE = 'Risk & Fraud Copilot'
        """
    )
    print("CREATE STREAMLIT:", cur.fetchone())

    cur.execute(f"ALTER STREAMLIT {APP} ADD LIVE VERSION FROM LAST")
    print("ADD LIVE VERSION:", cur.fetchone())
finally:
    cur.close()
    con.close()

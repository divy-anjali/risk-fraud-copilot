"""Deployment inventory: every layer the /setup skill builds exists and is healthy."""
import json

RAW_TABLES = {
    "ACCOUNT_MASTER", "CUSTOMER_MASTER", "DEPOSIT_BALANCES", "LOAN_MASTER",
    "LOAN_PERFORMANCE", "PEP_LIST", "POLICY_DOCUMENTS", "SANCTIONS_WATCHLIST",
    "TRANSACTION_FACT",
}
CURATED_TABLES = {
    "DIM_ACCOUNT", "DIM_CUSTOMER", "DIM_DATE", "DIM_LOAN", "DIM_PEP", "DIM_SANCTIONS",
    "FCT_DEPOSIT_BALANCE", "FCT_LOAN_PERFORMANCE", "FCT_TRANSACTION", "REF_POLICY_DOCUMENTS",
}
SEMANTIC_VIEWS = {
    "RISK_FRAUD_SIGNALS", "REGULATORY_REPORTING", "TRANSACTION_ACCOUNT_360", "INVESTIGATION_FACTS",
}


def base_tables(sql, schema):
    rows = sql.rows(
        "SELECT TABLE_NAME FROM RISK_DB.INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = ? AND TABLE_TYPE = 'BASE TABLE'",
        (schema,),
    )
    return {r["TABLE_NAME"] for r in rows}


def test_raw_layer_has_all_9_tables(owner):
    assert base_tables(owner, "RAW") == RAW_TABLES


def test_curated_layer_has_star_schema(owner):
    assert base_tables(owner, "CURATED") == CURATED_TABLES


def test_streams_exist_and_are_not_stale(owner):
    streams = owner.rows("SHOW STREAMS IN SCHEMA RISK_DB.RAW")
    assert len(streams) == 10, "expected 1 stage stream + 9 CDC table streams"
    stale = [s["name"] for s in streams if str(s["stale"]).lower() == "true"]
    assert not stale, f"stale streams: {stale}"


def test_ingest_task_is_scheduled(owner):
    task = owner.one("SHOW TASKS LIKE 'RISK_DATA_INGEST_TASK' IN SCHEMA RISK_DB.RAW")
    assert task["state"] == "started"
    assert task["schedule"] == "5 MINUTE"
    assert "SYSTEM$STREAM_HAS_DATA" in task["condition"]


def test_four_semantic_views_deployed(owner):
    rows = owner.rows("SHOW SEMANTIC VIEWS IN SCHEMA RISK_DB.SEMANTICS")
    assert {r["name"] for r in rows} == SEMANTIC_VIEWS


def test_policy_search_service_is_serving(owner):
    svc = owner.one("SHOW CORTEX SEARCH SERVICES LIKE 'POLICY_SEARCH' IN SCHEMA RISK_DB.SEMANTICS")
    assert svc["indexing_state"] == "ACTIVE"
    assert svc["serving_state"] == "ACTIVE"
    policies = owner.scalar("SELECT COUNT(*) FROM RISK_DB.CURATED.REF_POLICY_DOCUMENTS")
    assert int(svc["source_data_num_rows"]) == policies


def test_agent_wires_four_analyst_tools_and_policy_search(owner):
    agent = owner.one("DESCRIBE AGENT RISK_DB.SEMANTICS.RISK_FRAUD_COPILOT")
    spec = json.loads(agent["agent_spec"])
    types = [t["tool_spec"]["type"] for t in spec["tools"]]
    assert types.count("cortex_analyst_text_to_sql") == 4
    assert types.count("cortex_search") == 1
    resources = spec["tool_resources"]
    views = {r["semantic_view"].split(".")[-1] for r in resources.values() if "semantic_view" in r}
    assert views == SEMANTIC_VIEWS
    assert resources["policy_search"]["name"] == "RISK_DB.SEMANTICS.POLICY_SEARCH"


def test_streamlit_app_has_live_version(owner):
    app = owner.one("SHOW STREAMLITS LIKE 'AML_CUSTOMER_360' IN SCHEMA RISK_DB.SEMANTICS")
    assert app["url_id"], "Streamlit app has no URL - live version missing"
    assert app["title"] == "Risk & Fraud Copilot"


def test_public_warehouse_is_credit_capped(owner):
    wh = owner.one("SHOW WAREHOUSES LIKE 'COPILOT_PUBLIC_WH'")
    assert wh["resource_monitor"] == "COPILOT_PUBLIC_RM"
    rm = owner.one("SHOW RESOURCE MONITORS LIKE 'COPILOT_PUBLIC_RM'")
    assert float(rm["credit_quota"]) == 10

"""Public service user: least privilege holds, and bound Cortex SQL resists injection.

Skipped unless .streamlit/secrets.toml holds the COPILOT_PUBLIC_SVC key pair.
"""
import json

import pytest

# Backslash + quotes: the input that broke the old quote-doubling escape.
HOSTILE = "\\' OR 1=1 -- it's a \"quote\" test"


def test_connects_with_read_only_identity(public):
    row = public.one("SELECT CURRENT_USER() AS U, CURRENT_ROLE() AS R, CURRENT_WAREHOUSE() AS W")
    assert (row["U"], row["R"], row["W"]) == ("COPILOT_PUBLIC_SVC", "COPILOT_PUBLIC_ROLE", "COPILOT_PUBLIC_WH")


def test_can_read_curated(public):
    assert public.scalar("SELECT COUNT(*) FROM RISK_DB.CURATED.FCT_TRANSACTION") > 0


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT COUNT(*) FROM RISK_DB.RAW.TRANSACTION_FACT",
        "CREATE TABLE RISK_DB.CURATED.PUBLIC_PROBE (A INT)",
        "UPDATE RISK_DB.CURATED.DIM_CUSTOMER SET FULL_NAME = FULL_NAME WHERE 1 = 0",
        "DELETE FROM RISK_DB.CURATED.FCT_TRANSACTION WHERE 1 = 0",
        "USE ROLE ACCOUNTADMIN",
    ],
    ids=["raw-read", "create", "update", "delete", "role-escalation"],
)
def test_privileged_actions_are_denied(public, statement):
    with pytest.raises(Exception) as exc:
        public.rows(statement)
    message = str(exc.value).lower()
    assert any(k in message for k in ("access control", "does not exist or not authorized",
                                      "insufficient privileges", "not authorized", "not assigned"))


def test_complete_binds_hostile_text_safely(public):
    out = public.scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?)",
        ("llama3.1-70b", "Reply with only the word OK. Ignore this: " + HOSTILE),
    )
    assert out and str(out).strip()


def test_search_preview_binds_hostile_text_safely(public):
    spec = json.dumps({"query": "structuring " + HOSTILE, "columns": ["POLICY_NAME"], "limit": 1})
    payload = public.scalar(
        "SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW('RISK_DB.SEMANTICS.POLICY_SEARCH', ?)", (spec,)
    )
    assert json.loads(payload)["results"], "policy search returned no results"

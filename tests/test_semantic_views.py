"""Semantic views: specs validate, and Cortex Analyst answers match ground truth."""
import json
import math

import pytest
import requests

from conftest import ROOT

ANALYST_ENDPOINT = "/api/v2/cortex/analyst/message"
YAML_FILES = sorted((ROOT / "semantics").glob("*.sv.yaml"))

# (semantic view, question, ground-truth SQL). Each answer must contain the
# ground-truth value (within 0.5%) somewhere in its first row.
ACCURACY_CASES = [
    ("RISK_FRAUD_SIGNALS", "How many transactions are flagged for AML?",
     "SELECT COUNT_IF(HAS_AML_FLAG) FROM RISK_DB.CURATED.FCT_TRANSACTION"),
    ("REGULATORY_REPORTING", "What is the total risk weighted assets across all loans?",
     "SELECT SUM(RWA) FROM RISK_DB.CURATED.DIM_LOAN WHERE IS_CURRENT"),
    ("TRANSACTION_ACCOUNT_360", "What is the total amount of all transactions?",
     "SELECT SUM(AMOUNT) FROM RISK_DB.CURATED.FCT_TRANSACTION"),
    ("INVESTIGATION_FACTS", "How many customers are politically exposed persons?",
     "SELECT COUNT_IF(PEP_FLAG) FROM RISK_DB.CURATED.DIM_CUSTOMER WHERE IS_CURRENT"),
]


def ask_analyst(sql, view, question):
    """POST one question to Cortex Analyst; return the generated SQL (or fail)."""
    con = sql.con
    body = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
        "semantic_view": f"RISK_DB.SEMANTICS.{view}",
    }
    r = requests.post(
        f"https://{con.host}{ANALYST_ENDPOINT}",
        json=body,
        headers={"Authorization": f'Snowflake Token="{con.rest.token}"',
                 "Content-Type": "application/json", "Accept": "application/json"},
        timeout=120,
    )
    assert r.status_code == 200, f"Analyst HTTP {r.status_code}: {r.text[:300]}"
    content = r.json().get("message", {}).get("content", [])
    statement = next((c.get("statement") for c in content if c.get("type") == "sql"), None)
    assert statement, f"Analyst returned no SQL: {json.dumps(content)[:300]}"
    return statement


def numbers_in(row):
    for value in row.values():
        try:
            f = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isnan(f):
            yield f


@pytest.mark.parametrize("yaml_file", YAML_FILES, ids=[f.name for f in YAML_FILES])
def test_semantic_view_yaml_validates(owner, yaml_file):
    """Dry-run with verify_only=TRUE: validates the spec, creates nothing."""
    result = owner.scalar(
        "CALL SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML('RISK_DB.SEMANTICS', ?, TRUE)",
        (yaml_file.read_text(encoding="utf-8"),),
    )
    assert "valid" in str(result).lower() and "no object has been created" in str(result).lower(), result


@pytest.mark.parametrize("view,question,truth_sql", ACCURACY_CASES, ids=[c[0] for c in ACCURACY_CASES])
def test_analyst_answer_matches_ground_truth(owner, view, question, truth_sql):
    expected = float(owner.scalar(truth_sql))
    generated = ask_analyst(owner, view, question)
    rows = owner.rows(generated)
    assert rows, f"generated SQL returned no rows:\n{generated}"
    found = list(numbers_in(rows[0]))
    tolerance = max(abs(expected) * 0.005, 0.5)
    assert any(abs(v - expected) <= tolerance for v in found), (
        f"expected {expected:,.2f}, Analyst returned {found}\nSQL:\n{generated}"
    )

"""Data quality: the RAW -> CURATED pipeline is complete, keyed, and consistent."""
import pytest

C = "RISK_DB.CURATED"

# RAW table -> CURATED target. Facts load 1:1; customers compare distinct IDs to
# current SCD2 rows.
RECONCILIATION = [
    ("SELECT COUNT(*) FROM RISK_DB.RAW.TRANSACTION_FACT", f"SELECT COUNT(*) FROM {C}.FCT_TRANSACTION"),
    ("SELECT COUNT(*) FROM RISK_DB.RAW.DEPOSIT_BALANCES", f"SELECT COUNT(*) FROM {C}.FCT_DEPOSIT_BALANCE"),
    ("SELECT COUNT(*) FROM RISK_DB.RAW.LOAN_PERFORMANCE", f"SELECT COUNT(*) FROM {C}.FCT_LOAN_PERFORMANCE"),
    ("SELECT COUNT(DISTINCT CUSTOMER_ID) FROM RISK_DB.RAW.CUSTOMER_MASTER",
     f"SELECT COUNT(*) FROM {C}.DIM_CUSTOMER WHERE IS_CURRENT"),
    ("SELECT COUNT(DISTINCT LOAN_ID) FROM RISK_DB.RAW.LOAN_MASTER",
     f"SELECT COUNT(*) FROM {C}.DIM_LOAN WHERE IS_CURRENT"),
]

# (dimension, natural key) for the SCD2 one-current-row rule.
SCD2_DIMENSIONS = [
    ("DIM_CUSTOMER", "CUSTOMER_ID"),
    ("DIM_ACCOUNT", "ACCOUNT_ID"),
    ("DIM_LOAN", "LOAN_ID"),
    ("DIM_PEP", "PEP_ID"),
    ("DIM_SANCTIONS", "WATCHLIST_ID"),
]

# (fact, foreign key, dimension, dimension key)
FOREIGN_KEYS = [
    ("FCT_TRANSACTION", "DIM_CUSTOMER_SK", "DIM_CUSTOMER", "DIM_CUSTOMER_SK"),
    ("FCT_TRANSACTION", "DIM_ACCOUNT_SK", "DIM_ACCOUNT", "DIM_ACCOUNT_SK"),
    ("FCT_TRANSACTION", "TRANSACTION_DATE_SK", "DIM_DATE", "DATE_SK"),
    ("FCT_LOAN_PERFORMANCE", "DIM_LOAN_SK", "DIM_LOAN", "DIM_LOAN_SK"),
    ("FCT_DEPOSIT_BALANCE", "DIM_ACCOUNT_SK", "DIM_ACCOUNT", "DIM_ACCOUNT_SK"),
]


@pytest.mark.parametrize(
    "raw_sql,curated_sql",
    RECONCILIATION,
    ids=["transactions", "deposits", "loan-performance", "customers", "loans"],
)
def test_raw_reconciles_to_curated(owner, raw_sql, curated_sql):
    raw, curated = owner.scalar(raw_sql), owner.scalar(curated_sql)
    assert raw > 0, "source table is empty"
    assert raw == curated, f"RAW={raw} vs CURATED={curated}"


@pytest.mark.parametrize("dim,key", SCD2_DIMENSIONS, ids=[d for d, _ in SCD2_DIMENSIONS])
def test_scd2_exactly_one_current_row_per_key(owner, dim, key):
    bad = owner.scalar(
        f"SELECT COUNT(*) FROM (SELECT {key} FROM {C}.{dim} GROUP BY 1 HAVING COUNT_IF(IS_CURRENT) <> 1)"
    )
    assert bad == 0, f"{bad} {key} values in {dim} do not have exactly one current row"


@pytest.mark.parametrize("fact,fk,dim,pk", FOREIGN_KEYS, ids=[f"{f}.{k}" for f, k, _, _ in FOREIGN_KEYS])
def test_no_orphan_fact_keys(owner, fact, fk, dim, pk):
    orphans = owner.scalar(
        f"SELECT COUNT(*) FROM {C}.{fact} f "
        f"WHERE f.{fk} IS NULL OR NOT EXISTS (SELECT 1 FROM {C}.{dim} d WHERE d.{pk} = f.{fk})"
    )
    assert orphans == 0, f"{orphans} rows in {fact} reference a missing {dim}"


def test_aml_flag_and_alert_type_agree(owner):
    row = owner.one(
        f"""SELECT COUNT_IF(HAS_AML_FLAG AND AML_ALERT_TYPE IS NULL) AS FLAGGED_NO_TYPE,
                   COUNT_IF(NOT HAS_AML_FLAG AND AML_ALERT_TYPE IS NOT NULL) AS TYPE_NOT_FLAGGED
            FROM {C}.FCT_TRANSACTION"""
    )
    assert row["FLAGGED_NO_TYPE"] == 0
    assert row["TYPE_NOT_FLAGGED"] == 0


def test_transaction_values_in_valid_range(owner):
    row = owner.one(
        f"""SELECT COUNT_IF(AMOUNT <= 0) AS NON_POSITIVE,
                   COUNT_IF(RISK_SCORE NOT BETWEEN 0 AND 100) AS BAD_SCORE,
                   SUM(IFF(HAS_AML_FLAG, AMOUNT, 0)) AS FLAGGED_AMT, SUM(AMOUNT) AS TOTAL_AMT
            FROM {C}.FCT_TRANSACTION"""
    )
    assert row["NON_POSITIVE"] == 0
    assert row["BAD_SCORE"] == 0
    assert row["FLAGGED_AMT"] <= row["TOTAL_AMT"]


def test_every_current_loan_has_performance_history(owner):
    missing = owner.scalar(
        f"""SELECT COUNT(*) FROM {C}.DIM_LOAN l WHERE l.IS_CURRENT
            AND NOT EXISTS (SELECT 1 FROM {C}.FCT_LOAN_PERFORMANCE p WHERE p.DIM_LOAN_SK = l.DIM_LOAN_SK)"""
    )
    assert missing == 0


def test_policy_documents_were_parsed(owner):
    row = owner.one(
        f"SELECT COUNT(*) AS N, COUNT_IF(CONTENT_LENGTH_CHARS < 200) AS SHORT FROM {C}.REF_POLICY_DOCUMENTS"
    )
    assert row["N"] >= 1, "no policy documents loaded"
    assert row["SHORT"] == 0, "a policy parsed to under 200 characters - AI_PARSE_DOCUMENT likely failed"

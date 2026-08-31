import streamlit as st
import pandas as pd
import snowflake.connector

st.set_page_config(
    page_title="Risk & Fraud Copilot",
    page_icon=":shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_connection():
    return snowflake.connector.connect(
        connection_name="hmxhrph-kh35929",
        client_store_temporary_credential=True,
    )


sf_conn = get_connection()


@st.cache_data(ttl=300)
def run_query(sql: str) -> pd.DataFrame:
    cur = sf_conn.cursor()
    cur.execute(sql)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Sidebar: global filters
# ---------------------------------------------------------------------------
st.sidebar.title("Risk & Fraud Copilot")
page = st.sidebar.radio("Navigation", ["AML Monitoring", "Customer 360"])
st.sidebar.markdown("---")

alert_types_all = [
    "STRUCTURING",
    "RAPID_MOVEMENT",
    "ROUND_TRIPPING",
    "HIGH_RISK_JURISDICTION",
    "FRAUD_SUSPICION",
    "UNUSUAL_ACTIVITY",
    "CONCENTRATION_RISK",
    "LIQUIDITY_STRESS",
]
selected_alerts = st.sidebar.multiselect(
    "Alert type", alert_types_all, default=alert_types_all
)

screening_options = ["ALL", "ALERT_GENERATED", "UNDER_REVIEW", "ESCALATED", "SAR_FILED"]
selected_screening = st.sidebar.selectbox("Screening status", screening_options)


def alert_filter_clause():
    if not selected_alerts:
        return "AND 1=0"
    quoted = ", ".join(f"'{a}'" for a in selected_alerts)
    return f"AND t.AML_ALERT_TYPE IN ({quoted})"


def screening_filter_clause():
    if selected_screening == "ALL":
        return ""
    return f"AND t.SCREENING_STATUS = '{selected_screening}'"


# =========================================================================
# PAGE 1: AML MONITORING
# =========================================================================
if page == "AML Monitoring":
    st.title("AML Monitoring Dashboard")
    st.caption("Anti-Money Laundering alerts, risk scores, and flagged transaction analysis")

    # -- KPI row --
    kpi_sql = """
    SELECT
        COUNT(*) AS total_txns,
        SUM(CASE WHEN HAS_AML_FLAG THEN 1 ELSE 0 END) AS flagged_txns,
        ROUND(AVG(CASE WHEN HAS_AML_FLAG THEN RISK_SCORE END), 1) AS avg_risk_score,
        SUM(CASE WHEN HAS_AML_FLAG THEN AMOUNT ELSE 0 END) AS flagged_amount
    FROM RISK_DB.CURATED.FCT_TRANSACTION t
    """
    kpi = run_query(kpi_sql)

    c1, c2, c3, c4 = st.columns(4)
    total = int(kpi["TOTAL_TXNS"].iloc[0])
    flagged = int(kpi["FLAGGED_TXNS"].iloc[0])
    c1.metric("Total Transactions", f"{total:,}")
    c2.metric("Flagged Transactions", f"{flagged:,}")
    c3.metric("Avg Risk Score (flagged)", kpi["AVG_RISK_SCORE"].iloc[0] or "N/A")
    c4.metric("Flagged Amount", f"${kpi['FLAGGED_AMOUNT'].iloc[0]:,.0f}")

    st.markdown("---")

    # -- Charts row --
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Alerts by Type")
        alert_sql = f"""
        SELECT AML_ALERT_TYPE, COUNT(*) AS ALERT_COUNT, SUM(AMOUNT) AS TOTAL_AMOUNT
        FROM RISK_DB.CURATED.FCT_TRANSACTION t
        WHERE HAS_AML_FLAG = TRUE {alert_filter_clause()} {screening_filter_clause()}
        GROUP BY AML_ALERT_TYPE
        ORDER BY ALERT_COUNT DESC
        """
        alert_df = run_query(alert_sql)
        if not alert_df.empty:
            st.bar_chart(alert_df, x="AML_ALERT_TYPE", y="ALERT_COUNT")
        else:
            st.info("No alerts match the current filters.")

    with col_right:
        st.subheader("Risk Score Distribution")
        risk_sql = f"""
        SELECT
            CASE
                WHEN RISK_SCORE >= 90 THEN '90-100 (Critical)'
                WHEN RISK_SCORE >= 80 THEN '80-89 (High)'
                WHEN RISK_SCORE >= 70 THEN '70-79 (Elevated)'
                ELSE 'Below 70'
            END AS RISK_BAND,
            COUNT(*) AS TXN_COUNT
        FROM RISK_DB.CURATED.FCT_TRANSACTION t
        WHERE HAS_AML_FLAG = TRUE {alert_filter_clause()} {screening_filter_clause()}
        GROUP BY RISK_BAND
        ORDER BY RISK_BAND
        """
        risk_df = run_query(risk_sql)
        if not risk_df.empty:
            st.bar_chart(risk_df, x="RISK_BAND", y="TXN_COUNT")
        else:
            st.info("No data for risk distribution.")

    st.markdown("---")

    # -- Screening status breakdown --
    st.subheader("Screening Status Breakdown")
    screen_sql = f"""
    SELECT SCREENING_STATUS, COUNT(*) AS CNT, SUM(AMOUNT) AS TOTAL_AMOUNT
    FROM RISK_DB.CURATED.FCT_TRANSACTION t
    WHERE HAS_AML_FLAG = TRUE {alert_filter_clause()}
    GROUP BY SCREENING_STATUS
    ORDER BY CNT DESC
    """
    screen_df = run_query(screen_sql)
    if not screen_df.empty:
        sc1, sc2 = st.columns([1, 2])
        with sc1:
            st.dataframe(screen_df, use_container_width=True, hide_index=True)
        with sc2:
            st.bar_chart(screen_df, x="SCREENING_STATUS", y="TOTAL_AMOUNT")

    st.markdown("---")

    # -- Top flagged customers --
    st.subheader("Top Flagged Customers")
    top_cust_sql = f"""
    SELECT
        c.FULL_NAME,
        c.CUSTOMER_ID,
        c.RISK_RATING,
        c.PEP_FLAG,
        c.SANCTIONS_MATCH_FLAG,
        COUNT(t.TRANSACTION_ID) AS FLAGGED_TXNS,
        SUM(t.AMOUNT) AS FLAGGED_AMOUNT,
        ROUND(AVG(t.RISK_SCORE), 1) AS AVG_RISK
    FROM RISK_DB.CURATED.FCT_TRANSACTION t
    JOIN RISK_DB.CURATED.DIM_CUSTOMER c
        ON t.DIM_CUSTOMER_SK = c.DIM_CUSTOMER_SK AND c.IS_CURRENT = TRUE
    WHERE t.HAS_AML_FLAG = TRUE {alert_filter_clause()} {screening_filter_clause()}
    GROUP BY c.FULL_NAME, c.CUSTOMER_ID, c.RISK_RATING, c.PEP_FLAG, c.SANCTIONS_MATCH_FLAG
    ORDER BY FLAGGED_AMOUNT DESC
    LIMIT 20
    """
    top_df = run_query(top_cust_sql)
    if not top_df.empty:
        st.dataframe(top_df, use_container_width=True, hide_index=True)
    else:
        st.info("No flagged customers match the current filters.")

    st.markdown("---")

    # -- Detailed flagged transactions --
    st.subheader("Flagged Transaction Details")
    detail_sql = f"""
    SELECT
        t.TRANSACTION_ID,
        t.TRANSACTION_DATE,
        c.FULL_NAME AS CUSTOMER,
        a.ACCOUNT_TYPE,
        t.TRANSACTION_TYPE,
        t.AMOUNT,
        t.CURRENCY,
        t.AML_ALERT_TYPE,
        t.RISK_SCORE,
        t.SCREENING_STATUS,
        t.BENEFICIARY_COUNTRY,
        t.IS_CROSS_BORDER
    FROM RISK_DB.CURATED.FCT_TRANSACTION t
    JOIN RISK_DB.CURATED.DIM_CUSTOMER c
        ON t.DIM_CUSTOMER_SK = c.DIM_CUSTOMER_SK AND c.IS_CURRENT = TRUE
    LEFT JOIN RISK_DB.CURATED.DIM_ACCOUNT a
        ON t.DIM_ACCOUNT_SK = a.DIM_ACCOUNT_SK AND a.IS_CURRENT = TRUE
    WHERE t.HAS_AML_FLAG = TRUE {alert_filter_clause()} {screening_filter_clause()}
    ORDER BY t.RISK_SCORE DESC, t.AMOUNT DESC
    LIMIT 100
    """
    detail_df = run_query(detail_sql)
    if not detail_df.empty:
        st.dataframe(detail_df, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions match the current filters.")


# =========================================================================
# PAGE 2: CUSTOMER 360
# =========================================================================
elif page == "Customer 360":
    st.title("Customer 360")
    st.caption("Select a customer to see their full risk profile, accounts, and transaction history")

    # -- Customer selector --
    cust_list_sql = """
    SELECT CUSTOMER_ID, FULL_NAME, RISK_RATING, IS_HIGH_RISK
    FROM RISK_DB.CURATED.DIM_CUSTOMER
    WHERE IS_CURRENT = TRUE
    ORDER BY CUSTOMER_ID
    """
    cust_list = run_query(cust_list_sql)

    display_names = cust_list.apply(
        lambda r: f"{r['CUSTOMER_ID']} - {r['FULL_NAME']} ({r['RISK_RATING']})", axis=1
    ).tolist()

    selected_display = st.selectbox("Select a customer", display_names)
    selected_idx = display_names.index(selected_display)
    cust_id = cust_list.iloc[selected_idx]["CUSTOMER_ID"]

    # -- Customer profile --
    profile_sql = f"""
    SELECT
        CUSTOMER_ID, FULL_NAME, NATIONALITY, COUNTRY_OF_RESIDENCE,
        CUSTOMER_TYPE, INDUSTRY, RISK_RATING, KYC_STATUS,
        KYC_LAST_REVIEWED, ONBOARDING_DATE, PEP_FLAG,
        SANCTIONS_MATCH_FLAG, ANNUAL_INCOME, SOURCE_OF_FUNDS,
        ACCOUNT_PURPOSE, IS_HIGH_RISK, AGE_YEARS, DAYS_SINCE_ONBOARDING
    FROM RISK_DB.CURATED.DIM_CUSTOMER
    WHERE IS_CURRENT = TRUE AND CUSTOMER_ID = '{cust_id}'
    """
    profile = run_query(profile_sql)

    if not profile.empty:
        p = profile.iloc[0]

        # Profile KPI row
        pc1, pc2, pc3, pc4, pc5 = st.columns(5)
        pc1.metric("Risk Rating", p["RISK_RATING"])
        pc2.metric("KYC Status", p["KYC_STATUS"])
        pc3.metric("PEP", "Yes" if p["PEP_FLAG"] else "No")
        pc4.metric("Sanctions Match", "Yes" if p["SANCTIONS_MATCH_FLAG"] else "No")
        pc5.metric("High Risk", "Yes" if p["IS_HIGH_RISK"] else "No")

        with st.expander("Full Customer Profile", expanded=False):
            prof_left, prof_right = st.columns(2)
            with prof_left:
                st.markdown(f"**Name:** {p['FULL_NAME']}")
                st.markdown(f"**Nationality:** {p['NATIONALITY']}")
                st.markdown(f"**Residence:** {p['COUNTRY_OF_RESIDENCE']}")
                st.markdown(f"**Type:** {p['CUSTOMER_TYPE']}")
                st.markdown(f"**Industry:** {p['INDUSTRY']}")
            with prof_right:
                st.markdown(f"**Annual Income:** ${p['ANNUAL_INCOME']:,.0f}")
                st.markdown(f"**Source of Funds:** {p['SOURCE_OF_FUNDS']}")
                st.markdown(f"**Account Purpose:** {p['ACCOUNT_PURPOSE']}")
                st.markdown(f"**Onboarded:** {p['ONBOARDING_DATE']}")
                st.markdown(f"**KYC Last Reviewed:** {p['KYC_LAST_REVIEWED']}")

    st.markdown("---")

    # -- Accounts --
    st.subheader("Accounts")
    acct_sql = f"""
    SELECT
        a.ACCOUNT_ID, a.ACCOUNT_TYPE, a.CURRENCY, a.STATUS,
        a.BALANCE, a.CREDIT_LIMIT, a.RISK_SCORE,
        a.IS_DORMANT, a.IS_OVERDRAWN, a.LAST_ACTIVITY_DATE
    FROM RISK_DB.CURATED.DIM_ACCOUNT a
    WHERE a.IS_CURRENT = TRUE
      AND a.CUSTOMER_ID = '{cust_id}'
    ORDER BY a.ACCOUNT_ID
    """
    acct_df = run_query(acct_sql)
    if not acct_df.empty:
        st.dataframe(acct_df, use_container_width=True, hide_index=True)
    else:
        st.info("No accounts found for this customer.")

    st.markdown("---")

    # -- Transaction summary metrics --
    txn_summary_sql = f"""
    SELECT
        COUNT(*) AS TOTAL_TXNS,
        SUM(CASE WHEN t.HAS_AML_FLAG THEN 1 ELSE 0 END) AS FLAGGED_TXNS,
        SUM(t.AMOUNT) AS TOTAL_AMOUNT,
        ROUND(AVG(t.RISK_SCORE), 1) AS AVG_RISK
    FROM RISK_DB.CURATED.FCT_TRANSACTION t
    JOIN RISK_DB.CURATED.DIM_CUSTOMER c
        ON t.DIM_CUSTOMER_SK = c.DIM_CUSTOMER_SK AND c.IS_CURRENT = TRUE
    WHERE c.CUSTOMER_ID = '{cust_id}'
    """
    txn_sum = run_query(txn_summary_sql)

    st.subheader("Transaction Summary")
    ts1, ts2, ts3, ts4 = st.columns(4)
    if not txn_sum.empty:
        ts1.metric("Total Transactions", f"{int(txn_sum['TOTAL_TXNS'].iloc[0]):,}")
        ts2.metric("Flagged", int(txn_sum["FLAGGED_TXNS"].iloc[0]))
        ts3.metric("Total Amount", f"${txn_sum['TOTAL_AMOUNT'].iloc[0]:,.0f}")
        ts4.metric("Avg Risk Score", txn_sum["AVG_RISK"].iloc[0] or "N/A")

    st.markdown("---")

    # -- Transaction timeline --
    st.subheader("Transaction Timeline")
    timeline_sql = f"""
    SELECT
        t.TRANSACTION_DATE,
        t.AMOUNT,
        t.TRANSACTION_TYPE,
        CASE WHEN t.HAS_AML_FLAG THEN 'FLAGGED' ELSE 'NORMAL' END AS STATUS
    FROM RISK_DB.CURATED.FCT_TRANSACTION t
    JOIN RISK_DB.CURATED.DIM_CUSTOMER c
        ON t.DIM_CUSTOMER_SK = c.DIM_CUSTOMER_SK AND c.IS_CURRENT = TRUE
    WHERE c.CUSTOMER_ID = '{cust_id}'
    ORDER BY t.TRANSACTION_DATE
    """
    timeline_df = run_query(timeline_sql)
    if not timeline_df.empty:
        st.scatter_chart(
            timeline_df,
            x="TRANSACTION_DATE",
            y="AMOUNT",
            color="STATUS",
        )
    else:
        st.info("No transactions found for this customer.")

    st.markdown("---")

    # -- Full transaction history --
    st.subheader("Transaction History")
    hist_sql = f"""
    SELECT
        t.TRANSACTION_ID,
        t.TRANSACTION_DATE,
        t.TRANSACTION_TYPE,
        t.AMOUNT,
        t.CURRENCY,
        t.DIRECTION,
        t.CHANNEL,
        t.BENEFICIARY_COUNTRY,
        t.HAS_AML_FLAG,
        t.AML_ALERT_TYPE,
        t.RISK_SCORE,
        t.SCREENING_STATUS,
        t.IS_CROSS_BORDER
    FROM RISK_DB.CURATED.FCT_TRANSACTION t
    JOIN RISK_DB.CURATED.DIM_CUSTOMER c
        ON t.DIM_CUSTOMER_SK = c.DIM_CUSTOMER_SK AND c.IS_CURRENT = TRUE
    WHERE c.CUSTOMER_ID = '{cust_id}'
    ORDER BY t.TRANSACTION_DATE DESC, t.RISK_SCORE DESC
    """
    hist_df = run_query(hist_sql)
    if not hist_df.empty:
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions found.")

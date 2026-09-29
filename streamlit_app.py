import html
import json
import math

import altair as alt
import pandas as pd
import streamlit as st

# Dual-mode connection: inside Streamlit-in-Snowflake use the active session;
# for local development fall back to a named connection from connections.toml.
LOCAL_CONNECTION_NAME = "qbgiwtu-dk32675"

# LLM used for the in-app narrative generation (Report Builder). llama3.1-70b is
# natively available in this account's region (AWS ap-southeast-2), so the
# SNOWFLAKE.CORTEX.COMPLETE call does not depend on cross-region inference.
COMPLETE_MODEL = "llama3.1-70b"

ANALYST_ENDPOINT = "/api/v2/cortex/analyst/message"

# Cortex Analyst domains -> semantic view. Ask-the-Copilot queries one view per turn.
ANALYST_DOMAINS = {
    "Fraud & AML signals": "RISK_DB.SEMANTICS.RISK_FRAUD_SIGNALS",
    "Regulatory (Basel / IFRS9 / liquidity)": "RISK_DB.SEMANTICS.REGULATORY_REPORTING",
    "Transactions & accounts (360)": "RISK_DB.SEMANTICS.TRANSACTION_ACCOUNT_360",
    "Investigation facts": "RISK_DB.SEMANTICS.INVESTIGATION_FACTS",
}

# Human-readable labels for coded categories shown on charts.
ALERT_LABELS = {
    "STRUCTURING": "Structuring",
    "RAPID_MOVEMENT": "Rapid Movement",
    "ROUND_TRIPPING": "Round Tripping",
    "HIGH_RISK_JURISDICTION": "High-Risk Jurisdiction",
    "FRAUD_SUSPICION": "Fraud Suspicion",
    "UNUSUAL_ACTIVITY": "Unusual Activity",
    "CONCENTRATION_RISK": "Concentration Risk",
    "LIQUIDITY_STRESS": "Liquidity Stress",
}
SCREENING_LABELS = {
    "ALERT_GENERATED": "Alert Generated",
    "UNDER_REVIEW": "Under Review",
    "ESCALATED": "Escalated",
    "SAR_FILED": "SAR Filed",
}
COUNTRY_NAMES = {
    "AE": "UAE", "AU": "Australia", "BR": "Brazil", "CA": "Canada", "CH": "Switzerland",
    "CN": "China", "DE": "Germany", "FR": "France", "IN": "India", "IR": "Iran",
    "JP": "Japan", "KP": "North Korea", "NG": "Nigeria", "RU": "Russia",
    "SG": "Singapore", "UK": "United Kingdom", "US": "United States",
}

# Tile accent colours by tone.
TONES = {"risk": "#d64545", "warn": "#e08a00", "good": "#2e9e5b", "info": "#2f7ed8"}


@st.cache_resource
def get_session():
    """Return the active Snowpark session when running in Snowflake, else None."""
    try:
        from snowflake.snowpark.context import get_active_session

        return get_active_session()
    except Exception:
        return None


@st.cache_resource
def get_local_connection():
    """Local fallback: a snowflake.connector connection via connections.toml."""
    import snowflake.connector

    return snowflake.connector.connect(
        connection_name=LOCAL_CONNECTION_NAME,
        client_store_temporary_credential=True,
    )


st.set_page_config(
    page_title="Risk & Fraud Copilot",
    page_icon=":shield:",
    layout="wide",
)

_SESSION = get_session()


@st.cache_data(ttl=300)
def run_query(sql: str) -> pd.DataFrame:
    if _SESSION is not None:
        # Streamlit-in-Snowflake: run through the Snowpark session.
        return _SESSION.sql(sql).to_pandas()
    # Local: run through a cursor and build the DataFrame by hand.
    cur = get_local_connection().cursor()
    cur.execute(sql)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Formatting helpers (NULL/NaN-safe)
# ---------------------------------------------------------------------------
def num(value, default=0.0) -> float:
    """Coerce a query value (None, NaN, Decimal, int) to float safely."""
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(f) else f


def money(value) -> str:
    """Compact currency: $1.08B, $78.0M, $21.6K."""
    v = num(value)
    for threshold, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= threshold:
            return f"${v / threshold:,.{2 if suffix == 'B' else 1}f}{suffix}"
    return f"${v:,.0f}"


def pct(part, whole) -> float:
    w = num(whole)
    return 0.0 if w == 0 else 100.0 * num(part) / w


def pretty(code) -> str:
    """STRUCTURING -> Structuring, SAR_FILED -> Sar Filed (fallback for unmapped codes)."""
    return str(code).replace("_", " ").title() if code is not None else "Unknown"


# ---------------------------------------------------------------------------
# UI helpers: KPI tiles and readable bar charts
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.kpi-grid {display:grid; grid-template-columns:repeat(auto-fit, minmax(230px, 1fr)); gap:14px; margin:4px 0 22px;}
.kpi-card {border-radius:12px; padding:16px 18px; background:rgba(128,128,128,0.07);
  border:1px solid rgba(128,128,128,0.20); border-left:6px solid var(--accent);}
.kpi-label {font-size:0.78rem; text-transform:uppercase; letter-spacing:0.05em; font-weight:600; opacity:0.75;}
.kpi-value {font-size:2rem; font-weight:700; line-height:1.2; margin:6px 0 4px; color:var(--accent);}
.kpi-insight {font-size:0.9rem; line-height:1.4; opacity:0.9;}
.nav-card {border-radius:12px; padding:18px 20px 14px; background:rgba(128,128,128,0.06);
  border:1px solid rgba(128,128,128,0.20); margin-bottom:10px; min-height:132px;}
.nav-title {font-size:1.15rem; font-weight:700; margin-bottom:6px;}
.nav-icon {font-size:1.3rem; margin-right:9px;}
.nav-body {font-size:0.92rem; opacity:0.85; line-height:1.45;}
</style>
""",
    unsafe_allow_html=True,
)


def tiles(cards):
    """Render a row of KPI tiles. cards: list of (label, value, insight, tone)."""
    parts = []
    for label, value, insight, tone in cards:
        parts.append(
            f'<div class="kpi-card" style="--accent:{TONES.get(tone, TONES["info"])}">'
            f'<div class="kpi-label">{html.escape(label)}</div>'
            f'<div class="kpi-value">{html.escape(value)}</div>'
            f'<div class="kpi-insight">{html.escape(insight)}</div></div>'
        )
    st.markdown(f'<div class="kpi-grid">{"".join(parts)}</div>', unsafe_allow_html=True)


# Tone lookups for the status values present in DIM_CUSTOMER.
RATING_TONES = {"HIGH": "risk", "MEDIUM": "warn", "LOW": "good"}
KYC_TONES = {"COMPLETED": "good", "PENDING": "warn", "EXPIRED": "risk"}


def flag_tone(value) -> str:
    """Red when a risk flag is set (PEP, sanctions match, high risk), green otherwise."""
    return "risk" if bool(value) else "good"


def bar_chart(df, x, y, x_title, y_title, sort="-y", y_format=None, color=None,
              color_scale=None, color_title=None, height=340):
    """Bar chart with slanted, readable category labels and titled axes."""
    y_axis = alt.Axis(format=y_format) if y_format else alt.Axis()
    encoding = {
        "x": alt.X(f"{x}:N", title=x_title, sort=sort,
                   axis=alt.Axis(labelAngle=-35, labelLimit=200, labelOverlap=False)),
        "y": alt.Y(f"{y}:Q", title=y_title, axis=y_axis),
        "tooltip": [alt.Tooltip(f"{x}:N", title=x_title),
                    alt.Tooltip(f"{y}:Q", title=y_title, format=y_format or ",")],
    }
    if color:
        encoding["color"] = alt.Color(f"{color}:N", title=color_title, scale=color_scale,
                                      legend=alt.Legend(orient="top"))
    chart = alt.Chart(df).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(**encoding)
    st.altair_chart(chart.properties(height=height), use_container_width=True)


# ---------------------------------------------------------------------------
# Cortex helpers
# ---------------------------------------------------------------------------
def _sql_literal(text: str) -> str:
    """Escape a Python string for safe use inside a single-quoted SQL literal."""
    return text.replace("'", "''")


def cortex_complete(prompt: str, model: str = COMPLETE_MODEL) -> str:
    """Run SNOWFLAKE.CORTEX.COMPLETE via SQL (works in SiS and locally)."""
    sql = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{_sql_literal(prompt)}') AS RESPONSE"
    df = run_query(sql)
    return "" if df.empty else str(df["RESPONSE"].iloc[0])


@st.cache_data(ttl=300)
def search_policies(query: str, limit: int = 3) -> pd.DataFrame:
    """Query the POLICY_SEARCH Cortex Search service via SEARCH_PREVIEW (SQL)."""
    spec = json.dumps(
        {"query": query, "columns": ["POLICY_NAME", "CLASSIFICATION", "FULL_CONTENT"], "limit": limit}
    )
    sql = f"""
    SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
        'RISK_DB.SEMANTICS.POLICY_SEARCH', '{_sql_literal(spec)}'
    ) AS PAYLOAD
    """
    df = run_query(sql)
    if df.empty:
        return pd.DataFrame(columns=["POLICY_NAME", "CLASSIFICATION", "FULL_CONTENT"])
    return pd.DataFrame(json.loads(df["PAYLOAD"].iloc[0]).get("results", []))


def _post_analyst(body: dict):
    """POST to Cortex Analyst. Returns (http_status, parsed_json).

    Locally this uses the snowflake.connector session token over plain HTTPS, so
    it works without Snowsight. Inside Streamlit-in-Snowflake it uses the
    built-in `_snowflake` bridge instead.
    """
    if _SESSION is not None:
        try:
            import _snowflake
        except ImportError:
            _snowflake = None
        if _snowflake is not None:
            resp = _snowflake.send_snow_api_request("POST", ANALYST_ENDPOINT, {}, {}, body, {}, 60000)
            return resp.get("status"), json.loads(resp.get("content") or "{}")

    import requests

    con = get_local_connection()

    def _call():
        return requests.post(
            f"https://{con.host}{ANALYST_ENDPOINT}",
            json=body,
            headers={
                "Authorization": f'Snowflake Token="{con.rest.token}"',
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=120,
        )

    r = _call()
    if r.status_code == 401 or "390112" in r.text:
        # Session token expired: a query makes the connector renew it, then retry once.
        con.cursor().execute("SELECT 1")
        r = _call()
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"message": r.text}


def run_analyst(question: str, semantic_view: str):
    """Ask Cortex Analyst a question. Returns (interpretation, sql, suggestions, error)."""
    body = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
        "semantic_view": semantic_view,
    }
    try:
        status, payload = _post_analyst(body)
    except Exception as exc:
        return None, None, [], f"Could not reach Cortex Analyst: {exc}"
    if status != 200:
        return None, None, [], f"Cortex Analyst returned {status}: {payload.get('message', payload)}"

    interpretation, sql_text, suggestions = [], None, []
    for item in payload.get("message", {}).get("content", []):
        if item.get("type") == "text":
            interpretation.append(item.get("text", ""))
        elif item.get("type") == "sql":
            sql_text = item.get("statement")
        elif item.get("type") == "suggestions":
            suggestions = item.get("suggestions", [])
    return "\n\n".join(interpretation).strip(), sql_text, suggestions, None


# Latest snapshot per loan (loan performance is a monthly time series).
LATEST_PERF_CTE = """
WITH latest_perf AS (
    SELECT p.*,
        ROW_NUMBER() OVER (PARTITION BY p.DIM_LOAN_SK ORDER BY p.REPORT_DATE DESC) AS rn
    FROM RISK_DB.CURATED.FCT_LOAN_PERFORMANCE p
)
"""


# ---------------------------------------------------------------------------
# Pages + router
# ---------------------------------------------------------------------------
# key -> (title, icon, short description shown on the landing page and page header)
PAGES = [
    ("overview", "Risk Overview", "📊",
     "Headline fraud, credit and liquidity KPIs, plus the AML alert analysis: "
     "which alerts fire, where flagged money goes, and which customers to review."),
    ("copilot", "Ask the Copilot", "💬",
     "Ask a question in plain English. Cortex Analyst answers from governed "
     "semantic views and shows the SQL it used."),
    ("customer360", "Customer 360", "👤",
     "Everything about one customer: profile, KYC/PEP/sanctions status, "
     "accounts, and full transaction history."),
    ("report", "Investigation & Report Builder", "🔍",
     "Turn a flagged customer into a documented finding: signal, evidence, "
     "cited policy, and a downloadable report."),
]
PAGE_TITLES = {key: title for key, title, _, _ in PAGES}
PAGE_ICONS = {key: icon for key, _, icon, _ in PAGES}
PAGE_DESCRIPTIONS = {key: desc for key, _, _, desc in PAGES}


def go_to(page_key: str):
    st.session_state.page = page_key


def render_home():
    """Landing page: one clickable card per page, with its description."""
    st.title("Risk, Fraud & Regulatory Intelligence Copilot")
    st.caption(
        "Governed answers over fraud, credit, liquidity and regulatory data in Snowflake. "
        "Choose where to start."
    )
    st.write("")

    # 2x2 grid so each description has room to breathe.
    for row_start in range(0, len(PAGES), 2):
        cols = st.columns(2, gap="large")
        for col, (key, title, icon, desc) in zip(cols, PAGES[row_start:row_start + 2]):
            with col:
                st.markdown(
                    f'<div class="nav-card">'
                    f'<div class="nav-title"><span class="nav-icon">{icon}</span>'
                    f'{html.escape(title)}</div>'
                    f'<div class="nav-body">{html.escape(desc)}</div></div>',
                    unsafe_allow_html=True,
                )
                st.button(f"{icon}  Open {title}", key=f"open_{key}",
                          use_container_width=True, on_click=go_to, args=(key,))
        st.write("")


def render_page_nav(current_key: str):
    """Compact nav strip shown on every page: Home plus one button per page.

    The active page is highlighted with the theme's primary colour rather than
    being greyed out, so it still reads as a live tab.
    """
    cols = st.columns([1, 2, 2, 2, 2])
    cols[0].button("Home", key="nav_home", use_container_width=True,
                   on_click=go_to, args=("home",))
    for col, (key, title, icon, _) in zip(cols[1:], PAGES):
        col.button(
            f"{icon}  {title}",
            key=f"nav_{key}",
            use_container_width=True,
            type="primary" if key == current_key else "secondary",
            on_click=go_to,
            args=(key,),
        )
    st.header(f"{PAGE_ICONS[current_key]} {PAGE_TITLES[current_key]}")
    st.caption(PAGE_DESCRIPTIONS[current_key])


# =========================================================================
# PAGE: RISK OVERVIEW (executive KPIs + AML monitoring)
# =========================================================================
def render_overview():
    st.caption("All figures are all-time totals from the curated layer. "
               "Credit figures use each loan's latest monthly snapshot.")

    fraud = run_query(
        """
        SELECT COUNT(*) AS TOTAL_TXNS,
               SUM(CASE WHEN HAS_AML_FLAG THEN 1 ELSE 0 END) AS FLAGGED_TXNS,
               COALESCE(SUM(CASE WHEN HAS_AML_FLAG THEN AMOUNT END), 0) AS FLAGGED_AMOUNT,
               ROUND(AVG(CASE WHEN HAS_AML_FLAG THEN RISK_SCORE END), 1) AS AVG_RISK
        FROM RISK_DB.CURATED.FCT_TRANSACTION
        """
    ).iloc[0]
    cust = run_query(
        """
        SELECT COUNT(*) AS CUSTOMERS,
               SUM(CASE WHEN IS_HIGH_RISK THEN 1 ELSE 0 END) AS HIGH_RISK
        FROM RISK_DB.CURATED.DIM_CUSTOMER WHERE IS_CURRENT = TRUE
        """
    ).iloc[0]
    loans = run_query(
        """
        SELECT COUNT(*) AS LOANS,
               COALESCE(SUM(RWA), 0) AS TOTAL_RWA,
               COALESCE(SUM(CAPITAL_REQUIREMENT), 0) AS TOTAL_CAPITAL,
               COALESCE(SUM(OUTSTANDING_BALANCE), 0) AS LOAN_BOOK,
               SUM(CASE WHEN HAS_BASEL_VIOLATION THEN 1 ELSE 0 END) AS VIOLATIONS,
               COALESCE(SUM(CASE WHEN HAS_BASEL_VIOLATION THEN OUTSTANDING_BALANCE END), 0) AS VIOLATION_BOOK
        FROM RISK_DB.CURATED.DIM_LOAN WHERE IS_CURRENT = TRUE
        """
    ).iloc[0]
    ecl = run_query(
        LATEST_PERF_CTE
        + """
        SELECT COALESCE(SUM(ECL_AMOUNT), 0) AS TOTAL_ECL,
               COALESCE(SUM(CASE WHEN STAGE_IFRS9 = 'STAGE_3' THEN ECL_AMOUNT END), 0) AS STAGE3_ECL,
               SUM(CASE WHEN STAGE_IFRS9 = 'STAGE_3' THEN 1 ELSE 0 END) AS STAGE3_LOANS
        FROM latest_perf WHERE rn = 1
        """
    ).iloc[0]
    liq = run_query(
        """
        SELECT COUNT(*) AS DEPOSITS,
               COALESCE(SUM(BALANCE), 0) AS DEPOSIT_BASE,
               COALESCE(SUM(UNINSURED_AMOUNT), 0) AS UNINSURED,
               SUM(CASE WHEN HAS_LIQUIDITY_VIOLATION THEN 1 ELSE 0 END) AS LIQ_VIOLATIONS,
               SUM(CASE WHEN HAS_CONCENTRATION_RISK THEN 1 ELSE 0 END) AS CONC_DEPOSITS,
               COALESCE(SUM(CASE WHEN HAS_CONCENTRATION_RISK THEN BALANCE END), 0) AS CONC_BALANCE
        FROM RISK_DB.CURATED.FCT_DEPOSIT_BALANCE
        """
    ).iloc[0]

    st.subheader("Fraud & AML")
    tiles([
        ("Flagged transactions", f"{int(num(fraud['FLAGGED_TXNS'])):,}",
         f"{pct(fraud['FLAGGED_TXNS'], fraud['TOTAL_TXNS']):.0f}% of all "
         f"{int(num(fraud['TOTAL_TXNS'])):,} transactions raised an AML alert", "risk"),
        ("Money under review", money(fraud["FLAGGED_AMOUNT"]),
         "Total value of transactions that were flagged", "warn"),
        ("Avg risk score (flagged)", f"{num(fraud['AVG_RISK']):.0f} / 100",
         "Average severity of flagged transactions (higher = more suspicious)", "warn"),
        ("High-risk customers", f"{int(num(cust['HIGH_RISK'])):,}",
         f"{pct(cust['HIGH_RISK'], cust['CUSTOMERS']):.0f}% of "
         f"{int(num(cust['CUSTOMERS'])):,} customers are rated high risk", "info"),
    ])

    st.subheader("Credit & Capital")
    tiles([
        ("Capital we must hold", money(loans["TOTAL_CAPITAL"]),
         f"{pct(loans['TOTAL_CAPITAL'], loans['TOTAL_RWA']):.1f}% of "
         f"{money(loans['TOTAL_RWA'])} risk-weighted assets, as required by Basel", "info"),
        ("Expected credit loss", money(ecl["TOTAL_ECL"]),
         f"{pct(ecl['TOTAL_ECL'], loans['LOAN_BOOK']):.1f}% of the "
         f"{money(loans['LOAN_BOOK'])} loan book is expected to be lost (IFRS9)", "warn"),
        ("Loans breaking Basel rules", f"{int(num(loans['VIOLATIONS']))} of {int(num(loans['LOANS']))}",
         f"{money(loans['VIOLATION_BOOK'])} "
         f"({pct(loans['VIOLATION_BOOK'], loans['LOAN_BOOK']):.0f}% of lending) needs remediation", "risk"),
        ("Defaulted loans (Stage 3)", f"{int(num(ecl['STAGE3_LOANS']))} of {int(num(loans['LOANS']))}",
         f"These few loans carry {pct(ecl['STAGE3_ECL'], ecl['TOTAL_ECL']):.0f}% "
         "of all expected credit loss", "risk"),
    ])

    st.subheader("Liquidity")
    tiles([
        ("Deposit base", money(liq["DEPOSIT_BASE"]),
         f"Funding held across {int(num(liq['DEPOSITS'])):,} deposits", "info"),
        ("Uninsured deposits", f"{pct(liq['UNINSURED'], liq['DEPOSIT_BASE']):.0f}%",
         f"{money(liq['UNINSURED'])} is not covered by deposit insurance and could "
         "leave quickly under stress", "warn"),
        ("Liquidity rule breaches", f"{int(num(liq['LIQ_VIOLATIONS']))} of {int(num(liq['DEPOSITS']))}",
         "Deposits breaching liquidity coverage (LCR/NSFR) limits", "risk"),
        ("Concentration risk", f"{pct(liq['CONC_BALANCE'], liq['DEPOSIT_BASE']):.0f}%",
         f"of funding sits in {int(num(liq['CONC_DEPOSITS']))} concentrated deposits", "warn"),
    ])

    st.markdown("---")
    st.subheader("AML alert analysis")

    alert_types_all = list(ALERT_LABELS.keys())
    screening_options = ["ALL"] + list(SCREENING_LABELS.keys())
    fcol1, fcol2 = st.columns([3, 1])
    selected_alerts = fcol1.multiselect(
        "Alert type", alert_types_all, default=alert_types_all,
        format_func=lambda c: ALERT_LABELS.get(c, pretty(c)), key="aml_alert_filter",
    )
    selected_screening = fcol2.selectbox(
        "Screening status", screening_options,
        format_func=lambda c: "All" if c == "ALL" else SCREENING_LABELS.get(c, pretty(c)),
        key="aml_screening_filter",
    )

    def alert_filter_clause():
        if not selected_alerts:
            return "AND 1=0"
        quoted = ", ".join(f"'{a}'" for a in selected_alerts)
        return f"AND t.AML_ALERT_TYPE IN ({quoted})"

    def screening_filter_clause():
        if selected_screening == "ALL":
            return ""
        return f"AND t.SCREENING_STATUS = '{selected_screening}'"

    filters = f"{alert_filter_clause()} {screening_filter_clause()}"

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("**Alerts by type**")
        alert_df = run_query(
            f"""
            SELECT AML_ALERT_TYPE, COUNT(*) AS ALERT_COUNT
            FROM RISK_DB.CURATED.FCT_TRANSACTION t
            WHERE HAS_AML_FLAG = TRUE {filters}
            GROUP BY AML_ALERT_TYPE
            """
        )
        if not alert_df.empty:
            alert_df["Alert type"] = alert_df["AML_ALERT_TYPE"].map(lambda c: ALERT_LABELS.get(c, pretty(c)))
            alert_df["Alerts"] = alert_df["ALERT_COUNT"].astype(int)
            bar_chart(alert_df, "Alert type", "Alerts", "Alert type", "Number of alerts")
            top = alert_df.sort_values("Alerts", ascending=False).iloc[0]
            st.caption(f"Most common alert: **{top['Alert type']}** ({top['Alerts']} alerts).")
        else:
            st.info("No alerts match the current filters.")

    with col_right:
        st.markdown("**Where flagged money goes**")
        dest_df = run_query(
            f"""
            SELECT t.BENEFICIARY_COUNTRY,
                   COUNT(*) AS FLAGGED_TXNS,
                   SUM(t.AMOUNT) AS FLAGGED_AMOUNT,
                   MAX(CASE WHEN s.COUNTRY IS NOT NULL THEN 1 ELSE 0 END) AS ON_WATCHLIST
            FROM RISK_DB.CURATED.FCT_TRANSACTION t
            LEFT JOIN (SELECT DISTINCT COUNTRY FROM RISK_DB.CURATED.DIM_SANCTIONS WHERE IS_CURRENT = TRUE) s
                ON s.COUNTRY = t.BENEFICIARY_COUNTRY
            WHERE t.HAS_AML_FLAG = TRUE {filters}
            GROUP BY t.BENEFICIARY_COUNTRY
            ORDER BY FLAGGED_AMOUNT DESC
            LIMIT 12
            """
        )
        if not dest_df.empty:
            dest_df["Destination country"] = dest_df["BENEFICIARY_COUNTRY"].map(
                lambda c: COUNTRY_NAMES.get(c, c or "Unknown"))
            dest_df["Flagged amount"] = dest_df["FLAGGED_AMOUNT"].map(num)
            dest_df["Destination"] = dest_df["ON_WATCHLIST"].map(
                lambda w: "Sanctions-watchlist country" if int(num(w)) else "Other country")
            bar_chart(
                dest_df, "Destination country", "Flagged amount", "Beneficiary country",
                "Flagged amount (USD)", y_format="$,.2s", color="Destination",
                color_scale=alt.Scale(domain=["Sanctions-watchlist country", "Other country"],
                                      range=[TONES["risk"], "#8a94a6"]),
                color_title=None,
            )
            watch = dest_df[dest_df["Destination"] == "Sanctions-watchlist country"]
            share = pct(watch["Flagged amount"].sum(), dest_df["Flagged amount"].sum())
            names = ", ".join(watch["Destination country"].tolist()) or "none"
            st.caption(f"**{share:.0f}%** of this flagged money goes to sanctions-watchlist "
                       f"countries ({names}).")
        else:
            st.info("No flagged transactions match the current filters.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**How severe are the alerts?**")
        risk_df = run_query(
            f"""
            SELECT
                CASE
                    WHEN RISK_SCORE >= 90 THEN 'Critical (90-100)'
                    WHEN RISK_SCORE >= 80 THEN 'High (80-89)'
                    WHEN RISK_SCORE >= 70 THEN 'Elevated (70-79)'
                    ELSE 'Below 70'
                END AS RISK_BAND,
                COUNT(*) AS TXN_COUNT
            FROM RISK_DB.CURATED.FCT_TRANSACTION t
            WHERE HAS_AML_FLAG = TRUE {filters}
            GROUP BY RISK_BAND
            """
        )
        if not risk_df.empty:
            risk_df["Transactions"] = risk_df["TXN_COUNT"].astype(int)
            bar_chart(risk_df, "RISK_BAND", "Transactions", "Risk score band",
                      "Flagged transactions",
                      sort=["Critical (90-100)", "High (80-89)", "Elevated (70-79)", "Below 70"])
        else:
            st.info("No data for risk distribution.")

    with col_b:
        st.markdown("**Where are alerts in the review process?**")
        screen_df = run_query(
            f"""
            SELECT SCREENING_STATUS, COUNT(*) AS CNT, SUM(AMOUNT) AS TOTAL_AMOUNT
            FROM RISK_DB.CURATED.FCT_TRANSACTION t
            WHERE HAS_AML_FLAG = TRUE {alert_filter_clause()}
            GROUP BY SCREENING_STATUS
            """
        )
        if not screen_df.empty:
            screen_df["Review stage"] = screen_df["SCREENING_STATUS"].map(
                lambda c: SCREENING_LABELS.get(c, pretty(c)))
            screen_df["Flagged amount"] = screen_df["TOTAL_AMOUNT"].map(num)
            bar_chart(screen_df, "Review stage", "Flagged amount", "Review stage",
                      "Flagged amount (USD)", y_format="$,.2s",
                      sort=[SCREENING_LABELS[k] for k in SCREENING_LABELS])

    st.markdown("---")

    st.subheader("Top flagged customers")
    top_df = run_query(
        f"""
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
        WHERE t.HAS_AML_FLAG = TRUE {filters}
        GROUP BY c.FULL_NAME, c.CUSTOMER_ID, c.RISK_RATING, c.PEP_FLAG, c.SANCTIONS_MATCH_FLAG
        ORDER BY FLAGGED_AMOUNT DESC
        LIMIT 20
        """
    )
    if not top_df.empty:
        st.dataframe(top_df, use_container_width=True, hide_index=True)
    else:
        st.info("No flagged customers match the current filters.")

    st.subheader("Flagged transaction details")
    detail_df = run_query(
        f"""
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
        WHERE t.HAS_AML_FLAG = TRUE {filters}
        ORDER BY t.RISK_SCORE DESC, t.AMOUNT DESC
        LIMIT 100
        """
    )
    if not detail_df.empty:
        st.dataframe(detail_df, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions match the current filters.")


# =========================================================================
# PAGE: ASK THE COPILOT
# =========================================================================
def render_copilot():
    st.caption(
        "The generated SQL is shown with every answer, so the result is explainable. "
        "Works both when running locally and inside Snowflake."
    )

    domain = st.selectbox("Data domain", list(ANALYST_DOMAINS.keys()), key="copilot_domain")
    semantic_view = ANALYST_DOMAINS[domain]

    examples = {
        "Fraud & AML signals": [
            "Which customers have the highest total flagged transaction amount?",
            "How many alerts of each type were generated?",
        ],
        "Regulatory (Basel / IFRS9 / liquidity)": [
            "What is the total risk-weighted assets by asset class?",
            "Which loans have a Basel violation?",
        ],
        "Transactions & accounts (360)": [
            "What is the total transaction amount by channel?",
            "Which accounts have the highest balances?",
        ],
        "Investigation facts": [
            "Show customers who are PEPs with flagged transactions.",
            "Which customers have both sanctions matches and AML alerts?",
        ],
    }
    st.markdown("**Try:** " + "  |  ".join(f"_{q}_" for q in examples[domain]))

    if "copilot_history" not in st.session_state:
        st.session_state.copilot_history = []

    with st.form("copilot_form", clear_on_submit=True):
        question = st.text_input("Your question", placeholder="Ask about your risk data...")
        submitted = st.form_submit_button("Ask")

    if submitted and question.strip():
        with st.spinner("Cortex Analyst is thinking..."):
            interpretation, sql_text, suggestions, error = run_analyst(question.strip(), semantic_view)
        entry = {"q": question.strip(), "domain": domain, "interpretation": interpretation,
                 "sql": sql_text, "suggestions": suggestions, "error": error}
        if error is None and sql_text:
            try:
                entry["df"] = run_query(sql_text)
            except Exception as exc:
                entry["error"] = f"Generated SQL failed to run: {exc}"
        st.session_state.copilot_history.insert(0, entry)

    if st.session_state.copilot_history and st.button("Clear conversation", key="copilot_clear"):
        st.session_state.copilot_history = []
        st.rerun()

    for entry in st.session_state.copilot_history:
        with st.chat_message("user"):
            st.write(entry["q"])
            st.caption(entry["domain"])
        with st.chat_message("assistant"):
            if entry.get("error"):
                st.warning(entry["error"])
            if entry.get("interpretation"):
                st.write(entry["interpretation"])
            if entry.get("suggestions"):
                st.markdown("**You could ask instead:**\n" + "\n".join(f"- {s}" for s in entry["suggestions"]))
            if entry.get("sql"):
                with st.expander("Generated SQL"):
                    st.code(entry["sql"], language="sql")
            df = entry.get("df")
            if df is not None and not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
                numeric = df.select_dtypes("number").columns.tolist()
                if len(df.columns) == 2 and len(numeric) == 1:
                    label = [c for c in df.columns if c not in numeric][0]
                    chart_df = df.copy()
                    chart_df[label] = chart_df[label].map(pretty)
                    bar_chart(chart_df, label, numeric[0], pretty(label), pretty(numeric[0]), height=300)


# =========================================================================
# PAGE: CUSTOMER 360
# =========================================================================
def render_customer360():

    cust_list = run_query(
        """
        SELECT CUSTOMER_ID, FULL_NAME, RISK_RATING, IS_HIGH_RISK
        FROM RISK_DB.CURATED.DIM_CUSTOMER
        WHERE IS_CURRENT = TRUE
        ORDER BY CUSTOMER_ID
        """
    )
    display_names = cust_list.apply(
        lambda r: f"{r['CUSTOMER_ID']} - {r['FULL_NAME']} ({r['RISK_RATING']})", axis=1
    ).tolist()
    selected_display = st.selectbox("Select a customer", display_names, key="c360_customer")
    cust_id = cust_list.iloc[display_names.index(selected_display)]["CUSTOMER_ID"]

    profile = run_query(
        f"""
        SELECT
            CUSTOMER_ID, FULL_NAME, NATIONALITY, COUNTRY_OF_RESIDENCE,
            CUSTOMER_TYPE, INDUSTRY, RISK_RATING, KYC_STATUS,
            KYC_LAST_REVIEWED, ONBOARDING_DATE, PEP_FLAG,
            SANCTIONS_MATCH_FLAG, ANNUAL_INCOME, SOURCE_OF_FUNDS,
            ACCOUNT_PURPOSE, IS_HIGH_RISK, AGE_YEARS, DAYS_SINCE_ONBOARDING
        FROM RISK_DB.CURATED.DIM_CUSTOMER
        WHERE IS_CURRENT = TRUE AND CUSTOMER_ID = '{cust_id}'
        """
    )

    if not profile.empty:
        p = profile.iloc[0]
        rating = str(p["RISK_RATING"])
        kyc = str(p["KYC_STATUS"])
        kyc_insight = {
            "COMPLETED": "Identity checks are complete and up to date",
            "PENDING": "Identity checks are still outstanding",
            "EXPIRED": "Identity checks have lapsed and need refreshing",
        }.get(kyc, "Know-Your-Customer verification status")
        tiles([
            ("Risk rating", rating.title(),
             f"Bank's overall risk classification for this customer ({rating})",
             RATING_TONES.get(rating, "info")),
            ("KYC status", kyc.title(), kyc_insight, KYC_TONES.get(kyc, "info")),
            ("Politically exposed", "Yes" if p["PEP_FLAG"] else "No",
             "A PEP requires enhanced due diligence" if p["PEP_FLAG"]
             else "Not on any politically-exposed-person list",
             flag_tone(p["PEP_FLAG"])),
            ("Sanctions match", "Yes" if p["SANCTIONS_MATCH_FLAG"] else "No",
             "Matches a sanctions watchlist entry - escalate" if p["SANCTIONS_MATCH_FLAG"]
             else "No match against sanctions watchlists",
             flag_tone(p["SANCTIONS_MATCH_FLAG"])),
            ("High risk overall", "Yes" if p["IS_HIGH_RISK"] else "No",
             "Flagged as high risk by the bank's own criteria" if p["IS_HIGH_RISK"]
             else "Not flagged as high risk",
             flag_tone(p["IS_HIGH_RISK"])),
        ])

        with st.expander("Full Customer Profile", expanded=False):
            prof_left, prof_right = st.columns(2)
            with prof_left:
                st.markdown(f"**Name:** {p['FULL_NAME']}")
                st.markdown(f"**Nationality:** {p['NATIONALITY']}")
                st.markdown(f"**Residence:** {p['COUNTRY_OF_RESIDENCE']}")
                st.markdown(f"**Type:** {p['CUSTOMER_TYPE']}")
                st.markdown(f"**Industry:** {p['INDUSTRY']}")
            with prof_right:
                st.markdown(f"**Annual Income:** ${num(p['ANNUAL_INCOME']):,.0f}")
                st.markdown(f"**Source of Funds:** {p['SOURCE_OF_FUNDS']}")
                st.markdown(f"**Account Purpose:** {p['ACCOUNT_PURPOSE']}")
                st.markdown(f"**Onboarded:** {p['ONBOARDING_DATE']}")
                st.markdown(f"**KYC Last Reviewed:** {p['KYC_LAST_REVIEWED']}")

    st.markdown("---")

    st.subheader("Accounts")
    acct_df = run_query(
        f"""
        SELECT
            a.ACCOUNT_ID, a.ACCOUNT_TYPE, a.CURRENCY, a.STATUS,
            a.BALANCE, a.CREDIT_LIMIT, a.RISK_SCORE,
            a.IS_DORMANT, a.IS_OVERDRAWN, a.LAST_ACTIVITY_DATE
        FROM RISK_DB.CURATED.DIM_ACCOUNT a
        WHERE a.IS_CURRENT = TRUE
          AND a.CUSTOMER_ID = '{cust_id}'
        ORDER BY a.ACCOUNT_ID
        """
    )
    if not acct_df.empty:
        st.dataframe(acct_df, use_container_width=True, hide_index=True)
    else:
        st.info("No accounts found for this customer.")

    st.markdown("---")

    # COALESCE keeps the sums at 0 for customers with no transactions (SUM of no rows is NULL).
    txn_sum = run_query(
        f"""
        SELECT
            COUNT(*) AS TOTAL_TXNS,
            COALESCE(SUM(CASE WHEN t.HAS_AML_FLAG THEN 1 ELSE 0 END), 0) AS FLAGGED_TXNS,
            COALESCE(SUM(t.AMOUNT), 0) AS TOTAL_AMOUNT,
            ROUND(AVG(t.RISK_SCORE), 1) AS AVG_RISK
        FROM RISK_DB.CURATED.FCT_TRANSACTION t
        JOIN RISK_DB.CURATED.DIM_CUSTOMER c
            ON t.DIM_CUSTOMER_SK = c.DIM_CUSTOMER_SK AND c.IS_CURRENT = TRUE
        WHERE c.CUSTOMER_ID = '{cust_id}'
        """
    )

    st.subheader("Transaction Summary")
    s = txn_sum.iloc[0]
    total_txns = int(num(s["TOTAL_TXNS"]))
    flagged_txns = int(num(s["FLAGGED_TXNS"]))
    avg_risk = num(s["AVG_RISK"])
    tiles([
        ("Total transactions", f"{total_txns:,}",
         "All transactions recorded for this customer", "info"),
        ("Flagged transactions", f"{flagged_txns:,}",
         f"{pct(flagged_txns, total_txns):.0f}% of their activity raised an AML alert"
         if total_txns else "No transaction activity to screen",
         "risk" if flagged_txns else "good"),
        ("Total value moved", money(s["TOTAL_AMOUNT"]),
         f"Across {total_txns:,} transactions" if total_txns else "No money movement recorded",
         "info"),
        ("Avg risk score", f"{avg_risk:.0f} / 100" if total_txns else "N/A",
         "Average severity across their transactions (higher = more suspicious)"
         if total_txns else "No transactions to score",
         "risk" if avg_risk >= 70 else "warn" if avg_risk >= 40 else "good"),
    ])

    st.markdown("---")

    st.subheader("Transaction Timeline")
    timeline_df = run_query(
        f"""
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
    )
    if not timeline_df.empty:
        # Split AMOUNT into one column per status so st.scatter_chart accepts an
        # explicit colour per series (red = flagged, green = normal). Keeping
        # st.scatter_chart preserves its native zoom/pan behaviour.
        chart_df = timeline_df.copy()
        chart_df["Flagged"] = chart_df["AMOUNT"].where(chart_df["STATUS"] == "FLAGGED")
        chart_df["Normal"] = chart_df["AMOUNT"].where(chart_df["STATUS"] == "NORMAL")
        st.scatter_chart(
            chart_df,
            x="TRANSACTION_DATE",
            y=["Flagged", "Normal"],
            color=[TONES["risk"], TONES["good"]],
        )
    else:
        st.info("No transactions found for this customer.")

    st.markdown("---")

    st.subheader("Transaction History")
    hist_df = run_query(
        f"""
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
    )
    if not hist_df.empty:
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions found.")


# =========================================================================
# PAGE: INVESTIGATION & REPORT BUILDER
# =========================================================================
def render_report():

    inv_list = run_query(
        """
        SELECT c.CUSTOMER_ID, c.FULL_NAME, c.RISK_RATING,
               COUNT(CASE WHEN t.HAS_AML_FLAG THEN 1 END) AS FLAGGED
        FROM RISK_DB.CURATED.DIM_CUSTOMER c
        LEFT JOIN RISK_DB.CURATED.FCT_TRANSACTION t
            ON t.DIM_CUSTOMER_SK = c.DIM_CUSTOMER_SK
        WHERE c.IS_CURRENT = TRUE
        GROUP BY c.CUSTOMER_ID, c.FULL_NAME, c.RISK_RATING
        ORDER BY FLAGGED DESC, c.CUSTOMER_ID
        """
    )
    inv_display = inv_list.apply(
        lambda r: f"{r['CUSTOMER_ID']} - {r['FULL_NAME']} ({int(num(r['FLAGGED']))} flagged)", axis=1
    ).tolist()
    inv_sel = st.selectbox("Select a customer to investigate", inv_display, key="report_customer")
    inv_id = inv_list.iloc[inv_display.index(inv_sel)]["CUSTOMER_ID"]

    profile = run_query(
        f"""
        SELECT CUSTOMER_ID, FULL_NAME, RISK_RATING, KYC_STATUS, PEP_FLAG,
               SANCTIONS_MATCH_FLAG, COUNTRY_OF_RESIDENCE, CUSTOMER_TYPE,
               SOURCE_OF_FUNDS, IS_HIGH_RISK
        FROM RISK_DB.CURATED.DIM_CUSTOMER
        WHERE IS_CURRENT = TRUE AND CUSTOMER_ID = '{inv_id}'
        """
    ).iloc[0]

    signal = run_query(
        f"""
        SELECT
            COUNT(*) AS FLAGGED_TXNS,
            COALESCE(SUM(t.AMOUNT), 0) AS FLAGGED_AMOUNT,
            MAX(t.RISK_SCORE) AS MAX_RISK,
            LISTAGG(DISTINCT t.AML_ALERT_TYPE, ', ') AS ALERT_TYPES
        FROM RISK_DB.CURATED.FCT_TRANSACTION t
        JOIN RISK_DB.CURATED.DIM_CUSTOMER c
            ON t.DIM_CUSTOMER_SK = c.DIM_CUSTOMER_SK AND c.IS_CURRENT = TRUE
        WHERE c.CUSTOMER_ID = '{inv_id}' AND t.HAS_AML_FLAG = TRUE
        """
    ).iloc[0]
    flagged_txns = int(num(signal["FLAGGED_TXNS"]))
    flagged_amount = num(signal["FLAGGED_AMOUNT"])
    max_risk = f"{num(signal['MAX_RISK']):.0f}" if flagged_txns else "N/A"
    alert_types = signal["ALERT_TYPES"] if isinstance(signal["ALERT_TYPES"], str) else ""
    alert_types_pretty = ", ".join(ALERT_LABELS.get(a.strip(), pretty(a.strip()))
                                   for a in alert_types.split(",") if a.strip())

    top_txns = run_query(
        f"""
        SELECT t.TRANSACTION_ID, t.TRANSACTION_DATE, t.TRANSACTION_TYPE, t.AMOUNT,
               t.AML_ALERT_TYPE, t.RISK_SCORE, t.BENEFICIARY_COUNTRY, t.IS_CROSS_BORDER
        FROM RISK_DB.CURATED.FCT_TRANSACTION t
        JOIN RISK_DB.CURATED.DIM_CUSTOMER c
            ON t.DIM_CUSTOMER_SK = c.DIM_CUSTOMER_SK AND c.IS_CURRENT = TRUE
        WHERE c.CUSTOMER_ID = '{inv_id}' AND t.HAS_AML_FLAG = TRUE
        ORDER BY t.RISK_SCORE DESC, t.AMOUNT DESC LIMIT 10
        """
    )

    st.header("1. Signal")
    tiles([
        ("Flagged transactions", f"{flagged_txns:,}", "Transactions that raised an AML alert", "risk"),
        ("Flagged amount", money(flagged_amount), "Total value of the flagged transactions", "warn"),
        ("Max risk score", max_risk, "Most severe single alert (out of 100)", "warn"),
        ("Risk rating", str(profile["RISK_RATING"]), "Customer's current KYC risk rating", "info"),
    ])
    st.markdown(f"**Alert types observed:** {alert_types_pretty or 'None'}")

    st.header("2. Evidence")
    e1, e2, e3 = st.columns(3)
    e1.metric("KYC Status", profile["KYC_STATUS"])
    e2.metric("PEP", "Yes" if profile["PEP_FLAG"] else "No")
    e3.metric("Sanctions Match", "Yes" if profile["SANCTIONS_MATCH_FLAG"] else "No")
    st.markdown(
        f"**Residence:** {profile['COUNTRY_OF_RESIDENCE']}  |  "
        f"**Type:** {profile['CUSTOMER_TYPE']}  |  "
        f"**Source of funds:** {profile['SOURCE_OF_FUNDS']}"
    )
    if not top_txns.empty:
        st.markdown("**Top flagged transactions**")
        st.dataframe(top_txns, use_container_width=True, hide_index=True)
    else:
        st.info("This customer has no flagged transactions.")

    st.header("3. Policy citation")
    policy_query = (alert_types_pretty or str(profile["RISK_RATING"]) or "AML monitoring") + \
        " transaction monitoring suspicious activity"
    policies = search_policies(policy_query, limit=2)
    cited_policy_name, cited_excerpt = "", ""
    if not policies.empty:
        cited_policy_name = str(policies["POLICY_NAME"].iloc[0])
        cited_excerpt = str(policies["FULL_CONTENT"].iloc[0])[:800]
        st.markdown(
            f"**Most relevant policy:** {pretty(cited_policy_name)} "
            f"_(classification: {policies['CLASSIFICATION'].iloc[0]})_"
        )
        with st.expander("Policy excerpt"):
            st.write(cited_excerpt)
    else:
        st.info("No policy match returned.")

    st.header("4. Documented finding")
    findings = st.session_state.setdefault("findings", {})
    if st.button("Generate finding narrative", key="report_generate"):
        facts = f"""Customer: {profile['FULL_NAME']} ({inv_id})
Risk rating: {profile['RISK_RATING']}; High-risk flag: {bool(profile['IS_HIGH_RISK'])}
KYC status: {profile['KYC_STATUS']}; PEP: {bool(profile['PEP_FLAG'])}; Sanctions match: {bool(profile['SANCTIONS_MATCH_FLAG'])}
Residence: {profile['COUNTRY_OF_RESIDENCE']}; Customer type: {profile['CUSTOMER_TYPE']}; Source of funds: {profile['SOURCE_OF_FUNDS']}
Flagged transactions: {flagged_txns}; Flagged amount: {flagged_amount:,.0f}; Max risk score: {max_risk}
Alert types: {alert_types_pretty or 'None'}
Cited policy: {cited_policy_name}"""
        prompt = (
            "You are a financial-crime compliance analyst. Using ONLY the facts below, write a "
            "concise, professional SAR-style investigation finding with these sections: "
            "Summary, Observed Activity, Risk Assessment, Policy Basis, and Recommended Action. "
            "Do not invent facts.\n\nFACTS:\n" + facts
        )
        with st.spinner("Generating finding..."):
            findings[inv_id] = cortex_complete(prompt)

    narrative = findings.get(inv_id)
    if narrative:
        report_md = f"""# Investigation Finding - {profile['FULL_NAME']} ({inv_id})

## Signal
- Flagged transactions: {flagged_txns}
- Flagged amount: ${flagged_amount:,.0f}
- Max risk score: {max_risk}
- Alert types: {alert_types_pretty or 'None'}

## Evidence
- Risk rating: {profile['RISK_RATING']} | KYC: {profile['KYC_STATUS']}
- PEP: {bool(profile['PEP_FLAG'])} | Sanctions match: {bool(profile['SANCTIONS_MATCH_FLAG'])}
- Residence: {profile['COUNTRY_OF_RESIDENCE']} | Type: {profile['CUSTOMER_TYPE']}

## Policy basis
- {cited_policy_name}

## Analyst narrative
{narrative}
"""
        st.markdown(narrative)
        st.download_button(
            "Download finding (Markdown)",
            data=report_md,
            file_name=f"finding_{inv_id}.md",
            mime="text/markdown",
            key="report_download",
        )


# =========================================================================
# ROUTER: landing page, or the selected page with its nav strip
# =========================================================================
RENDERERS = {
    "overview": render_overview,
    "copilot": render_copilot,
    "customer360": render_customer360,
    "report": render_report,
}

current = st.session_state.setdefault("page", "home")
if current not in RENDERERS:
    render_home()
else:
    render_page_nav(current)
    RENDERERS[current]()

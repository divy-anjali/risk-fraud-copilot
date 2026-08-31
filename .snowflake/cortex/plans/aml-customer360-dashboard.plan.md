# AML Monitoring + Customer 360 Streamlit Dashboard

## Context

The RISK_DB database has a fully populated curated star schema with 1,000 transactions (100 AML-flagged), 100 customers, 150 accounts, 60 loans, and 4 semantic views. The dashboard will query the curated tables directly using `st.connection("snowflake")`.

## Dashboard Layout

The app will have two pages using Streamlit's sidebar navigation:

### Page 1: AML Monitoring
- **KPI cards at top**: Total transactions, Flagged count, Flagged %, Average risk score
- **AML Alert Type breakdown**: Bar chart showing counts by alert type (Structuring, Rapid Movement, High-Risk Jurisdiction, Unusual Activity)
- **Risk Score Distribution**: Histogram of risk scores across all flagged transactions
- **Flagged Transactions Table**: Sortable, filterable table of flagged transactions with customer name, amount, type, alert type, screening status
- **Filters in sidebar**: Date range, transaction type, alert type, screening status

### Page 2: Customer 360
- **Customer selector**: Dropdown to pick a customer
- **Customer profile card**: Name, nationality, risk rating, KYC status, PEP/sanctions flags, onboarding date
- **Accounts table**: All accounts for that customer with balances and status
- **Transaction history**: All transactions for that customer with AML flags highlighted
- **Risk timeline**: Chart showing transaction amounts over time, colored by risk level

## Implementation Steps

### Step 1: Scaffold the project
Create the Streamlit app file and configuration. The app will be a single `streamlit_app.py` with multi-page layout using `st.navigation`.

### Step 2: Build the AML Monitoring page
Write the SQL queries and Streamlit components for the AML overview: KPI metrics, alert type charts, risk distribution, and the flagged transactions data table.

### Step 3: Build the Customer 360 page
Write the customer lookup, profile card, accounts grid, transaction history, and risk timeline chart.

### Step 4: Add sidebar filters and theming
Add global filters (date range, risk level), Snowflake theme colors, and the sidebar navigation.

### Step 5: Test locally
Run the app with `streamlit run` to verify it works against the Snowflake data.

### Step 6: Deploy to Snowflake (optional)
Prepare `snowflake.yml` and deploy using `snow streamlit deploy` if the user wants it running in Snowsight.

## Verification
- Run locally with `streamlit run streamlit_app.py`
- Verify KPI cards show correct counts (1000 total txns, 100 flagged)
- Verify Customer 360 shows correct data when selecting different customers
- Verify charts render correctly

## Critical Files
- `streamlit_app.py` -- The entire dashboard application
- `snowflake.yml` -- Deployment manifest for SiS (if deploying)

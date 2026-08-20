# Synthetic Risk Data Generator

## Overview

The `RISK_DB.RAW.GENERATE_RISK_DATA()` stored procedure generates synthetic banking risk and fraud data for development, testing, and demo purposes. Each execution produces a complete, internally consistent dataset that simulates a mid-size bank's risk portfolio.

## Usage

```sql
CALL RISK_DB.RAW.GENERATE_RISK_DATA();
```

**Returns:** A summary string with run ID, file counts, and violation statistics.

**Runtime:** Python 3.11 with `snowflake-snowpark-python` and `fpdf2` packages. Executes as caller.

## Output

Each run creates a timestamped folder (e.g., `20260819_072321/`) under two internal stages:

| Stage | Files | Format |
|-------|-------|--------|
| `@RISK_DB.RAW.RISK_FRAUD_DATA_STAGE/<run_id>/` | 8 CSV files | Comma-delimited, header row, UTF-8 |
| `@RISK_DB.RAW.POLICIES_STAGE/<run_id>/` | 6 PDF files | Single-page policy documents |

## Datasets Generated

### 1. CUSTOMER_MASTER (100 rows)

Customer KYC and risk profile data.

| Column | Description |
|--------|-------------|
| CUSTOMER_ID | Unique identifier (CUST-0001 to CUST-0100) |
| FIRST_NAME, LAST_NAME, FULL_NAME | Customer name |
| DATE_OF_BIRTH | Between 1955–1998 |
| NATIONALITY, COUNTRY_OF_RESIDENCE | From 17 country pool |
| CUSTOMER_TYPE | INDIVIDUAL or CORPORATE |
| INDUSTRY | Banking, Real Estate, Crypto, etc. (10 industries) |
| RISK_RATING | LOW, MEDIUM, or HIGH |
| KYC_STATUS | COMPLETED, PENDING, or EXPIRED |
| KYC_LAST_REVIEWED, ONBOARDING_DATE | Date fields |
| PEP_FLAG | Politically Exposed Person indicator |
| SANCTIONS_MATCH_FLAG | Sanctions watchlist match indicator |
| ANNUAL_INCOME | 20,000–5,000,000 |
| SOURCE_OF_FUNDS | EMPLOYMENT, BUSINESS, INHERITANCE, INVESTMENT, UNKNOWN |
| ACCOUNT_PURPOSE | SAVINGS, TRADING, BUSINESS_OPS, SALARY, INVESTMENT |
| STATUS | Account status |

**Built-in risk scenarios:**
- Customers 1–5: Match sanctioned entity names (SANCTIONS_MATCH_FLAG = Y)
- Customers 6–8: Politically Exposed Persons (PEP_FLAG = Y)
- Customers from high-risk countries (IR, KP, RU, NG, AE) are automatically rated HIGH

### 2. ACCOUNT_MASTER (150 rows)

Bank accounts linked to customers.

| Column | Description |
|--------|-------------|
| ACCOUNT_ID | ACC-0001 to ACC-0150 |
| CUSTOMER_ID | FK to CUSTOMER_MASTER |
| ACCOUNT_TYPE | SAVINGS, CHECKING, BUSINESS, INVESTMENT, LOAN, FIXED_DEPOSIT |
| CURRENCY | USD, EUR, GBP, CHF, SGD, AED, JPY, INR |
| OPENING_DATE | 2015–2024 |
| STATUS | ACTIVE, DORMANT, FROZEN, or CLOSED |
| BRANCH_CODE, COUNTRY | Branch and geography |
| BALANCE | 0–10,000,000 |
| CREDIT_LIMIT | Up to 500,000 (40% of accounts) |
| OVERDRAFT_LIMIT | Up to 50,000 (30% of accounts) |
| LAST_ACTIVITY_DATE | 2024 |
| RISK_SCORE | 1–100 |

### 3. TRANSACTION_FACT (1,000 rows)

Transactions with embedded AML scenarios.

| Column | Description |
|--------|-------------|
| TRANSACTION_ID | TXN-000001 to TXN-001000 |
| ACCOUNT_ID, CUSTOMER_ID | FK references |
| TRANSACTION_DATE, TRANSACTION_TIME | 2024 date range |
| TRANSACTION_TYPE | WIRE_TRANSFER, CASH_DEPOSIT, CRYPTO_PURCHASE, etc. (10 types) |
| AMOUNT | 10–10,000,000 depending on scenario |
| CURRENCY, DIRECTION, CHANNEL | Transaction metadata |
| ORIGINATOR_*, BENEFICIARY_* | Counterparty details |
| PURPOSE_CODE | TRADE, SALARY, INVESTMENT, PERSONAL, LOAN_REPAY, GOODS_SERVICES |
| AML_FLAG | Y/N — whether transaction triggered an AML alert |
| AML_ALERT_TYPE | STRUCTURING, RAPID_MOVEMENT, HIGH_RISK_JURISDICTION, etc. |
| RISK_SCORE | 1–100 |
| SCREENING_STATUS | CLEARED, ALERT_GENERATED, UNDER_REVIEW, ESCALATED, SAR_FILED |
| IS_CASH | Whether cash transaction |
| CTR_FILED | Currency Transaction Report filed (cash >= $10,000) |

**Built-in AML scenarios (100 of 1,000 transactions flagged):**

| Rows | Scenario | Pattern |
|------|----------|---------|
| 1–25 | Structuring | Cash deposits $9,000–$9,999 (just below CTR threshold) |
| 26–50 | Rapid Movement / Round-Tripping | Wire/internal transfers $50k–$2M |
| 51–75 | High-Risk Jurisdiction / Fraud | Transfers to IR, KP, RU, NG, AE |
| 76–100 | Unusual Activity / Concentration | Large transactions $500k–$10M |

### 4. LOAN_MASTER (60 rows)

Loan book with Basel credit risk metrics.

| Column | Description |
|--------|-------------|
| LOAN_ID | LOAN-0001 to LOAN-0060 |
| CUSTOMER_ID, ACCOUNT_ID | FK references |
| LOAN_TYPE | MORTGAGE, PERSONAL, BUSINESS, AUTO, CREDIT_LINE, TRADE_FINANCE |
| LOAN_AMOUNT, OUTSTANDING_BALANCE | Principal figures |
| INTEREST_RATE | 2.5%–18% |
| ORIGINATION_DATE, MATURITY_DATE | Lifecycle dates |
| COLLATERAL_TYPE, COLLATERAL_VALUE, LTV_RATIO | Collateral coverage |
| INTERNAL_RATING | AAA to D |
| PD | Probability of Default |
| LGD | Loss Given Default |
| EAD | Exposure at Default |
| RISK_WEIGHT_PCT | Basel risk weight |
| RWA | Risk-Weighted Assets |
| EXPECTED_LOSS | PD × LGD × EAD |
| CAPITAL_REQUIREMENT | RWA × 8% |
| BASEL_APPROACH | SA, FIRB, or AIRB |
| ASSET_CLASS | CORPORATE, RETAIL, SME, SOVEREIGN, BANK |
| STATUS | PERFORMING, WATCHLIST, SUBSTANDARD, DOUBTFUL, LOSS |
| BASEL_VIOLATION_FLAG | Y/N |

**Built-in Basel violations (loans 1–10):**
- Under-collateralized (LTV > 200%)
- High PD (5%–35%)
- High LGD (60%–95%)
- Ratings CCC or below
- Status: WATCHLIST, SUBSTANDARD, DOUBTFUL, or LOSS

### 5. LOAN_PERFORMANCE (200 rows)

IFRS9 staging and expected credit loss tracking.

| Column | Description |
|--------|-------------|
| PERFORMANCE_ID | PERF-0001 to PERF-0200 |
| LOAN_ID, CUSTOMER_ID | FK references |
| REPORT_DATE | 2024 |
| DAYS_PAST_DUE | 0–360 |
| DELINQUENCY_STATUS | CURRENT, DELINQUENT, or DEFAULT |
| PAYMENT_AMOUNT_DUE, PAYMENT_AMOUNT_RECEIVED | Payment data |
| OUTSTANDING_PRINCIPAL, ACCRUED_INTEREST | Balance data |
| PROVISION_AMOUNT | Loan loss provision |
| STAGE_IFRS9 | STAGE_1 (< 30 DPD), STAGE_2 (30–89), STAGE_3 (90+) |
| ECL_AMOUNT | Expected Credit Loss |
| RESTRUCTURED_FLAG | Whether loan has been restructured |
| WRITE_OFF_FLAG | Whether loan has been written off (DPD >= 360) |
| RECOVERY_AMOUNT | Amount recovered post-default |
| RISK_MIGRATION | UPGRADE, STABLE, or DOWNGRADE |

### 6. DEPOSIT_BALANCES (150 rows)

Deposit data with Basel III liquidity risk metrics.

| Column | Description |
|--------|-------------|
| DEPOSIT_ID | DEP-0001 to DEP-0150 |
| ACCOUNT_ID, CUSTOMER_ID | FK references |
| DEPOSIT_TYPE | DEMAND, SAVINGS, TERM_30D through TERM_2Y |
| BALANCE, CURRENCY | Deposit amount |
| EFFECTIVE_DATE, MATURITY_DATE | Dates (maturity only for term deposits) |
| INTEREST_RATE | 0.5%–6% |
| INSURED_AMOUNT | Capped at 250,000 |
| UNINSURED_AMOUNT | Balance above insurance limit |
| STABILITY_FACTOR | 0.1–0.95 (how stable the deposit is) |
| RUN_OFF_FACTOR | 1 - STABILITY_FACTOR |
| LCR_CATEGORY | RETAIL_STABLE, RETAIL_LESS_STABLE, or WHOLESALE_UNSECURED |
| NSFR_CATEGORY | STABLE_FUNDING or LESS_STABLE_FUNDING |
| CONCENTRATION_FLAG | Y if balance > 10M |
| LARGE_DEPOSIT_FLAG | Y if balance > 5M |
| LIQUIDITY_VIOLATION_FLAG | Y/N |

**Built-in liquidity violations (deposits 1–15):**
- Large demand/savings deposits ($5M–$100M)
- Low stability factors (0.1–0.4) indicating run risk

### 7. PEP_LIST (15 rows)

Politically Exposed Persons reference list.

| Column | Description |
|--------|-------------|
| PEP_ID | PEP-0001 to PEP-0015 |
| FULL_NAME | Name of the PEP |
| POSITION | Head of State, Minister, Senator, Governor, etc. |
| COUNTRY | Country of political exposure |
| PEP_TIER | TIER_1 (heads of state), TIER_2 (ministers), TIER_3 (associates) |
| RELATIONSHIP_TYPE | DIRECT, FAMILY_MEMBER, or CLOSE_ASSOCIATE |
| DATE_ADDED | 2015–2024 |
| STATUS | ACTIVE or FORMER |
| SOURCE | WORLD_CHECK, DOW_JONES, or INTERNAL |

### 8. SANCTIONS_WATCHLIST (20 rows)

Sanctions screening reference list.

| Column | Description |
|--------|-------------|
| WATCHLIST_ID | SAN-0001 to SAN-0020 |
| ENTITY_NAME | Sanctioned entity name |
| ENTITY_TYPE | INDIVIDUAL or ORGANIZATION |
| SOURCE_LIST | OFAC_SDN, UN_SANCTIONS, EU_SANCTIONS, or UK_HMT |
| COUNTRY | High-risk country (IR, KP, RU, NG, AE) |
| DATE_LISTED | 2018–2024 |
| REASON | Terrorism Financing, WMD Proliferation, etc. |
| STATUS | ACTIVE |
| MATCH_SCORE_THRESHOLD | 85, 90, or 95 (fuzzy match threshold) |

## Policy Documents (6 PDFs)

Single-page PDF summaries of regulatory policies:

| File | Content |
|------|---------|
| `AML_Policy.pdf` | Anti-Money Laundering — screening thresholds, watchlist sources |
| `Transaction_Monitoring_Policy.pdf` | Structuring detection rules, round-tripping patterns |
| `Fraud_Risk_Management_Policy.pdf` | Fraud detection scenarios, triage SLAs |
| `Basel_Credit_Risk_Policy.pdf` | RWA formulas, EL calculation, violation criteria |
| `Basel_Liquidity_Risk_Policy.pdf` | LCR/NSFR thresholds, violation triggers |
| `Capital_Adequacy_Policy.pdf` | CET1/T1/Total capital minimums, buffer breach rules |

## Data Relationships

```
CUSTOMER_MASTER (1)──┬──(N) ACCOUNT_MASTER
                     │         │
                     │         ├──(N) TRANSACTION_FACT
                     │         │
                     │         └──(N) DEPOSIT_BALANCES
                     │
                     ├──(N) LOAN_MASTER
                     │         │
                     │         └──(N) LOAN_PERFORMANCE
                     │
                     ├── matched against ── SANCTIONS_WATCHLIST
                     │
                     └── screened against ── PEP_LIST
```

## Randomization and Reproducibility

- Each run produces **different data** (no fixed seed)
- Row counts are fixed per run (100 customers, 150 accounts, 1000 transactions, etc.)
- Risk scenarios are deterministic by row position (e.g., first 10 loans always have Basel violations)
- The run ID (timestamp) ensures multiple runs don't overwrite each other

## Running Multiple Times

Each call creates a new timestamped subfolder. The downstream ingestion pipeline (`LOAD_NEW_CSV_FILES`) uses `COPY INTO ... FORCE = FALSE`, which loads each file exactly once based on Snowflake's 64-day file metadata cache. Running the generator multiple times will produce new data batches that append to the raw tables with distinct `_SOURCE_FILE` values.


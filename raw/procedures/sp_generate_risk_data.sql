-- Stored Procedure: SP_GENERATE_RISK_DATA
-- Generates synthetic banking risk data and loads to stages
-- Usage: CALL RISK_DB.RAW.SP_GENERATE_RISK_DATA();
--
-- Outputs:
--   8 CSV files -> @RISK_DB.RAW.RISK_FRAUD_DATA_STAGE/<timestamp>/
--   6 PDF files -> @RISK_DB.RAW.POLICIES_STAGE/<timestamp>/
--
-- Each run creates a new timestamp folder for versioning.

CREATE OR REPLACE PROCEDURE RISK_DB.RAW.SP_GENERATE_RISK_DATA()
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'fpdf2')
HANDLER = 'run'
EXECUTE AS CALLER
AS
$$
import random
import os
import csv
import tempfile
from datetime import datetime, timedelta
from snowflake.snowpark import Session

def rand_date(start, end):
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))

def rand_amount(low, high):
    return round(random.uniform(low, high), 2)

def run(session):
    RUN_ID = datetime.now().strftime('%Y%m%d_%H%M%S')
    DATA_STAGE = 'RISK_DB.RAW.RISK_FRAUD_DATA_STAGE'
    POLICIES_STAGE = 'RISK_DB.RAW.POLICIES_STAGE'

    COUNTRIES = ['US','UK','DE','CH','SG','AE','NG','IR','KP','RU','CN','IN','BR','JP','CA','FR','AU']
    HIGH_RISK_COUNTRIES = ['IR','KP','RU','NG','AE']
    INDUSTRIES = ['Banking','Real Estate','Import/Export','Crypto','Retail','Manufacturing','Consulting','Oil & Gas','Technology','Healthcare']
    CURRENCIES = ['USD','EUR','GBP','CHF','SGD','AED','JPY','INR']
    ACCT_TYPES = ['SAVINGS','CHECKING','BUSINESS','INVESTMENT','LOAN','FIXED_DEPOSIT']
    TXN_TYPES = ['WIRE_TRANSFER','CASH_DEPOSIT','CASH_WITHDRAWAL','INTERNAL_TRANSFER','CHECK_DEPOSIT','CARD_PAYMENT','CRYPTO_PURCHASE','TRADE_SETTLEMENT','LOAN_DISBURSEMENT','FX_CONVERSION']
    CHANNELS = ['BRANCH','ONLINE','MOBILE','ATM','SWIFT','CORRESPONDENT']
    LOAN_TYPES = ['MORTGAGE','PERSONAL','BUSINESS','AUTO','CREDIT_LINE','TRADE_FINANCE']
    COLLATERAL_TYPES = ['REAL_ESTATE','SECURITIES','CASH_DEPOSIT','EQUIPMENT','NONE','INVENTORY']
    DEPOSIT_TYPES = ['DEMAND','SAVINGS','TERM_30D','TERM_90D','TERM_180D','TERM_1Y','TERM_2Y']

    SANCTIONED_NAMES = ['Ahmad Al-Rashid','Viktor Petrov','Kim Sung-Ho','Ali Khamenei Jr','Dmitry Volkov',
        'Hassan Nasrallah II','Yuri Kozlov','Omar Al-Bashir III','Chen Wei-Lin','Abdul Karim',
        'Sergei Ivanov','Mohammed Al-Faisal','Park Chul-Soo','Reza Mohammadi','Igor Smirnov',
        'Fatima Al-Zahra','Boris Kuznetsov','Tariq Hussain','Li Xiao-Peng','Andrei Popov']
    PEP_NAMES = ['Carlos Mendez','Vladimir Orlov','Sheikh Al-Maktoum','Gen. Zhao Wei','Minister Adebayo',
        'Sen. Ricardo Torres','Amb. Jean-Pierre Dupont','Gov. Hiroshi Tanaka','PM Alexei Navalny Jr',
        'Dir. Fatou Diallo','Dep. Maria Santos','Judge Kwame Asante','Sec. Li Qiang',
        'Pres. Mikhail Sorokin','Min. Aisha Bello']
    FIRST_NAMES = ['James','Maria','Ahmed','Yuki','Olga','Chen','Fatima','Robert','Anna','Raj',
                   'Sarah','Mohammed','Lisa','Ivan','Priya','John','Elena','David','Aisha','Thomas']
    LAST_NAMES = ['Smith','Petrov','Al-Rashid','Tanaka','Mueller','Wang','Hassan','Johnson','Kim','Patel',
                  'Brown','Ivanova','Santos','Kozlov','Sharma','Wilson','Volkov','Martinez','Li','Anderson']

    # --- Generate all datasets ---
    sanctions = []
    for i, name in enumerate(SANCTIONED_NAMES, 1):
        sanctions.append({'WATCHLIST_ID': f'SAN-{i:04d}','ENTITY_NAME': name,
            'ENTITY_TYPE': random.choice(['INDIVIDUAL','ORGANIZATION']),
            'SOURCE_LIST': random.choice(['OFAC_SDN','UN_SANCTIONS','EU_SANCTIONS','UK_HMT']),
            'COUNTRY': random.choice(HIGH_RISK_COUNTRIES),
            'DATE_LISTED': rand_date(datetime(2018,1,1),datetime(2024,6,1)).strftime('%Y-%m-%d'),
            'REASON': random.choice(['Terrorism Financing','WMD Proliferation','Narcotics Trafficking','Corruption','Human Rights Abuse']),
            'STATUS': 'ACTIVE','MATCH_SCORE_THRESHOLD': random.choice([85,90,95])})

    peps = []
    for i, name in enumerate(PEP_NAMES, 1):
        peps.append({'PEP_ID': f'PEP-{i:04d}','FULL_NAME': name,
            'POSITION': random.choice(['Head of State','Minister','Senator','Governor','Ambassador','Military General','Judge','Central Bank Director']),
            'COUNTRY': random.choice(COUNTRIES),'PEP_TIER': random.choice(['TIER_1','TIER_2','TIER_3']),
            'RELATIONSHIP_TYPE': random.choice(['DIRECT','FAMILY_MEMBER','CLOSE_ASSOCIATE']),
            'DATE_ADDED': rand_date(datetime(2015,1,1),datetime(2024,1,1)).strftime('%Y-%m-%d'),
            'STATUS': random.choice(['ACTIVE','ACTIVE','ACTIVE','FORMER']),
            'SOURCE': random.choice(['WORLD_CHECK','DOW_JONES','INTERNAL'])})

    customers = []
    for i in range(1, 101):
        fname = random.choice(FIRST_NAMES); lname = random.choice(LAST_NAMES)
        country = random.choice(COUNTRIES)
        is_high_risk = country in HIGH_RISK_COUNTRIES or random.random() < 0.15
        if i <= 5:
            parts = SANCTIONED_NAMES[i-1].split(); fname, lname = parts[0], parts[-1]
            country = random.choice(HIGH_RISK_COUNTRIES); is_high_risk = True
        elif i in [6,7,8]:
            parts = PEP_NAMES[i-6].split(); fname, lname = parts[0], parts[-1]
        customers.append({'CUSTOMER_ID': f'CUST-{i:04d}','FIRST_NAME': fname,'LAST_NAME': lname,
            'FULL_NAME': f'{fname} {lname}',
            'DATE_OF_BIRTH': rand_date(datetime(1955,1,1),datetime(1998,12,31)).strftime('%Y-%m-%d'),
            'NATIONALITY': country,
            'COUNTRY_OF_RESIDENCE': country if random.random() < 0.8 else random.choice(COUNTRIES),
            'CUSTOMER_TYPE': random.choice(['INDIVIDUAL','INDIVIDUAL','CORPORATE','CORPORATE']),
            'INDUSTRY': random.choice(INDUSTRIES),
            'RISK_RATING': 'HIGH' if is_high_risk else random.choice(['LOW','LOW','MEDIUM','MEDIUM','HIGH']),
            'KYC_STATUS': random.choice(['COMPLETED','COMPLETED','COMPLETED','PENDING','EXPIRED']),
            'KYC_LAST_REVIEWED': rand_date(datetime(2022,1,1),datetime(2024,12,1)).strftime('%Y-%m-%d'),
            'ONBOARDING_DATE': rand_date(datetime(2015,1,1),datetime(2024,6,1)).strftime('%Y-%m-%d'),
            'PEP_FLAG': 'Y' if i in [6,7,8] else ('Y' if random.random() < 0.05 else 'N'),
            'SANCTIONS_MATCH_FLAG': 'Y' if i <= 5 else 'N',
            'ANNUAL_INCOME': rand_amount(20000,5000000),
            'SOURCE_OF_FUNDS': random.choice(['EMPLOYMENT','BUSINESS','INHERITANCE','INVESTMENT','UNKNOWN']),
            'ACCOUNT_PURPOSE': random.choice(['SAVINGS','TRADING','BUSINESS_OPS','SALARY','INVESTMENT']),
            'STATUS': 'ACTIVE'})

    accounts = []
    for i in range(1, 151):
        cust = random.choice(customers)
        accounts.append({'ACCOUNT_ID': f'ACC-{i:04d}','CUSTOMER_ID': cust['CUSTOMER_ID'],
            'ACCOUNT_TYPE': random.choice(ACCT_TYPES),'CURRENCY': random.choice(CURRENCIES),
            'OPENING_DATE': rand_date(datetime(2015,1,1),datetime(2024,6,1)).strftime('%Y-%m-%d'),
            'STATUS': random.choice(['ACTIVE','ACTIVE','ACTIVE','DORMANT','FROZEN','CLOSED']),
            'BRANCH_CODE': f'BR-{random.randint(100,999)}','COUNTRY': cust['COUNTRY_OF_RESIDENCE'],
            'BALANCE': rand_amount(0,10000000),
            'CREDIT_LIMIT': rand_amount(5000,500000) if random.random() < 0.4 else 0,
            'OVERDRAFT_LIMIT': rand_amount(1000,50000) if random.random() < 0.3 else 0,
            'LAST_ACTIVITY_DATE': rand_date(datetime(2024,1,1),datetime(2024,12,1)).strftime('%Y-%m-%d'),
            'RISK_SCORE': random.randint(1,100)})

    transactions = []
    for i in range(1, 1001):
        acct = random.choice(accounts)
        txn_date = rand_date(datetime(2024,1,1),datetime(2024,12,15))
        txn_type = random.choice(TXN_TYPES); beneficiary_country = random.choice(COUNTRIES)
        amount = rand_amount(10,500000); aml_flag = 'N'; aml_alert_type = ''
        screening_status = 'CLEARED'; risk_score = random.randint(1,50)
        if i <= 25:
            amount = rand_amount(9000,9999); txn_type = 'CASH_DEPOSIT'; acct = accounts[i % 10]
            aml_flag = 'Y'; aml_alert_type = 'STRUCTURING'; risk_score = random.randint(75,100)
            screening_status = random.choice(['ALERT_GENERATED','UNDER_REVIEW','SAR_FILED'])
        elif i <= 50:
            amount = rand_amount(50000,2000000); txn_type = random.choice(['WIRE_TRANSFER','INTERNAL_TRANSFER'])
            aml_flag = 'Y'; aml_alert_type = random.choice(['RAPID_MOVEMENT','ROUND_TRIPPING'])
            risk_score = random.randint(80,100); screening_status = random.choice(['ALERT_GENERATED','ESCALATED','SAR_FILED'])
        elif i <= 75:
            amount = rand_amount(15000,1000000); txn_type = random.choice(['WIRE_TRANSFER','CRYPTO_PURCHASE','CARD_PAYMENT'])
            beneficiary_country = random.choice(HIGH_RISK_COUNTRIES)
            aml_flag = 'Y'; aml_alert_type = random.choice(['HIGH_RISK_JURISDICTION','FRAUD_SUSPICION','UNUSUAL_ACTIVITY'])
            risk_score = random.randint(70,100); screening_status = random.choice(['ALERT_GENERATED','UNDER_REVIEW','ESCALATED'])
        elif i <= 100:
            amount = rand_amount(500000,10000000); txn_type = random.choice(['WIRE_TRANSFER','FX_CONVERSION','TRADE_SETTLEMENT'])
            aml_flag = 'Y'; aml_alert_type = random.choice(['UNUSUAL_ACTIVITY','CONCENTRATION_RISK','LIQUIDITY_STRESS'])
            risk_score = random.randint(72,95); screening_status = random.choice(['ALERT_GENERATED','UNDER_REVIEW'])
        transactions.append({'TRANSACTION_ID': f'TXN-{i:06d}','ACCOUNT_ID': acct['ACCOUNT_ID'],
            'CUSTOMER_ID': acct['CUSTOMER_ID'],'TRANSACTION_DATE': txn_date.strftime('%Y-%m-%d'),
            'TRANSACTION_TIME': f'{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}',
            'TRANSACTION_TYPE': txn_type,'AMOUNT': amount,'CURRENCY': acct['CURRENCY'],
            'DIRECTION': random.choice(['CREDIT','DEBIT']),'CHANNEL': random.choice(CHANNELS),
            'ORIGINATOR_NAME': acct['CUSTOMER_ID'],'ORIGINATOR_COUNTRY': acct['COUNTRY'],
            'BENEFICIARY_NAME': f'BEN-{random.randint(1000,9999)}','BENEFICIARY_COUNTRY': beneficiary_country,
            'BENEFICIARY_BANK': f'BANK-{random.choice(["SWIFT","LOCAL"])}-{random.randint(100,999)}',
            'PURPOSE_CODE': random.choice(['TRADE','SALARY','INVESTMENT','PERSONAL','LOAN_REPAY','GOODS_SERVICES']),
            'AML_FLAG': aml_flag,'AML_ALERT_TYPE': aml_alert_type,'RISK_SCORE': risk_score,
            'SCREENING_STATUS': screening_status,
            'IS_CASH': 'Y' if txn_type in ['CASH_DEPOSIT','CASH_WITHDRAWAL'] else 'N',
            'CTR_FILED': 'Y' if (txn_type in ['CASH_DEPOSIT','CASH_WITHDRAWAL'] and amount >= 10000) else 'N'})

    loans = []
    for i in range(1, 61):
        cust = customers[(i-1) % 100]
        cust_accounts = [a for a in accounts if a['CUSTOMER_ID'] == cust['CUSTOMER_ID']]
        acct = cust_accounts[0] if cust_accounts else random.choice(accounts)
        loan_amount = rand_amount(10000,50000000); is_basel_violation = i <= 10
        if is_basel_violation:
            collateral_value = loan_amount * random.uniform(0.2,0.5)
            risk_weight = random.choice([100,150,200]); pd = round(random.uniform(0.05,0.35),4)
            lgd = round(random.uniform(0.6,0.95),4); rating = random.choice(['CCC','CC','C','D'])
            status = random.choice(['WATCHLIST','SUBSTANDARD','DOUBTFUL','LOSS'])
        else:
            collateral_value = loan_amount * random.uniform(0.8,1.5)
            risk_weight = random.choice([20,35,50,75,100]); pd = round(random.uniform(0.001,0.05),4)
            lgd = round(random.uniform(0.2,0.5),4); rating = random.choice(['AAA','AA','A','BBB','BB'])
            status = random.choice(['PERFORMING','PERFORMING','PERFORMING','WATCHLIST'])
        ead = round(loan_amount * random.uniform(0.8,1.0),2); rwa = round(ead * risk_weight / 100,2)
        loans.append({'LOAN_ID': f'LOAN-{i:04d}','CUSTOMER_ID': cust['CUSTOMER_ID'],
            'ACCOUNT_ID': acct['ACCOUNT_ID'],'LOAN_TYPE': random.choice(LOAN_TYPES),
            'LOAN_AMOUNT': loan_amount,'OUTSTANDING_BALANCE': round(loan_amount * random.uniform(0.3,1.0),2),
            'CURRENCY': random.choice(['USD','EUR','GBP']),'INTEREST_RATE': round(random.uniform(2.5,18.0),2),
            'ORIGINATION_DATE': rand_date(datetime(2018,1,1),datetime(2024,6,1)).strftime('%Y-%m-%d'),
            'MATURITY_DATE': rand_date(datetime(2025,1,1),datetime(2035,12,31)).strftime('%Y-%m-%d'),
            'COLLATERAL_TYPE': random.choice(COLLATERAL_TYPES),'COLLATERAL_VALUE': round(collateral_value,2),
            'LTV_RATIO': round(loan_amount / collateral_value * 100,2) if collateral_value > 0 else 999.99,
            'INTERNAL_RATING': rating,'PD': pd,'LGD': lgd,'EAD': ead,
            'RISK_WEIGHT_PCT': risk_weight,'RWA': rwa,
            'EXPECTED_LOSS': round(pd * lgd * ead,2),'CAPITAL_REQUIREMENT': round(rwa * 0.08,2),
            'BASEL_APPROACH': random.choice(['SA','FIRB','AIRB']),
            'ASSET_CLASS': random.choice(['CORPORATE','RETAIL','SME','SOVEREIGN','BANK']),
            'STATUS': status,'BASEL_VIOLATION_FLAG': 'Y' if is_basel_violation else 'N'})

    loan_performance = []
    for i in range(1, 201):
        loan = loans[(i-1) % 60]
        is_delinquent = loan['BASEL_VIOLATION_FLAG'] == 'Y' and random.random() < 0.6
        dpd = random.randint(30,360) if is_delinquent else random.randint(0,29)
        loan_performance.append({'PERFORMANCE_ID': f'PERF-{i:04d}','LOAN_ID': loan['LOAN_ID'],
            'CUSTOMER_ID': loan['CUSTOMER_ID'],
            'REPORT_DATE': rand_date(datetime(2024,1,1),datetime(2024,12,1)).strftime('%Y-%m-%d'),
            'DAYS_PAST_DUE': dpd,
            'DELINQUENCY_STATUS': 'DEFAULT' if dpd >= 90 else ('DELINQUENT' if dpd >= 30 else 'CURRENT'),
            'PAYMENT_AMOUNT_DUE': rand_amount(500,50000),
            'PAYMENT_AMOUNT_RECEIVED': rand_amount(0,50000) if not is_delinquent else rand_amount(0,5000),
            'OUTSTANDING_PRINCIPAL': round(loan['OUTSTANDING_BALANCE'] * random.uniform(0.8,1.0),2),
            'ACCRUED_INTEREST': rand_amount(100,50000),
            'PROVISION_AMOUNT': rand_amount(10000,500000) if dpd >= 90 else rand_amount(0,10000),
            'STAGE_IFRS9': 'STAGE_3' if dpd >= 90 else ('STAGE_2' if dpd >= 30 else 'STAGE_1'),
            'ECL_AMOUNT': rand_amount(50000,2000000) if dpd >= 90 else rand_amount(100,50000),
            'RESTRUCTURED_FLAG': 'Y' if is_delinquent and random.random() < 0.3 else 'N',
            'WRITE_OFF_FLAG': 'Y' if dpd >= 360 else 'N',
            'RECOVERY_AMOUNT': rand_amount(0,100000) if dpd >= 180 else 0,
            'RISK_MIGRATION': random.choice(['DOWNGRADE','STABLE','UPGRADE']) if dpd < 90 else 'DOWNGRADE'})

    deposit_balances = []
    for i in range(1, 151):
        acct = accounts[(i-1) % 150]; is_liquidity_violation = i <= 15
        if is_liquidity_violation:
            balance = rand_amount(5000000,100000000); dep_type = random.choice(['DEMAND','SAVINGS'])
            stability_factor = round(random.uniform(0.1,0.4),2)
        else:
            balance = rand_amount(1000,50000000); dep_type = random.choice(DEPOSIT_TYPES)
            stability_factor = round(random.uniform(0.6,0.95),2)
        deposit_balances.append({'DEPOSIT_ID': f'DEP-{i:04d}','ACCOUNT_ID': acct['ACCOUNT_ID'],
            'CUSTOMER_ID': acct['CUSTOMER_ID'],'DEPOSIT_TYPE': dep_type,'BALANCE': balance,
            'CURRENCY': acct['CURRENCY'],
            'EFFECTIVE_DATE': rand_date(datetime(2024,1,1),datetime(2024,12,1)).strftime('%Y-%m-%d'),
            'MATURITY_DATE': rand_date(datetime(2025,1,1),datetime(2027,12,31)).strftime('%Y-%m-%d') if 'TERM' in dep_type else '',
            'INTEREST_RATE': round(random.uniform(0.5,6.0),2),
            'INSURED_AMOUNT': min(balance,250000),'UNINSURED_AMOUNT': max(0,balance - 250000),
            'STABILITY_FACTOR': stability_factor,'RUN_OFF_FACTOR': round(1 - stability_factor,2),
            'LCR_CATEGORY': 'RETAIL_STABLE' if stability_factor >= 0.7 else ('RETAIL_LESS_STABLE' if stability_factor >= 0.5 else 'WHOLESALE_UNSECURED'),
            'NSFR_CATEGORY': 'STABLE_FUNDING' if 'TERM' in dep_type and stability_factor >= 0.7 else 'LESS_STABLE_FUNDING',
            'CONCENTRATION_FLAG': 'Y' if balance > 10000000 else 'N',
            'LARGE_DEPOSIT_FLAG': 'Y' if balance > 5000000 else 'N',
            'LIQUIDITY_VIOLATION_FLAG': 'Y' if is_liquidity_violation else 'N'})

    # --- Write CSVs to stage ---
    def write_csv_to_stage(data, filename, stage):
        tmp_dir = tempfile.mkdtemp()
        filepath = os.path.join(tmp_dir, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        session.file.put(filepath, f'@{stage}/{RUN_ID}/', auto_compress=False, overwrite=True)

    datasets = [(sanctions,'SANCTIONS_WATCHLIST.csv'),(peps,'PEP_LIST.csv'),
        (customers,'CUSTOMER_MASTER.csv'),(accounts,'ACCOUNT_MASTER.csv'),
        (transactions,'TRANSACTION_FACT.csv'),(loans,'LOAN_MASTER.csv'),
        (loan_performance,'LOAN_PERFORMANCE.csv'),(deposit_balances,'DEPOSIT_BALANCES.csv')]
    for data, filename in datasets:
        write_csv_to_stage(data, filename, DATA_STAGE)

    # --- Generate & upload policy PDFs ---
    from fpdf import FPDF
    POLICIES = {
        'AML_Policy.pdf': ('Anti-Money Laundering Policy', 'INTERNAL', [
            ('Purpose',
             'This policy establishes the minimum standards the institution applies to prevent, detect, '
             'and report money laundering (ML) and terrorist financing (TF). It applies to all business '
             'lines, all customer types, and all transaction channels including branch, online, mobile, '
             'ATM, SWIFT, and correspondent banking. Compliance is mandatory for all staff. The Money '
             'Laundering Reporting Officer (MLRO) owns this policy and reviews it at least annually.'),
            ('Customer Due Diligence',
             'Standard Due Diligence (SDD) requires verified identity, address, date of birth, source of '
             'funds, and expected account purpose before an account is activated. Enhanced Due Diligence '
             '(EDD) is mandatory where the customer is a Politically Exposed Person (PEP), resides in or '
             'transacts with a high-risk jurisdiction, is assigned a HIGH internal risk rating, or declares '
             'source of funds as UNKNOWN. EDD requires senior compliance sign-off, documented source of '
             'wealth, and adverse media screening. A customer whose KYC_STATUS is PENDING may not transact '
             'above USD 10,000. A customer whose KYC_STATUS is EXPIRED must be restricted to debit-only '
             'activity until review completes.'),
            ('KYC Review Cycle',
             'KYC records are refreshed on a risk-based cycle: HIGH risk every 12 months, MEDIUM risk every '
             '24 months, LOW risk every 36 months. A review is triggered out of cycle by a sanctions or PEP '
             'match, a Suspicious Activity Report (SAR) filing, a change of beneficial ownership, or any '
             'transaction exceeding five times the customer declared annual income.'),
            ('Sanctions and PEP Screening',
             'All customers and all transaction counterparties are screened against OFAC SDN, UN '
             'Consolidated, EU Consolidated, and UK HMT lists. The fuzzy name match threshold is 85 percent; '
             'any match at or above threshold blocks the transaction and creates an alert in ALERT_GENERATED '
             'status. Matches are adjudicated within one business day. A confirmed true match requires the '
             'account to be frozen immediately and reported to the relevant authority within 24 hours. '
             'Screening lists are refreshed daily. PEP matches do not automatically block but always '
             'escalate to EDD.'),
            ('Reporting Obligations',
             'A Currency Transaction Report (CTR) is filed for any cash transaction at or above USD 10,000, '
             'or for structured cash activity aggregating to that amount. A Suspicious Activity Report (SAR) '
             'is filed within 30 calendar days of the date suspicion is established, and within 15 days '
             'where terrorist financing is suspected. SAR filings are confidential; tipping off a customer '
             'is a criminal offence. All alerts, dispositions, and filings are retained for a minimum of '
             'five years and must be reproducible for audit.'),
            ('Violations',
             'The following constitute policy violations requiring escalation to the MLRO: transacting a '
             'customer with EXPIRED KYC status; clearing a screening match at or above the 85 percent '
             'threshold without documented adjudication; failure to file a CTR for a reportable cash '
             'transaction; failure to file a SAR within the required window; onboarding a PEP without '
             'EDD sign-off.'),
        ]),
        'Transaction_Monitoring_Policy.pdf': ('Transaction Monitoring Policy', 'INTERNAL', [
            ('Purpose',
             'This policy defines the automated scenarios, thresholds, and investigation workflow used to '
             'monitor customer transactions for money laundering, fraud, and sanctions risk. Every '
             'transaction is scored from 0 (low risk) to 100 (high risk). Scores at or above 70 generate '
             'an alert. Scores at or above 90 escalate directly to a senior investigator.'),
            ('Structuring',
             'Structuring is the deliberate splitting of cash activity to evade the USD 10,000 reporting '
             'threshold. The detection scenario fires when three or more cash transactions between USD '
             '9,000 and USD 9,999 occur on the same customer within a rolling seven day window, or when '
             'aggregate cash activity exceeds USD 10,000 across multiple accounts under common control '
             'within the same period. Structuring alerts carry a minimum risk score of 75 and require a '
             'CTR review in every case.'),
            ('Rapid Movement of Funds',
             'Rapid movement fires when funds are credited and substantially withdrawn within 48 hours, '
             'where the outbound amount is at least 80 percent of the inbound amount and the inbound amount '
             'exceeds USD 50,000. This pattern indicates pass-through or mule account behaviour. Accounts '
             'with two or more rapid movement alerts in 30 days are referred for closure review.'),
            ('Round-Tripping',
             'Round-tripping fires when funds traverse three or more accounts and return to the originating '
             'account, or to an account under common beneficial ownership, within a 30 day window. Where '
             'any leg of the cycle crosses a high-risk jurisdiction, the risk score is raised by 15 points.'),
            ('High-Risk Jurisdiction Exposure',
             'Any transaction where the originator or beneficiary country appears on the institution high-risk '
             'jurisdiction list (currently IR, KP, RU, NG, AE) generates an alert regardless of amount. '
             'Cross-border wires to these jurisdictions above USD 15,000 require pre-approval from compliance '
             'before release.'),
            ('Investigation Workflow',
             'Alerts move through the states ALERT_GENERATED, UNDER_REVIEW, ESCALATED, and then either '
             'CLEARED or SAR_FILED. An analyst must action an alert within three business days of generation. '
             'Every disposition requires a written rationale and the underlying evidence set. Clearing an '
             'alert with a risk score at or above 90 requires two-person approval.'),
            ('Violations',
             'Violations include: an alert left unactioned beyond three business days; an alert cleared '
             'without a documented rationale; a single-person clearance of a score 90 or above alert; '
             'release of a restricted-jurisdiction wire without compliance pre-approval; disabling or '
             'tuning a detection scenario without model governance approval.'),
        ]),
        'Fraud_Risk_Management_Policy.pdf': ('Fraud Risk Management Policy', 'CONFIDENTIAL', [
            ('Purpose',
             'This policy governs the identification, prevention, detection, and response to internal and '
             'external fraud across all products and channels. It covers payment fraud, account takeover, '
             'application fraud, card fraud, and insider fraud. The Head of Financial Crime owns this policy.'),
            ('Detection Scenarios',
             'Card-present fraud fires when the same card is used in two or more countries within four hours. '
             'Account takeover (ATO) fires when a new device or IP registration is followed by a wire '
             'transfer or beneficiary change within one hour. Application fraud fires on duplicate identity '
             'attributes across distinct applications. Insider fraud fires on staff access to customer '
             'records without an associated service request. Velocity rules trigger on more than five '
             'card-not-present attempts in ten minutes.'),
            ('Triage and Response',
             'Alerts are triaged into four severities. CRITICAL: block the transaction, freeze the channel, '
             'and contact the customer immediately. HIGH: apply a 15 minute hold pending analyst review. '
             'MEDIUM: allow the transaction and review within one business day. LOW: log for trend analysis. '
             'Provisional credit is issued to the customer within ten business days for disputed unauthorised '
             'transactions, pending investigation outcome.'),
            ('Customer Remediation',
             'Confirmed unauthorised transactions are reimbursed in full where the customer is not grossly '
             'negligent. Compromised credentials require forced reset and re-authentication across all '
             'channels. Compromised cards are blocked and reissued within two business days. Every confirmed '
             'fraud case is assessed for a parallel AML reporting obligation.'),
            ('Violations',
             'Violations include: failure to block a CRITICAL severity alert; releasing a HIGH severity '
             'transaction before the 15 minute hold elapses; failure to issue provisional credit within ten '
             'business days; accessing customer records without a service request; failure to assess a '
             'confirmed fraud case for SAR reporting.'),
        ]),
        'Basel_Credit_Risk_Policy.pdf': ('Basel Credit Risk Policy', 'INTERNAL', [
            ('Purpose',
             'This policy sets the framework for measuring and managing credit risk and for calculating '
             'regulatory capital under the Basel accords. It governs rating assignment, risk parameter '
             'estimation, risk-weighted asset (RWA) computation, and IFRS 9 impairment staging across all '
             'lending portfolios. The Chief Risk Officer owns this policy.'),
            ('Risk Parameters',
             'Probability of Default (PD) is the one year likelihood of default expressed as a decimal. Loss '
             'Given Default (LGD) is the expected loss severity as a proportion of exposure. Exposure At '
             'Default (EAD) is the expected outstanding amount at the point of default. Expected Loss is '
             'calculated as EL = PD x LGD x EAD. Default is defined as 90 or more days past due, or the '
             'occurrence of an unlikeliness-to-pay event such as restructuring under distress or bankruptcy.'),
            ('RWA and Capital Calculation',
             'Under the Standardised Approach (SA), RWA is exposure multiplied by the prescribed supervisory '
             'risk weight. Under the Foundation and Advanced IRB approaches (FIRB, AIRB), the capital '
             'requirement K is derived from internal PD and LGD estimates and RWA is computed as K x 12.5 x '
             'EAD. The minimum capital requirement is 8 percent of RWA. Exposures rated CCC or below attract '
             'a risk weight of 150 percent or higher.'),
            ('IFRS 9 Impairment Staging',
             'Stage 1 covers performing exposures with no significant increase in credit risk; a 12 month '
             'expected credit loss (ECL) is recognised. Stage 2 covers exposures with a significant increase '
             'in credit risk, presumed at 30 or more days past due; a lifetime ECL is recognised. Stage 3 '
             'covers credit-impaired exposures at 90 or more days past due; a lifetime ECL is recognised on '
             'net carrying amount. Migration between stages is reassessed at every reporting date. Cure back '
             'to a lower stage requires three consecutive months of contractual performance.'),
            ('Collateral and Loan-to-Value',
             'Collateral is revalued at least annually, and semi-annually where the loan-to-value (LTV) ratio '
             'exceeds 80 percent. An LTV above 100 percent means the exposure is under-collateralised and must '
             'be reported to the credit committee. Unsecured exposures to obligors rated below BB require '
             'credit committee approval irrespective of amount.'),
            ('Violations',
             'The following breach this policy and require credit committee escalation: an LTV ratio above 100 '
             'percent without a remediation plan; a PD above 10 percent without watchlist classification; '
             'single-obligor exposure exceeding 25 percent of eligible capital; failure to migrate an exposure '
             'to Stage 3 at 90 days past due; collateral not revalued within the required cycle.'),
        ]),
        'Basel_Liquidity_Risk_Policy.pdf': ('Basel Liquidity Risk Policy', 'INTERNAL', [
            ('Purpose',
             'This policy establishes the framework for measuring, monitoring, and managing liquidity risk, '
             'including the Basel III Liquidity Coverage Ratio (LCR) and Net Stable Funding Ratio (NSFR). '
             'It governs the composition of the liquid asset buffer, deposit behavioural assumptions, and '
             'contingency funding. The Treasurer owns this policy and reports to the Asset and Liability '
             'Committee (ALCO).'),
            ('Liquidity Coverage Ratio',
             'LCR is High Quality Liquid Assets (HQLA) divided by total net cash outflows over a 30 calendar '
             'day stress horizon, and must be maintained at 100 percent or above at all times. Level 1 HQLA '
             '(cash, central bank reserves, qualifying sovereign debt) is uncapped and carries no haircut. '
             'Level 2A assets carry a 15 percent haircut. Level 2B assets carry a 25 to 50 percent haircut '
             'and together Level 2 may not exceed 40 percent of the buffer.'),
            ('Deposit Run-Off Assumptions',
             'Run-off factors are applied by deposit category. Stable retail deposits that are insured and '
             'held in an established relationship attract a 5 percent run-off. Less stable retail deposits '
             'attract 10 percent. Unsecured wholesale funding from non-financial corporates attracts 40 '
             'percent. Unsecured wholesale funding from financial institutions attracts 100 percent. The '
             'uninsured portion of any deposit is always treated as less stable.'),
            ('Net Stable Funding Ratio',
             'NSFR is Available Stable Funding divided by Required Stable Funding over a one year horizon and '
             'must be maintained at 100 percent or above. Term deposits with residual maturity of one year or '
             'more count as fully stable funding. Demand and savings deposits receive partial recognition '
             'based on their assessed behavioural stability.'),
            ('Concentration and Early Warning',
             'A single depositor representing more than 5 percent of total funding, or any deposit above USD '
             '10,000,000, is flagged for concentration risk and reported to ALCO monthly. Early warning '
             'indicators include a declining LCR trend over five consecutive business days, a rise in the '
             'uninsured deposit ratio, and widening funding spreads. Breach of any indicator activates the '
             'Contingency Funding Plan.'),
            ('Violations',
             'Violations include: LCR below 100 percent on three or more consecutive days; NSFR below 100 '
             'percent at any reporting date; Level 2 assets exceeding 40 percent of the HQLA buffer; a '
             'concentration flag not reported to ALCO within the monthly cycle; failure to activate the '
             'Contingency Funding Plan following an early warning breach.'),
        ]),
        'Capital_Adequacy_Policy.pdf': ('Capital Adequacy Policy', 'INTERNAL', [
            ('Purpose',
             'This policy defines the minimum regulatory and internal capital the institution holds against '
             'its risk exposures, the composition of eligible capital, and the actions required when capital '
             'falls toward or below threshold. It covers credit, market, and operational risk capital. The '
             'Chief Financial Officer owns this policy jointly with the Chief Risk Officer.'),
            ('Minimum Capital Requirements',
             'Common Equity Tier 1 (CET1) must be at least 4.5 percent of RWA. Total Tier 1 capital must be at '
             'least 6 percent of RWA. Total capital (Tier 1 plus Tier 2) must be at least 8 percent of RWA. '
             'These are regulatory floors; the board sets internal management buffers above each floor and '
             'the institution operates to the internal buffer, not the floor.'),
            ('Capital Buffers',
             'A Capital Conservation Buffer of 2.5 percent of RWA, met with CET1, sits above the minimums. A '
             'Countercyclical Capital Buffer of 0 to 2.5 percent may be imposed by the regulator depending on '
             'credit cycle conditions. Where the institution is designated systemically important, an '
             'additional loss absorbency surcharge applies. The combined buffer requirement determines the '
             'maximum distributable amount.'),
            ('Leverage Ratio',
             'The Tier 1 leverage ratio is Tier 1 capital divided by total exposure including off-balance '
             'sheet commitments, and must be maintained at 3 percent or above. The leverage ratio is a '
             'non-risk-based backstop and applies irrespective of RWA outcomes.'),
            ('Stress Testing and ICAAP',
             'Capital adequacy is assessed under baseline, adverse, and severely adverse macroeconomic '
             'scenarios at least annually as part of the Internal Capital Adequacy Assessment Process '
             '(ICAAP). The institution must remain above all regulatory minimums throughout the stress '
             'horizon in every scenario. ICAAP results are approved by the board and submitted to the '
             'regulator.'),
            ('Violations',
             'Breach of the combined buffer requirement triggers automatic restrictions on dividends, share '
             'buybacks, and discretionary staff bonuses, scaled to the severity of the shortfall. Breach of '
             'any regulatory minimum requires immediate notification to the regulator, submission of a '
             'capital restoration plan within 30 days, and board-level remediation oversight. Falling below '
             'the 3 percent leverage ratio is a reportable breach even where risk-based ratios are met.'),
        ]),
    }
    for filename, (title, classification, sections) in POLICIES.items():
        pdf = FPDF(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_font('Helvetica','B',16); pdf.multi_cell(0,9,title,new_x='LMARGIN',new_y='NEXT'); pdf.ln(1)
        pdf.set_font('Helvetica','I',9)
        pdf.cell(0,5,f'Classification: {classification}',new_x='LMARGIN',new_y='NEXT')
        pdf.cell(0,5,f'Generated: {RUN_ID}',new_x='LMARGIN',new_y='NEXT'); pdf.ln(6)
        for st, sb in sections:
            pdf.set_font('Helvetica','B',12); pdf.multi_cell(0,7,st,new_x='LMARGIN',new_y='NEXT')
            pdf.set_font('Helvetica','',10); pdf.multi_cell(0,5,sb,new_x='LMARGIN',new_y='NEXT'); pdf.ln(3)
        tmp_dir = tempfile.mkdtemp(); filepath = os.path.join(tmp_dir, filename); pdf.output(filepath)
        session.file.put(filepath, f'@{POLICIES_STAGE}/{RUN_ID}/', auto_compress=False, overwrite=True)

    violation_count = sum(1 for t in transactions if t['AML_FLAG'] == 'Y')
    return (f'Run ID: {RUN_ID} | '
            f'Data: @{DATA_STAGE}/{RUN_ID}/ (8 CSVs) | '
            f'Policies: @{POLICIES_STAGE}/{RUN_ID}/ (6 PDFs) | '
            f'Txns: 1000 (violations: {violation_count}) | '
            f'Basel: {sum(1 for l in loans if l["BASEL_VIOLATION_FLAG"]=="Y")} loans | '
            f'Liquidity: {sum(1 for d in deposit_balances if d["LIQUIDITY_VIOLATION_FLAG"]=="Y")} deposits')
$$;

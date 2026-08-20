-- Stored Procedure: GENERATE_RISK_DATA
-- Generates synthetic banking risk data and loads to stages
-- Usage: CALL RISK_DB.RAW.GENERATE_RISK_DATA();
--
-- Outputs:
--   8 CSV files -> @RISK_DB.RAW.RISK_FRAUD_DATA_STAGE/<timestamp>/
--   6 PDF files -> @RISK_DB.RAW.POLICIES_STAGE/<timestamp>/
--
-- Each run creates a new timestamp folder for versioning.

CREATE OR REPLACE PROCEDURE RISK_DB.RAW.GENERATE_RISK_DATA()
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
        'AML_Policy.pdf': ('Anti-Money Laundering Policy', [('Purpose','Prevents ML/TF.'),('Screening','OFAC/UN/EU/UK. Threshold: 85%.')]),
        'Transaction_Monitoring_Policy.pdf': ('Transaction Monitoring Policy', [('Structuring','3+ txns $9k-$9.9k in 7 days.'),('Round-Tripping','Funds cycle 3+ accounts in 30 days.')]),
        'Fraud_Risk_Management_Policy.pdf': ('Fraud Risk Management Policy', [('Detection','Card 2+ countries in 4hrs. ATO: new device+wire in 1hr.'),('Triage','CRITICAL: block. HIGH: 15min hold.')]),
        'Basel_Credit_Risk_Policy.pdf': ('Basel Credit Risk Policy', [('RWA','K*12.5*EAD. EL=PD*LGD*EAD. Capital=RWA*8%.'),('Violations','High LTV, PD>10%, concentration.')]),
        'Basel_Liquidity_Risk_Policy.pdf': ('Basel Liquidity Risk Policy', [('LCR','HQLA/Outflows>=100%.'),('Violations','LCR<100% 3+days, NSFR<100%.')]),
        'Capital_Adequacy_Policy.pdf': ('Capital Adequacy Policy', [('Minimums','CET1:4.5%, T1:6%, Total:8%.'),('Violations','Buffer breach: dividend restriction.')]),
    }
    for filename, (title, sections) in POLICIES.items():
        pdf = FPDF(); pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_font('Helvetica','B',16); pdf.cell(0,10,title,new_x='LMARGIN',new_y='NEXT')
        pdf.set_font('Helvetica','I',9); pdf.cell(0,5,f'Generated: {RUN_ID}',new_x='LMARGIN',new_y='NEXT'); pdf.ln(8)
        for st, sb in sections:
            pdf.set_font('Helvetica','B',12); pdf.cell(0,8,st,new_x='LMARGIN',new_y='NEXT')
            pdf.set_font('Helvetica','',10); pdf.multi_cell(0,5,sb); pdf.ln(4)
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

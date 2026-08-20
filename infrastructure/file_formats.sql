-- CSV file format for loading risk/fraud data from RISK_FRAUD_DATA_STAGE
CREATE FILE FORMAT IF NOT EXISTS RISK_DB.RAW.CSV_FORMAT
    TYPE = 'CSV'
    FIELD_DELIMITER = ','
    RECORD_DELIMITER = '\n'
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    TRIM_SPACE = TRUE
    NULL_IF = ('', 'NULL', 'null')
    COMMENT = 'Standard CSV format for risk data files';

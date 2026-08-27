CREATE OR REPLACE PROCEDURE RISK_DB.CURATED.SP_LOAD_DIM_CUSTOMER()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    -- Expire existing current records where the hash has changed
    UPDATE RISK_DB.CURATED.DIM_CUSTOMER tgt
    SET tgt.EFFECTIVE_TO = CURRENT_TIMESTAMP(),
        tgt.IS_CURRENT = FALSE
    WHERE tgt.IS_CURRENT = TRUE
      AND EXISTS (
          SELECT 1 FROM RISK_DB.CURATED.INT_CUSTOMER src
          WHERE src.CUSTOMER_ID = tgt.CUSTOMER_ID
            AND MD5(COALESCE(src.FIRST_NAME,'') || '|' || COALESCE(src.LAST_NAME,'') || '|' ||
                    COALESCE(src.FULL_NAME,'') || '|' || COALESCE(TO_CHAR(src.DATE_OF_BIRTH),'') || '|' ||
                    COALESCE(src.NATIONALITY,'') || '|' || COALESCE(src.COUNTRY_OF_RESIDENCE,'') || '|' ||
                    COALESCE(src.CUSTOMER_TYPE,'') || '|' || COALESCE(src.INDUSTRY,'') || '|' ||
                    COALESCE(src.RISK_RATING,'') || '|' || COALESCE(src.KYC_STATUS,'') || '|' ||
                    COALESCE(TO_CHAR(src.KYC_LAST_REVIEWED),'') || '|' || COALESCE(src.STATUS,'') || '|' ||
                    COALESCE(TO_CHAR(src.PEP_FLAG),'') || '|' || COALESCE(TO_CHAR(src.SANCTIONS_MATCH_FLAG),'') || '|' ||
                    COALESCE(TO_CHAR(src.ANNUAL_INCOME),'') || '|' || COALESCE(src.SOURCE_OF_FUNDS,'') || '|' ||
                    COALESCE(src.ACCOUNT_PURPOSE,''))
                != tgt.RECORD_HASH
      );

    -- Insert new versions for changed records + brand new records
    INSERT INTO RISK_DB.CURATED.DIM_CUSTOMER (
        CUSTOMER_ID, FIRST_NAME, LAST_NAME, FULL_NAME, DATE_OF_BIRTH,
        NATIONALITY, COUNTRY_OF_RESIDENCE, CUSTOMER_TYPE, INDUSTRY, RISK_RATING,
        KYC_STATUS, KYC_LAST_REVIEWED, ONBOARDING_DATE, PEP_FLAG, SANCTIONS_MATCH_FLAG,
        ANNUAL_INCOME, SOURCE_OF_FUNDS, ACCOUNT_PURPOSE, STATUS,
        IS_HIGH_RISK, AGE_YEARS, DAYS_SINCE_ONBOARDING,
        EFFECTIVE_FROM, EFFECTIVE_TO, IS_CURRENT, RECORD_HASH
    )
    SELECT
        src.CUSTOMER_ID, src.FIRST_NAME, src.LAST_NAME, src.FULL_NAME, src.DATE_OF_BIRTH,
        src.NATIONALITY, src.COUNTRY_OF_RESIDENCE, src.CUSTOMER_TYPE, src.INDUSTRY, src.RISK_RATING,
        src.KYC_STATUS, src.KYC_LAST_REVIEWED, src.ONBOARDING_DATE, src.PEP_FLAG, src.SANCTIONS_MATCH_FLAG,
        src.ANNUAL_INCOME, src.SOURCE_OF_FUNDS, src.ACCOUNT_PURPOSE, src.STATUS,
        src.IS_HIGH_RISK, src.AGE_YEARS, src.DAYS_SINCE_ONBOARDING,
        CURRENT_TIMESTAMP(), '9999-12-31'::TIMESTAMP_NTZ, TRUE,
        MD5(COALESCE(src.FIRST_NAME,'') || '|' || COALESCE(src.LAST_NAME,'') || '|' ||
            COALESCE(src.FULL_NAME,'') || '|' || COALESCE(TO_CHAR(src.DATE_OF_BIRTH),'') || '|' ||
            COALESCE(src.NATIONALITY,'') || '|' || COALESCE(src.COUNTRY_OF_RESIDENCE,'') || '|' ||
            COALESCE(src.CUSTOMER_TYPE,'') || '|' || COALESCE(src.INDUSTRY,'') || '|' ||
            COALESCE(src.RISK_RATING,'') || '|' || COALESCE(src.KYC_STATUS,'') || '|' ||
            COALESCE(TO_CHAR(src.KYC_LAST_REVIEWED),'') || '|' || COALESCE(src.STATUS,'') || '|' ||
            COALESCE(TO_CHAR(src.PEP_FLAG),'') || '|' || COALESCE(TO_CHAR(src.SANCTIONS_MATCH_FLAG),'') || '|' ||
            COALESCE(TO_CHAR(src.ANNUAL_INCOME),'') || '|' || COALESCE(src.SOURCE_OF_FUNDS,'') || '|' ||
            COALESCE(src.ACCOUNT_PURPOSE,''))
    FROM RISK_DB.CURATED.INT_CUSTOMER src
    WHERE NOT EXISTS (
        SELECT 1 FROM RISK_DB.CURATED.DIM_CUSTOMER tgt
        WHERE tgt.CUSTOMER_ID = src.CUSTOMER_ID
          AND tgt.IS_CURRENT = TRUE
          AND tgt.RECORD_HASH = MD5(COALESCE(src.FIRST_NAME,'') || '|' || COALESCE(src.LAST_NAME,'') || '|' ||
              COALESCE(src.FULL_NAME,'') || '|' || COALESCE(TO_CHAR(src.DATE_OF_BIRTH),'') || '|' ||
              COALESCE(src.NATIONALITY,'') || '|' || COALESCE(src.COUNTRY_OF_RESIDENCE,'') || '|' ||
              COALESCE(src.CUSTOMER_TYPE,'') || '|' || COALESCE(src.INDUSTRY,'') || '|' ||
              COALESCE(src.RISK_RATING,'') || '|' || COALESCE(src.KYC_STATUS,'') || '|' ||
              COALESCE(TO_CHAR(src.KYC_LAST_REVIEWED),'') || '|' || COALESCE(src.STATUS,'') || '|' ||
              COALESCE(TO_CHAR(src.PEP_FLAG),'') || '|' || COALESCE(TO_CHAR(src.SANCTIONS_MATCH_FLAG),'') || '|' ||
              COALESCE(TO_CHAR(src.ANNUAL_INCOME),'') || '|' || COALESCE(src.SOURCE_OF_FUNDS,'') || '|' ||
              COALESCE(src.ACCOUNT_PURPOSE,''))
    );

    RETURN 'DIM_CUSTOMER loaded successfully';
END;
$$;

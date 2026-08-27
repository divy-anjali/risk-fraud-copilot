CREATE OR REPLACE PROCEDURE RISK_DB.CURATED.SP_LOAD_DIM_PEP()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    UPDATE RISK_DB.CURATED.DIM_PEP tgt
    SET tgt.EFFECTIVE_TO = CURRENT_TIMESTAMP(),
        tgt.IS_CURRENT = FALSE
    WHERE tgt.IS_CURRENT = TRUE
      AND EXISTS (
          SELECT 1 FROM RISK_DB.CURATED.INT_PEP src
          WHERE src.PEP_ID = tgt.PEP_ID
            AND MD5(COALESCE(src.FULL_NAME,'') || '|' || COALESCE(src.POSITION,'') || '|' ||
                    COALESCE(src.COUNTRY,'') || '|' || COALESCE(src.PEP_TIER,'') || '|' ||
                    COALESCE(src.RELATIONSHIP_TYPE,'') || '|' || COALESCE(src.STATUS,'') || '|' ||
                    COALESCE(src.SOURCE,''))
                != tgt.RECORD_HASH
      );

    INSERT INTO RISK_DB.CURATED.DIM_PEP (
        PEP_ID, FULL_NAME, POSITION, COUNTRY, PEP_TIER, RELATIONSHIP_TYPE,
        DATE_ADDED, STATUS, SOURCE, DAYS_ON_LIST,
        EFFECTIVE_FROM, EFFECTIVE_TO, IS_CURRENT, RECORD_HASH
    )
    SELECT
        src.PEP_ID, src.FULL_NAME, src.POSITION, src.COUNTRY, src.PEP_TIER, src.RELATIONSHIP_TYPE,
        src.DATE_ADDED, src.STATUS, src.SOURCE, src.DAYS_ON_LIST,
        CURRENT_TIMESTAMP(), '9999-12-31'::TIMESTAMP_NTZ, TRUE,
        MD5(COALESCE(src.FULL_NAME,'') || '|' || COALESCE(src.POSITION,'') || '|' ||
            COALESCE(src.COUNTRY,'') || '|' || COALESCE(src.PEP_TIER,'') || '|' ||
            COALESCE(src.RELATIONSHIP_TYPE,'') || '|' || COALESCE(src.STATUS,'') || '|' ||
            COALESCE(src.SOURCE,''))
    FROM RISK_DB.CURATED.INT_PEP src
    WHERE NOT EXISTS (
        SELECT 1 FROM RISK_DB.CURATED.DIM_PEP tgt
        WHERE tgt.PEP_ID = src.PEP_ID
          AND tgt.IS_CURRENT = TRUE
          AND tgt.RECORD_HASH = MD5(COALESCE(src.FULL_NAME,'') || '|' || COALESCE(src.POSITION,'') || '|' ||
              COALESCE(src.COUNTRY,'') || '|' || COALESCE(src.PEP_TIER,'') || '|' ||
              COALESCE(src.RELATIONSHIP_TYPE,'') || '|' || COALESCE(src.STATUS,'') || '|' ||
              COALESCE(src.SOURCE,''))
    );

    RETURN 'DIM_PEP loaded successfully';
END;
$$;

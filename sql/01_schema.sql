-- =====================================================================
-- PhonePe Transaction Insights : PostgreSQL schema
-- 9 tables = {aggregated, map, top} x {transaction, user, merchant}
--
-- NOTE: the brief lists *_insurance tables, but the current PhonePe Pulse
-- repo ships MERCHANT data instead (no insurance folder exists in any
-- commit). The merchant tables below are the direct replacement.
-- =====================================================================

DROP TABLE IF EXISTS aggregated_transaction, aggregated_user, aggregated_merchant,
                     map_transaction, map_user, map_merchant,
                     top_transaction, top_user, top_merchant CASCADE;

-- ---------------------------- AGGREGATED (state level) ----------------
CREATE TABLE aggregated_transaction (
    state             VARCHAR(60) NOT NULL,
    year              SMALLINT    NOT NULL CHECK (year BETWEEN 2018 AND 2100),
    quarter           SMALLINT    NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    payment_category  VARCHAR(30) NOT NULL,          -- P2P / Retail / Utility
    txn_count         BIGINT      NOT NULL CHECK (txn_count >= 0),
    PRIMARY KEY (state, year, quarter, payment_category)
);

CREATE TABLE aggregated_user (
    state             VARCHAR(60) NOT NULL,
    year              SMALLINT    NOT NULL,
    quarter           SMALLINT    NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    registered_users  BIGINT      NOT NULL CHECK (registered_users >= 0),
    PRIMARY KEY (state, year, quarter)
);

CREATE TABLE aggregated_merchant (
    state                 VARCHAR(60) NOT NULL,
    year                  SMALLINT    NOT NULL,
    quarter               SMALLINT    NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    registered_merchants  BIGINT      NOT NULL CHECK (registered_merchants >= 0),
    PRIMARY KEY (state, year, quarter)
);

-- ---------------------------- MAP (district level) --------------------
CREATE TABLE map_transaction (
    state       VARCHAR(60)   NOT NULL,
    year        SMALLINT      NOT NULL,
    quarter     SMALLINT      NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    district    VARCHAR(100)  NOT NULL,
    txn_count   BIGINT        NOT NULL CHECK (txn_count >= 0),
    txn_amount  NUMERIC(20,2) NOT NULL CHECK (txn_amount >= 0),   -- INR
    PRIMARY KEY (state, district, year, quarter)
);

CREATE TABLE map_user (
    state             VARCHAR(60)  NOT NULL,
    year              SMALLINT     NOT NULL,
    quarter           SMALLINT     NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    district          VARCHAR(100) NOT NULL,
    registered_users  BIGINT       NOT NULL CHECK (registered_users >= 0),
    PRIMARY KEY (state, district, year, quarter)
);

CREATE TABLE map_merchant (
    state                 VARCHAR(60)  NOT NULL,
    year                  SMALLINT     NOT NULL,
    quarter               SMALLINT     NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    district              VARCHAR(100) NOT NULL,
    registered_merchants  BIGINT       NOT NULL CHECK (registered_merchants >= 0),
    PRIMARY KEY (state, district, year, quarter)
);

-- ---------------------------- TOP (ranked leaderboards (up to 10 for txn/user, longer for merchant)) ---------------
-- state = 'All India' rows rank states; state = <name> rows rank districts.
CREATE TABLE top_transaction (
    state         VARCHAR(60)  NOT NULL,
    year          SMALLINT     NOT NULL,
    quarter       SMALLINT     NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    entity_level  VARCHAR(10)  NOT NULL CHECK (entity_level IN ('state','district')),
    rank          SMALLINT     NOT NULL CHECK (rank >= 1),
    entity_name   VARCHAR(100) NOT NULL,
    txn_count     BIGINT       NOT NULL,
    PRIMARY KEY (state, year, quarter, entity_level, rank)
);

CREATE TABLE top_user (
    state             VARCHAR(60)  NOT NULL,
    year              SMALLINT     NOT NULL,
    quarter           SMALLINT     NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    entity_level      VARCHAR(10)  NOT NULL CHECK (entity_level IN ('state','district')),
    rank              SMALLINT     NOT NULL CHECK (rank >= 1),
    entity_name       VARCHAR(100) NOT NULL,
    registered_users  BIGINT       NOT NULL,
    PRIMARY KEY (state, year, quarter, entity_level, rank)
);

CREATE TABLE top_merchant (
    state                 VARCHAR(60)  NOT NULL,
    year                  SMALLINT     NOT NULL,
    quarter               SMALLINT     NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    entity_level          VARCHAR(10)  NOT NULL CHECK (entity_level IN ('state','district')),
    rank                  SMALLINT     NOT NULL CHECK (rank >= 1),
    entity_name           VARCHAR(100) NOT NULL,
    registered_merchants  BIGINT       NOT NULL,
    PRIMARY KEY (state, year, quarter, entity_level, rank)
);

-- ---------------------------- INDEXES ---------------------------------
-- PKs already cover (state, year, quarter) lookups. These speed up the
-- time-series and "by period" filters the dashboard uses most.
CREATE INDEX idx_aggtxn_period  ON aggregated_transaction (year, quarter);
CREATE INDEX idx_aggtxn_cat     ON aggregated_transaction (payment_category);
CREATE INDEX idx_maptxn_period  ON map_transaction (year, quarter);
CREATE INDEX idx_mapuser_period ON map_user (year, quarter);
CREATE INDEX idx_mapmerch_period ON map_merchant (year, quarter);

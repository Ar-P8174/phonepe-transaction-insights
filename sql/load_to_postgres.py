"""
Step 2 - Load processed CSVs into PostgreSQL.

1. Runs sql/01_schema.sql (drops + recreates the 9 tables)
2. Bulk-loads every CSV in data/processed/ using COPY (fast)
3. Prints row counts so you can verify the load

Connection settings come from environment variables (never hard-code passwords):
    PGHOST (localhost)  PGPORT (5432)  PGDATABASE (phonepe)
    PGUSER (postgres)   PGPASSWORD

Usage:
    python sql/load_to_postgres.py
    python sql/load_to_postgres.py --dsn "postgresql://user:pw@host:5432/phonepe"
"""
import argparse
import logging
import os
from pathlib import Path

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("load_to_postgres")

ROOT = Path(__file__).resolve().parent.parent
LOAD_ORDER = [
    "aggregated_transaction", "aggregated_user", "aggregated_merchant",
    "map_transaction", "map_user", "map_merchant",
    "top_transaction", "top_user", "top_merchant",
]


def connect(dsn: str | None):
    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "phonepe"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=None)
    ap.add_argument("--csv-dir", default=str(ROOT / "data" / "processed"))
    args = ap.parse_args()
    csv_dir = Path(args.csv_dir)

    missing = [t for t in LOAD_ORDER if not (csv_dir / f"{t}.csv").exists()]
    if missing:
        raise SystemExit(f"Missing CSVs {missing}. Run data_extraction/extract_pulse.py first.")

    conn = connect(args.dsn)
    try:
        with conn, conn.cursor() as cur:          # one transaction: all-or-nothing
            cur.execute((ROOT / "sql" / "01_schema.sql").read_text())
            log.info("Schema created")
            for table in LOAD_ORDER:
                with open(csv_dir / f"{table}.csv", encoding="utf-8") as fh:
                    header = fh.readline().strip()   # column names from CSV header
                    cur.copy_expert(
                        f"COPY {table} ({header}) FROM STDIN WITH (FORMAT csv)", fh
                    )
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                log.info("%-24s %8d rows loaded", table, cur.fetchone()[0])
        log.info("Load committed successfully")
    except Exception:
        log.exception("Load failed - transaction rolled back")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

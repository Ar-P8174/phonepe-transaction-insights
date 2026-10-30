"""
Step 3 - Execute every business query, time it, and export results.

Outputs
  web/data/<query_name>.json     -> consumed by the Vercel dashboard
  docs/query_performance.csv     -> execution time + row count per query

Usage:
    python sql/run_queries.py                 # uses PG* env vars
    python sql/run_queries.py --dsn "postgresql://user:pw@host:5432/phonepe"
"""
import argparse
import csv
import decimal
import json
import logging
import re
import time
from pathlib import Path

import psycopg2

from load_to_postgres import connect  # reuse the same connection logic

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("run_queries")

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.M)


def parse_queries(sql_text: str) -> dict[str, str]:
    """Split the .sql file into {name: sql} using the '-- name:' markers."""
    marks = list(NAME_RE.finditer(sql_text))
    out = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(sql_text)
        out[m.group(1)] = sql_text[m.end():end].strip().rstrip(";")
    return out


def jsonable(v):
    """psycopg2 returns Decimal for NUMERIC; JSON needs plain numbers."""
    if isinstance(v, decimal.Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default=None)
    args = ap.parse_args()

    queries = parse_queries((ROOT / "sql" / "02_business_queries.sql").read_text(encoding="utf-8"))
    out_dir = ROOT / "web" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / "docs").mkdir(exist_ok=True)

    conn = connect(args.dsn)
    perf = []
    try:
        with conn.cursor() as cur:
            for name, sql in queries.items():
                t0 = time.perf_counter()
                try:
                    cur.execute(sql)
                    rows = cur.fetchall()
                except psycopg2.Error:
                    conn.rollback()
                    log.exception("Query %s failed", name)
                    raise
                ms = (time.perf_counter() - t0) * 1000
                cols = [d.name for d in cur.description]
                records = [{c: jsonable(v) for c, v in zip(cols, r)} for r in rows]
                (out_dir / f"{name}.json").write_text(json.dumps(records, separators=(",", ":")), encoding="utf-8")
                perf.append((name, len(records), round(ms, 1)))
                log.info("%-36s %5d rows  %7.1f ms", name, len(records), ms)
    finally:
        conn.close()

    with open(ROOT / "docs" / "query_performance.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["query", "rows", "exec_ms"])
        w.writerows(perf)


if __name__ == "__main__":
    main()

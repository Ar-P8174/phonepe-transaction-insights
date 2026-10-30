"""
Step 1 - ETL (Extract + Transform): PhonePe Pulse JSON  ->  clean CSVs.

Walks the cloned PhonePe Pulse repo (github.com/PhonePe/pulse) and writes one
tidy CSV per target table into data/processed/.

Usage:
    git clone https://github.com/PhonePe/pulse.git
    python extract_pulse.py --pulse-dir ./pulse/data --out-dir ./data/processed

Design notes
------------
* State-level files feed the aggregated_/map_ tables. Country-level files are
  NOT loaded into them (that would double count when summing); they are used
  only for a reconciliation check at the end and for the top_ tables.
* Names are normalised: 'andhra-pradesh' -> 'Andhra Pradesh',
  'alluri sitharama raju district' -> 'Alluri Sitharama Raju'.
"""
import argparse
import json
import logging
import re
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("extract_pulse")

PERIOD_RE = re.compile(r"(?P<year>\d{4})[\\/](?P<q>[1-4])\.json$")


# ----------------------------------------------------------------- helpers
def clean_state(slug: str) -> str:
    """'andaman-&-nicobar-islands' -> 'Andaman & Nicobar Islands'."""
    return slug.replace("-", " ").title()


def clean_district(name: str) -> str:
    """'ananthapuramu district' -> 'Ananthapuramu'."""
    return re.sub(r"\s+district$", "", name.strip(), flags=re.I).title()


def read_json(path: Path) -> dict | None:
    """Load a Pulse JSON file; return its 'data' block or None if unusable."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload["data"] if payload.get("success") else None
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        log.warning("Skipping %s (%s)", path, exc)
        return None


def period_of(path: Path) -> tuple[int, int]:
    m = PERIOD_RE.search(str(path))
    return int(m["year"]), int(m["q"])


def state_files(root: Path):
    """Yield (state_name, year, quarter, path) for every state-level file."""
    for f in sorted(root.glob("state/*/*/*.json")):
        year, q = period_of(f)
        yield clean_state(f.parents[1].name), year, q, f


def country_files(root: Path):
    for f in sorted(root.glob("*/*.json")):
        year, q = period_of(f)
        yield year, q, f


# --------------------------------------------------------------- extractors
def aggregated_transaction(base: Path) -> pd.DataFrame:
    rows = []
    for state, y, q, f in state_files(base / "aggregated/transaction/country/india"):
        data = read_json(f)
        for cat in (data or {}).get("transactionData", []):
            for inst in cat["paymentInstruments"]:
                rows.append((state, y, q, cat["name"], inst["count"]))
    return pd.DataFrame(rows, columns=["state", "year", "quarter", "payment_category", "txn_count"])


def aggregated_registered(base: Path, kind: str, col: str) -> pd.DataFrame:
    rows = []
    for state, y, q, f in state_files(base / f"aggregated/{kind}/country/india"):
        data = read_json(f)
        if data:
            rows.append((state, y, q, data["aggregated"]["registeredCount"]))
    return pd.DataFrame(rows, columns=["state", "year", "quarter", col])


def map_transaction(base: Path) -> pd.DataFrame:
    rows = []
    for state, y, q, f in state_files(base / "map/transaction/hover/country/india"):
        data = read_json(f)
        for d in (data or {}).get("hoverDataList", []):
            m = d["metric"][0]
            rows.append((state, y, q, clean_district(d["name"]), m["count"], m["amount"]))
    return pd.DataFrame(rows, columns=["state", "year", "quarter", "district", "txn_count", "txn_amount"])


def map_registered(base: Path, kind: str, col: str) -> pd.DataFrame:
    rows = []
    for state, y, q, f in state_files(base / f"map/{kind}/hover/country/india"):
        data = read_json(f)
        for name, v in (data or {}).get("hoverData", {}).items():
            rows.append((state, y, q, clean_district(name), v["registeredCount"]))
    return pd.DataFrame(rows, columns=["state", "year", "quarter", "district", col])


def top_table(base: Path, kind: str, col: str) -> pd.DataFrame:
    """Top-10 states (country files) and top-10 districts (state files)."""
    root = base / f"top/{kind}/country/india"

    def parse(entities, level, state, y, q):
        out = []
        for rank, e in enumerate(entities or [], start=1):
            name = e.get("entityName") or e.get("name")
            value = e["metric"]["count"] if "metric" in e else e["registeredCount"]
            clean = clean_state(name.replace(" ", "-")) if level == "state" else clean_district(name)
            out.append((state, y, q, level, rank, clean, value))
        return out

    rows = []
    for y, q, f in country_files(root):
        data = read_json(f)
        rows += parse((data or {}).get("states"), "state", "All India", y, q)
    for state, y, q, f in state_files(root):
        data = read_json(f)
        rows += parse((data or {}).get("districts"), "district", state, y, q)
    return pd.DataFrame(rows, columns=["state", "year", "quarter", "entity_level", "rank", "entity_name", col])


# ------------------------------------------------------------------- checks
def reconcile(base: Path, agg_txn: pd.DataFrame) -> None:
    """Sanity check: sum of states vs. the country-level file for one quarter."""
    f = base / "aggregated/transaction/country/india/2024/1.json"
    country = sum(i["count"] for c in read_json(f)["transactionData"] for i in c["paymentInstruments"])
    states = agg_txn.query("year == 2024 and quarter == 1")["txn_count"].sum()
    diff = abs(country - states) / country * 100
    log.info("Reconciliation 2024-Q1 | country=%s states=%s diff=%.3f%%", f"{country:,}", f"{states:,}", diff)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pulse-dir", default="./pulse/data")
    ap.add_argument("--out-dir", default="./data/processed")
    args = ap.parse_args()
    base, out = Path(args.pulse_dir), Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    agg_txn = aggregated_transaction(base)
    tables = {
        "aggregated_transaction": agg_txn,
        "aggregated_user": aggregated_registered(base, "user", "registered_users"),
        "aggregated_merchant": aggregated_registered(base, "merchant", "registered_merchants"),
        "map_transaction": map_transaction(base),
        "map_user": map_registered(base, "user", "registered_users"),
        "map_merchant": map_registered(base, "merchant", "registered_merchants"),
        "top_transaction": top_table(base, "transaction", "txn_count"),
        "top_user": top_table(base, "user", "registered_users"),
        "top_merchant": top_table(base, "merchant", "registered_merchants"),
    }
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
        log.info("%-24s %8d rows -> %s.csv", name, len(df), name)
    reconcile(base, agg_txn)


if __name__ == "__main__":
    main()

# PhonePe Transaction Insights

End-to-end analysis of the open [PhonePe Pulse](https://github.com/PhonePe/pulse) data: JSON extraction, PostgreSQL warehouse, 15 business SQL queries, a 21-chart EDA notebook, a Streamlit dashboard and a static web dashboard that deploys on Vercel.

Coverage: 36 states/UTs, 783 districts, Q1 2018 to Q2 2026.

## Project layout

```
data_extraction/extract_pulse.py   JSON -> 9 clean CSVs (with reconciliation check)
data/processed/                    the 9 CSVs (committed so everything runs without re-extracting)
sql/01_schema.sql                  PostgreSQL schema (keys, constraints, indexes)
sql/load_to_postgres.py            bulk loader (COPY, single transaction)
sql/02_business_queries.sql        15 business queries + 2 dashboard feeds
sql/run_queries.py                 runs + times every query, exports JSON to web/data/
notebook/PhonePe_EDA_Submission.ipynb   EDA (21 charts, template format, executed)
app/app.py                         Streamlit dashboard
web/                               static dashboard (deployed to Vercel)
docs/                              Insights PDF/Markdown, query timings
geo/india_states.geojson           simplified state boundaries
```

## Quick start

```bash
pip install -r requirements.txt

# 1. (optional) re-extract from source; CSVs are already included
git clone https://github.com/PhonePe/pulse.git
python data_extraction/extract_pulse.py --pulse-dir ./pulse/data --out-dir ./data/processed

# 2. PostgreSQL
createdb phonepe
export PGUSER=postgres PGPASSWORD=yourpassword      # PGHOST/PGPORT/PGDATABASE optional
python sql/load_to_postgres.py                      # creates 9 tables, loads ~114k rows
python sql/run_queries.py                           # runs queries, refreshes web/data/*.json

# 3. Notebook and dashboards (CSV fallback means no database is required)
jupyter notebook notebook/PhonePe_EDA_Submission.ipynb
streamlit run app/app.py
python -m http.server -d web 8000                   # static dashboard at http://localhost:8000
```

Set `DATABASE_URL=postgresql+psycopg2://user:pw@host:5432/phonepe` to make the notebook and Streamlit app read from PostgreSQL instead of the CSVs.

## Deploy the web dashboard on Vercel

Vercel hosts static sites and serverless functions; it cannot run Streamlit. The `web/` folder is a static dashboard that reads precomputed JSON, so it deploys directly.

1. Push this repo to GitHub.
2. On vercel.com choose **Add New > Project** and import the repo.
3. Leave Framework as **Other**. No build command is needed; `vercel.json` already sets the output directory to `web`.
4. Click **Deploy**.

Or from the command line: `npm i -g vercel && vercel --prod`.

To refresh the dashboard after new Pulse data: re-run steps 1 and 2 above, then commit `web/data/` and push; Vercel redeploys automatically.

## Deploy the Streamlit app (free)

Push to GitHub, then on [share.streamlit.io](https://share.streamlit.io) create an app pointing at `app/app.py`. It uses the committed CSVs, so no database or secrets are needed.

## Data notes (differences from the project brief)

- No `insurance` data exists in PhonePe Pulse (checked across the full git history). Merchant tables replace it.
- Transaction amounts exist only at district level (`map_transaction`); aggregated tables hold counts only.
- No pin-code level data, and no device-brand or app-open fields. Leaderboards stop at district level.
- District choropleth maps are not included: the public boundary files predate India's recent district reorganisations, so about 15% of district names would not match and leave misleading gaps. Districts are shown with bar charts and treemaps (100% coverage); the map is state level.
- The anomaly query flags unusual ticket sizes for review. It is a screen, not evidence of fraud.

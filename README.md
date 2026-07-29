# Outbreak EWS — Flask app

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # then edit SECRET_KEY etc.
python run.py
```

Visit http://127.0.0.1:5000, register an account, then go to **Pipeline**
and run detection against one of the demo countries (data/*.csv). The
demo CSVs have a spike injected in the last two weeks so a real run
produces alerts you can show on the Dashboard, Surveillance, and Alerts
log pages.

## Wiring in your real detection logic

`app/detection/c1.py` and `app/detection/isolation_forest.py` are
placeholders with the correct interface. Replace their bodies with your
validated implementations from the Streamlit build
(github.com/gathokib/outbreak-ews) — keep the same function signature
and returned columns and nothing else in the app needs to change.

## Wiring in your real data

Drop OWID/JHU extracts into `data/<country>.csv` with columns `date,cases`
(lowercase filename, spaces as underscores — e.g. `data/kenya.csv`).
`app/pipeline/data_loader.py` picks these up automatically and they'll
appear in the pipeline page's country dropdown.

## Project structure

```
app/
  __init__.py          # app factory
  extensions.py         # db, login_manager
  models.py              # User, PipelineRun, Alert, Country
  auth/                   # register, login, logout
  dashboard/              # risk status cards
  surveillance/           # interactive charts + JSON API
  pipeline/               # trigger runs, view live results
  alerts/                 # alerts log with filters
  detection/              # C1 and Isolation Forest (placeholders — see above)
  templates/, static/
data/                     # demo case-count CSVs
config.py
run.py
```

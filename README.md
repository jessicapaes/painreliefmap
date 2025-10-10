# PainReliefMap — Evidence Explorer + N‑of‑1 Tracker

A Streamlit app that lets you **explore public evidence** (ClinicalTrials.gov + PubMed counts) for pain-related therapies and **log your own daily well‑being** (N‑of‑1) to see what helps you most.

> This README matches the files you currently have in the repository **root**: `app.py`, `build_evidence_counts_aact.py`, `db.py`, `requirements.txt`, and optionally `evidence_counts.csv`.

---

## ✨ Features

* **📈 Evidence Explorer**

  * Filter by **condition** and **therapy**
  * See trial counts (ClinicalTrials.gov) and literature counts (PubMed)
  * Handy links out to **Trials** and **Articles** search pages

* **🌿 Daily Wellness Log (N‑of‑1)**

  * Patient‑friendly form: date, pain/stress sliders, sleep, mood, movement, digestion, cravings
  * Optional cycle tracking (toggle)
  * “Duplicate yesterday”, quick notes, “mark good day”
  * Review entries in a table and export from Streamlit if needed

* **🧪 Data Profile (EDA)**

  * KPI tiles, top‑20 leaderboards, and a concise data dictionary

---

## 🧭 Solution Architecture

```
┌──────────────────────────────────────────────────────────┐
│                         Browser                          │
└──────────────────────────────────────────────────────────┘
                   │  Streamlit UI + Plotly
                   ▼
┌──────────────────────────────────────────────────────────┐
│                 Streamlit App (app.py)                  │
│  • Tabs: Evidence Explorer | Data Profile | Daily Log   │
│  • Robust CSV loader (root/data/data/raw)               │
│  • Session-state for N‑of‑1 table + quick actions       │
└──────────────────────────────────────────────────────────┘
          │                         │
          │                         │ (optional)
          ▼                         ▼
┌───────────────────────────┐   ┌──────────────────────────┐
│ Evidence CSV (local)      │   │ Cloud DB (optional)      │
│ • evidence_counts.csv     │   │ PostgreSQL/Supabase      │
│   at **root** or          │   │ via `db.py` (SQLAlchemy) │
│   data/ or data/raw/      │   └──────────────────────────┘
└───────────────────────────┘
          ▲
          │ (one‑shot build / refresh)
          │
┌──────────────────────────────────────────────────────────┐
│ Evidence Builder (build_evidence_counts_aact.py)         │
│ • Reads AACT flat files placed in data/raw/              │
│ • Counts trials per (condition, therapy)                 │
│ • Fetches PubMed counts via E‑utilities                  │
│ • Adds links + optional metadata columns                 │
│ • Saves to data/raw/evidence_counts.csv                  │
└──────────────────────────────────────────────────────────┘
```

---

## 🌐 Data Sources

PainReliefMap combines **external scientific evidence** with **user-generated daily tracking data** to help users explore what works for them.

| Source Type                                   | Description                                                                                                                                                                                               | Access / API URL                                                                                                                                                                                                                                                                                                                                                                               | Used In                                                                                        |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| 🧾 **ClinicalTrials.gov (AACT Flat Files)**   | Official U.S. registry of clinical trials. The AACT dataset (Aggregate Analysis of ClinicalTrials.gov) provides downloadable flat files of all registered trials, including conditions and interventions. | [https://aact.ctti-clinicaltrials.org/pipe_files](https://aact.ctti-clinicaltrials.org/pipe_files)                                                                                                                                                                                                                                                                                             | `build_evidence_counts_aact.py` — counts number of clinical trials per *(condition × therapy)* |
| 📚 **PubMed (NCBI E-Utilities API)**          | Biomedical literature database maintained by the U.S. National Library of Medicine. The E-Utilities API is used to fetch the number of published papers for each *(condition × therapy)* combination.     | **Docs:** [https://www.ncbi.nlm.nih.gov/books/NBK25499/](https://www.ncbi.nlm.nih.gov/books/NBK25499/) · **Example query:** [https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&term=(Fibromyalgia)%20AND%20(Acupuncture)](https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&term=%28Fibromyalgia%29%20AND%20%28Acupuncture%29) | `build_evidence_counts_aact.py` — retrieves publication counts (`pubmed_n`)                    |
| 📅 **User Daily Wellness Logs (N-of-1 Data)** | Self-reported data entered directly in the Streamlit “Daily Wellness Log” tab. Includes pain, stress, sleep, movement, digestion, mood, and therapy usage.                                                | Local input via Streamlit UI; template at `data/templates/n_of_1_template.csv`                                                                                                                                                                                                                                                                                                                 | `app.py` — stores and visualizes daily well-being trends                                       |

### 📊 Output Datasets

| File                                 | Generated By                    | Description                                                                                                                 |
| ------------------------------------ | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `data/raw/evidence_counts.csv`       | `build_evidence_counts_aact.py` | Combined evidence summary for all condition × therapy pairs, with columns for `clinicaltrials_n`, `pubmed_n`, and metadata. |
| `data/templates/n_of_1_template.csv` | Manual / Streamlit              | Template for personal tracking data; used in N-of-1 analysis preparation.                                                   |

---

## 📦 What’s in this repo (now)

```
.
├── app.py                       # Streamlit app (3 tabs)
├── build_evidence_counts_aact.py# Evidence builder (AACT + PubMed)
├── db.py                        # Optional Postgres/Supabase helpers
├── requirements.txt             # Python deps
└── evidence_counts.csv          # (optional) evidence table; can also live in data/ or data/raw/
```

> If you later reorganize into folders (e.g., `app/`, `src/`, `scripts/`), the code is already written to tolerate CSV in `data/` or `data/raw/`.

---

## 📚 File‑level details (aligned with your code)

### `app.py`

* Sets the page title **“Pain Relief Map — Evidence Explorer + N‑of‑1”**
* **CSV Locator**: looks for `evidence_counts.csv` in `data/`, then `data/raw/`, then repo **root**.
* **Filters** in the sidebar: condition, therapies, year range, evidence direction, study type, countries, quality, participant filters (sex, age), language, and sorting.
* **Evidence Direction chart**: percentage breakdown with sensible colours if the `evidence_direction` column exists.
* **Daily Log**: big form with sliders and multiselects; “Duplicate yesterday”, “Quick note”, “Mark good day”, and optional menstrual cycle block.

### `build_evidence_counts_aact.py`

* Expects **AACT flat files** under `data/raw/` (e.g., `studies*.txt*`, `conditions*.txt*`, `interventions*.txt*`).
* Computes `clinicaltrials_n` per (condition, therapy), fetches `pubmed_n`, builds **links**, stamps `last_updated`, and saves to `data/raw/evidence_counts.csv`.
* On success, prints a ✅ line with row count and output path.
* (Optional) Attempts `from src.db import upsert_pairs`. If you are using the **current** root‑level `db.py`, either move it to `src/db.py` or change the import in the builder to `import db as src_db` and call `src_db.upsert_pairs(...)`.

### `db.py`

* Uses `DATABASE_URL` to open a SQLAlchemy engine.
* Provides:

  * `upsert_pairs(df)`: upsert one row per `(condition, therapy)` into `evidence_pairs` (requires that table and an `on conflict (condition,therapy)` index).
  * `read_pairs()`: read the whole table to a DataFrame.
* If you keep `db.py` at the **root**, update the builder import as noted above.

### `requirements.txt`

Exact deps used by your code:

* streamlit, pandas, numpy, plotly, requests
* statsmodels, scikit‑learn (planned causal features)
* sqlalchemy, psycopg2‑binary, supabase (optional DB path)
* beautifulsoup4 (HTML fallback/scraping if needed)

---

## 🚀 Setup & Run

### 1) Environment

```bash
conda create -n painreliefmap312 python=3.12.6
conda activate painreliefmap312
pip install -r requirements.txt
```

### 2) Provide evidence data

* Easiest: place `evidence_counts.csv` at **repo root** (works out of the box), or in `data/` or `data/raw/`.
* To **rebuild** from AACT + PubMed:

  1. Download AACT **Flat Text Files** and extract to `data/raw/`.
  2. Run:

     ```bash
     python -u build_evidence_counts_aact.py
     ```

     This saves `data/raw/evidence_counts.csv` and prints where it went.

### 3) (Optional) Connect a database

```bash
# Example (Supabase/Postgres)
set DATABASE_URL=postgresql+psycopg2://<user>:<pass>@<host>:<port>/<db>?sslmode=require
# macOS/Linux: export DATABASE_URL=...
```

* Ensure a table `evidence_pairs` exists with a **unique (condition, therapy)** constraint for upserts.

### 4) Run the app

```bash
streamlit run app.py
```

Open: [http://localhost:8501](http://localhost:8501)

---

## 🧪 Notes on N‑of‑1 (in this version)

* Entries are stored in **session state** (memory) during a run. Use the table to copy/export.
* The causal engine placeholder from earlier versions (bootstrap pre/post effect) isn’t wired in this root‑level layout yet; you can integrate it later once you add a small `src/causal.py` module and a “Run Analysis” button.

---

## 🔍 Troubleshooting

* **“I couldn’t find evidence_counts.csv”**
  Place the file at **repo root**, or at `data/evidence_counts.csv`, or `data/raw/evidence_counts.csv`. The app checks all three.

* **PubMed/AACT builder fails to import `src.db`**
  Either move `db.py` to `src/db.py` **or** change the line in the builder:

  ```python
  # from src.db import upsert_pairs
  import db as src_db
  src_db.upsert_pairs(out)
  ```

* **Charts show blanks for PubMed**
  Rebuild with the builder script to populate `pubmed_n`, or ensure the column exists in your CSV.

---

## 🗺️ Roadmap (near‑term)

* Wire a bootstrap pre/post effect (`src/causal.py`) and add an “Analyze” button
* Optional persistence of Daily Log to Postgres
* More filters (effect size, quality bands) and trend charts for N‑of‑1

---

## 📄 License

MIT (choose your preferred OSS license if different)

---

## 🙏 Acknowledgements

* ClinicalTrials.gov (AACT) and PubMed E‑utilities
* Streamlit, Pandas, NumPy, Plotly, SQLAlchemy
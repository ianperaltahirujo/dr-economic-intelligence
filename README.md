# DR Economic Intelligence Pipeline

Automated weekly system that scores Dominican Republic economic vulnerability, produces a formatted Excel workbook, and publishes a Spanish-language dashboard to GitHub Pages. Built for La Sociedad's upper management as a non-technical weekly briefing tool.

**[View Live Website →](https://ianperaltahirujo.github.io/dr-economic-intelligence)**

---

## What it does

Every Monday at 9:00 AM Santo Domingo time, a GitHub Actions workflow:

1. Downloads fresh BCRD Excel files from the official CDN
2. Fetches banking indicators from the Superintendencia de Bancos API
3. Fetches U.S. leading indicators from the FRED API
4. Computes a weighted 0–100 Vulnerability Score using z-scores
5. Generates a formatted Excel workbook with 6 sheets
6. Publishes a Spanish-language website to GitHub Pages

The pipeline is fully autonomous after deployment. No manual intervention is needed between runs.

---

## Vulnerability Score

The headline score combines 12 indicators into a single 0–100 composite. Higher scores indicate greater economic stress.

| Indicator                         | Weight | Direction        |
| --------------------------------- | ------ | ---------------- |
| Remesas familiares (USD mm)       | 10%    | Falling = stress |
| Inflación interanual (%)         | 10%    | Rising = stress  |
| Tasa de cambio DOP/USD            | 15%    | Rising = stress  |
| Reservas internacionales (USD mm) | 10%    | Falling = stress |
| IMAE (actividad económica)       | 5%     | Falling = stress |
| Morosidad bancaria (%)            | 10%    | Rising = stress  |
| Solvencia bancaria (%)            | 5%     | Falling = stress |
| Desempleo EE.UU. (%)              | 10%    | Rising = stress  |
| Confianza del consumidor EE.UU.   | 5%     | Falling = stress |
| Tasa de interés activa (%)       | 5%     | Rising = stress  |
| Gasolina Premium (DOP/galón)     | 5%     | Rising = stress  |
| Gasto turístico diario (USD)     | 10%    | Falling = stress |

**Score bands:** 0–49 = Normal, 50–64 = Moderate Stress, 65–100 = High Stress (alert)

**Z-score windows:** 60 months for IPC and exchange rate; 36 months for all others. A minimum of 12 months of history is required before a z-score is computed.

**Absolute level overrides:** Certain indicators trigger stress regardless of z-score (IPC above 7%, DOP/USD above 65, UMCSENT below 60).

**Provisional nowcast:** The BCRD tourism spending survey publishes approximately 6 months behind. When this indicator is forward-filled, the score is labeled *Avance Estimado* and the history chart renders the provisional period as a dashed line. All other institutional lags (remesas, IMAE, SB banking) are covered by a 2-month fill that does not trigger the provisional flag.

---

## Repository structure

```
dr-economic-intelligence/
├── run_pipeline.py                      # Main entry point
├── requirements.txt
│
├── pipeline/
│   ├── download_bcrd_files.py           # Downloads BCRD Excel files from CDN
│   ├── download_context_files.py        # Downloads gas price and tourism context files
│   ├── ingest_bcrd.py                   # Parses BCRD Excel files into DataFrames
│   ├── ingest_bcrd_api.py               # BCRD REST API client (IP-whitelisted endpoints)
│   ├── ingest_sb.py                     # Superintendencia de Bancos API v2 client
│   ├── ingest_fred_dr.py                # FRED API client for U.S. indicators
│   ├── ingest_context.py                # Gas prices, tourism fiscal revenue, national debt
│   ├── ingest_debt.py                   # BCRD consolidated public debt (quarterly)
│   ├── build_vulnerability.py           # Scoring engine, z-scores, weights, alerts
│   ├── backtest_weights.py              # Weight optimizer against known stress periods
│   ├── write_excel.py                   # Excel workbook writer (6 sheets)
│   ├── write_html.py                    # GitHub Pages site generator
│   ├── ms_graph.py                      # Microsoft Graph client (OneDrive upload, Outlook email)
│   └── monthly_report_state.py          # Tracks which months already have a finalized Monthly Report
│
├── docs/
│   ├── clima-social.html                    # Static Clima Social page
│   ├── fonts/                           # For loading necessary font files for both pages
│   └── index.html                       # Auto-generated, do not edit manually
│
├── data/
│   ├── raw/                             # Downloaded source files (gitignored)
│   ├── processed/                       # Intermediate CSVs (gitignored)
│   └── output/                          # Final Excel workbook
|
├── tests/
│   ├── README.md                        # A short README note for the tests directory    
│   ├── test_build_vulnerability.py
│   └── test_regression_real_data.py
│   └── fixtures/
│        └── vulnerability_history.csv
│
└── .github/workflows/
    └── weekly_pipeline.yml              # GitHub Actions workflow
```

---

## Setup

### Prerequisites

- Python 3.11+
- API keys for FRED and Superintendencia de Bancos

### Local installation

```bash
git clone https://github.com/ianperaltahirujo/dr-economic-intelligence.git
cd dr-economic-intelligence

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the project root:

```
FRED_API_KEY=your_fred_api_key
SB_API_KEY=your_sb_api_key
BCRD_API_KEY=your_bcrd_api_key
```

FRED keys are free at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html). The SB API key is obtained through the [Superintendencia de Bancos developer portal](https://desarrollador.sb.gob.do). The BCRD API requires IP whitelisting through their developer portal, all endpoints return HTTP 500 until the calling IP is registered.

### Running locally

```bash
# Full run (downloads fresh BCRD files)
python run_pipeline.py

# Skip BCRD download (use cached files in data/raw/)
python run_pipeline.py --skip-download

# Score only, no Excel or HTML output
python run_pipeline.py --dry-run
```

### Windows execution policy

On a new Windows machine, run this before activating the venv:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## GitHub Actions deployment

The workflow in `.github/workflows/weekly_pipeline.yml` runs every Monday at 13:00 UTC (9:00 AM Santo Domingo time).

### Required secrets

Add these in **Settings > Secrets and variables > Actions**:

| Secret           | Description                        |
| ---------------- | ---------------------------------- |
| `FRED_API_KEY` | FRED API key                       |
| `SB_API_KEY`   | Superintendencia de Bancos API key |
| `BCRD_API_KEY` | Banco Central API key              |
| `AZURE_TENANT_ID` | Azure AD app registration tenant ID (Microsoft Graph) |
| `AZURE_CLIENT_ID` | Azure AD app registration client ID (Microsoft Graph) |
| `AZURE_CLIENT_SECRET` | Azure AD app registration client secret (Microsoft Graph) |
| `EMAIL_RECIPIENTS` | Comma-separated recipient list for the weekly summary email; if unset, the email step is skipped |

### Manual trigger

The workflow can be triggered manually from the Actions tab. An optional `skip_download` input is available to rerun scoring without re-downloading BCRD files.

### Artifacts

Each run uploads the Excel workbook as a workflow artifact retained for 90 days, accessible from the Actions tab regardless of OneDrive/email delivery status.

---

## Data sources

| Source                            | Indicators                                                                    | Access method                        |
| --------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------ |
| BCRD CDN                          | Remesas, IMAE, exchange rate, IPC, reserves, tourism arrivals                 | Direct HTTPS download (no auth)      |
| BCRD CDN                          | Gas prices context, tourism fiscal revenue, consolidated debt                 | Direct HTTPS download (no auth)      |
| MICM                              | Fuel prices (weekly)                                                          | Open data CSV                        |
| Superintendencia de Bancos API v2 | Solvency, NPL ratio, lending rates, financial ratios                          | `Ocp-Apim-Subscription-Key` header |
| FRED API                          | U.S. unemployment (UNRATE), consumer sentiment (UMCSENT), yield curve, others | API key                              |

### Known data constraints

**BCRD API:** Requires IP whitelisting. Only `HistoricoTasas` and `HistoricoIPC` return true historical time series; all other `MacroVariables` endpoints return current-snapshot only. CDN file downloads are the reliable path for historical data. JavaScript-rendered pages cannot be scraped for URLs, correct file URLs must be found manually via browser.

**SB API:** The `indicadores/financieros` endpoint is hard-capped at 36 months to prevent timeouts. Intermittent 500 errors on valid requests are resolved with exponential backoff (2s, 4s, 8s). The `solvencia` and `tasaActiva` columns return `0.00` instead of null for the most recent unvalidated months, the pipeline treats these as missing values.

**Tourism spending:** The BCRD survey publishes approximately 6 months behind. The pipeline forward-fills the last known value for up to 6 months and marks affected scores as provisional.

---

## Output

### Excel workbook (`data/output/vulnerability_report.xlsx`)

| Sheet      | Contents                                                                        |
| ---------- | ------------------------------------------------------------------------------- |
| Dashboard  | Headline score, status, all 12 indicators with values, trend arrows, and status |
| Contexto   | Non-scored context indicators: tourism fiscal revenue, consolidated public debt |
| Indicators | Full indicator detail with z-scores, weights, and stress contributions          |
| Alerts     | Plain-language alert strings for all flagged indicators                         |
| History    | Last 60 months of scores and raw indicator values                               |
| Metadata   | Run timestamp, data source freshness, methodology notes                         |

### GitHub Pages site (`docs/index.html`)

Spanish-language dashboard with weekly briefing, macroeconomic context cards, indicator alerts, interactive indicator panel with filters, full score history chart with zoom and pan.

---

## Architecture decisions

**Single truth function:** All stress classification logic lives in `classify_indicator()` in `build_vulnerability.py`. The scoring engine, website cards, Excel sheets, and alert strings all call the same function, so the score and the UI can never disagree.

**Strict coverage rule:** A vulnerability score is only computed for months where all 12 indicators are present after targeted fills. There is no renormalization over a partial indicator set, because a score built from 10 of 12 indicators is not the same quantity as one built from all 12.

**Targeted forward-fills:** Each indicator has an explicit fill limit based on its publication cadence. Blind `ffill()` across all columns is avoided, fills are per-indicator and tracked, so the pipeline knows exactly which months contain estimates.

**Context vs. score separation:** Gas prices, tourism fiscal revenue, and public debt appear in the Context section of the dashboard but do not contribute to the vulnerability score. Gas prices and tourism daily spend were promoted into the score; tourism fiscal revenue and consolidated debt remained as context because their annual resolution and forward-fill artifacts would distort z-score calculations.

---

## Weight backtesting

`pipeline/backtest_weights.py` evaluates how well the current weights separate known stress periods from calm baseline periods using historical data.

```bash
# Run backtest only
python pipeline/backtest_weights.py

# Run backtest and apply optimized weights (requires confirmation)
python pipeline/backtest_weights.py --apply
```

Known stress periods used for calibration: COVID collapse (Mar–Sep 2020), post-COVID recovery (Jan–Jun 2021), inflation peak (Jun–Dec 2022), U.S. rate shock (Jan–Jun 2023).

---

## OneDrive and email integration

After each run, the pipeline writes and uploads Excel snapshots to OneDrive and sends a summary email, both via Microsoft Graph using app-only (client-credentials) authentication — there is no signed-in user context. Implemented in `pipeline/ms_graph.py`, wired in via `step_write_weekly_report()`, `step_write_monthly_report()`, `step_upload_onedrive()`, and `step_send_email()` in `run_pipeline.py`.

- **OneDrive target:** the OneDrive belonging to `work@lasociedad.com.do` (env `ONEDRIVE_OWNER_UPN`), under base folder `Economic Intelligence/Output/` (env `ONEDRIVE_FOLDER_PATH`) — a folder that account genuinely owns. App-only auth cannot resolve "shared with me" items (Graph returns 403 for that under client-credentials auth) and Graph's path-based upload silently auto-creates missing folders rather than failing, so the target folder must be one `work@lasociedad.com.do` owns outright, not a folder merely shared with it. Visibility from the team's shared `Propuestas y Proyectos` folder is handled by a one-time manual OneDrive shortcut placed inside it, pointing at this owned `Economic Intelligence` folder — not by the pipeline.
- **Weekly Reports** (`Economic Intelligence/Output/Weekly Reports/`): every run writes a new, dated workbook (`vulnerability_report_weekly_YYYY-MM-DD.xlsx`) headlined by the current in-progress calendar month's *projected* score — the same number shown on the website hero, built from `build_vulnerability.estimate_current_month()`. Old weekly files are never deleted; they're a permanent audit trail.
- **Monthly Reports** (`Economic Intelligence/Output/Monthly Reports/`): once a month has full indicator coverage (12/12 present after the existing fill policy — i.e. the same rule that already governs the historical record, see "Strict coverage rule" below), a single finalized workbook is written for that month (`vulnerability_report_YYYY-MM.xlsx`), headlined by the confirmed score. State is tracked in `data/state/monthly_reports_state.json` so a month's file is only rewritten if it's new or its provisional status changes (e.g. `tourism_daily_spend_usd`'s real value finally arrives, replacing a forward-filled estimate) — never re-uploaded every week for no reason. The "Avance Estimado" disclosure stays intact in both Excel and on the website whenever a component is filled; finalizing at 12/12-after-fills does not hide that disclosure.
- **Summary email:** sent from `work@lasociedad.com.do` (env `EMAIL_SENDER_UPN`) via Graph `sendMail`, with that run's Weekly Report attached. A static Spanish HTML template linking to the live dashboard, referencing the same projected current-month date as the Weekly Report. Recipients come from the comma-separated `EMAIL_RECIPIENTS` secret; if unset, the email step is skipped, not an error.

All of these steps are best-effort: failures are logged but never fail the workflow run. The dashboard commit and the original `vulnerability_report.xlsx` artifact upload always proceed regardless of whether OneDrive/email succeeded.

---

## Git workflow

The GitHub Actions workflow commits the regenerated `docs/index.html` back to the repo on each run. If local changes conflict with the Actions commit:

```bash
git stash
git pull --rebase
git stash pop
git push
```

The local branch is `main` tracking `origin/main`.

---

## Author

Ian Eduardo Peralta Hirujo |
B.S. Applied Data Sciences, The Pennsylvania State University

---

## Built with

Python 3.11 · pandas · numpy · openpyxl · fredapi · requests · python-dotenv · scipy · Chart.js · GitHub Actions · GitHub Pages

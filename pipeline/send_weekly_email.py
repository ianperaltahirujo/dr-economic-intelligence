"""
Sends the weekly summary email as its own GitHub Actions step, run after
"Commit updated dashboard" -- so a Graph/email failure here can't block
that week's dashboard publish the way it would if it ran inside the same
"Run pipeline" step (a single process's exit code gates the next workflow
step). run_pipeline.py's own step_send_email() still sends this inline for
a plain local `python run_pipeline.py` run; the workflow instead passes
--skip-email to that step and calls this script afterward. See
pipeline/notify_failure.py, which fires on this script's failure (or any
other step's) and alerts only the maintainer, never the full recipient list.

Reads the score date from data/state/current_month_snapshots.json (this
month's in-progress estimate, if this run refreshed it) or, failing that,
data/processed/vulnerability_scored.csv (last confirmed month) -- both
already written by the earlier "Run pipeline" step in the same job. Mirrors
step_send_email()'s precedence: current-month estimate first, else the last
confirmed historical month.
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd

from pipeline.ms_graph import send_summary_email
from pipeline.write_html import MONTHS_ES
from run_pipeline import build_email_html, DASHBOARD_URL, EMAIL_SENDER_NAME

SNAPSHOT_PATH = "data/state/current_month_snapshots.json"
SCORED_CSV_PATH = "data/processed/vulnerability_scored.csv"


def _score_date():
    snapshot_path = Path(SNAPSHOT_PATH)
    if snapshot_path.exists():
        try:
            data = json.loads(snapshot_path.read_text(encoding="utf-8"))
            month = data.get("month")
            if month and month == pd.Timestamp.now().strftime("%Y-%m"):
                return pd.Timestamp(f"{month}-01")
        except (json.JSONDecodeError, ValueError):
            pass

    csv_path = Path(SCORED_CSV_PATH)
    if csv_path.exists():
        scored = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        if "vulnerability_score" in scored.columns:
            valid = scored["vulnerability_score"].dropna()
            if not valid.empty:
                return valid.index[-1]
    return None


def main() -> None:
    recipients = [r.strip() for r in os.getenv("EMAIL_RECIPIENTS", "").split(",") if r.strip()]
    if not recipients:
        print("EMAIL_RECIPIENTS not set -- skipping summary email.")
        return

    score_date = _score_date()
    date_str = (
        f"{MONTHS_ES[score_date.month].capitalize()} de {score_date.year}"
        if score_date is not None else ""
    )

    subject = "Reporte Semanal Economic Intelligence"
    if date_str:
        subject += f" -- {date_str}"

    body_html = build_email_html(date_str=date_str, dashboard_url=DASHBOARD_URL)

    ok = send_summary_email(
        sender_upn=os.getenv("EMAIL_SENDER_UPN", "work@lasociedad.com.do"),
        recipients=recipients,
        subject=subject,
        body_text=body_html,
        content_type="HTML",
        sender_name=EMAIL_SENDER_NAME,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

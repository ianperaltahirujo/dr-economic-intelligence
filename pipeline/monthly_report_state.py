"""
Tracks which months already have a finalized "Monthly Report" workbook
uploaded to OneDrive, and that month's is_provisional status as of the last
upload -- so the weekly pipeline run only (re)generates and re-uploads a
month's Monthly Report when it's new, or when its status has changed since
last time (e.g. tourism_daily_spend_usd's real value finally arrived for a
month that was previously filled).

Lives outside data/processed/, which is gitignored and does not exist on
the GitHub Actions runner between scheduled runs. This file is meant to
survive across weekly runs, so it is tracked in git and committed by the
workflow alongside docs/index.html, the same way current_month_tracker.py's
snapshot file is.
"""

import json
from pathlib import Path

import pandas as pd

DEFAULT_PATH = "data/state/monthly_reports_state.json"


def month_key(date: pd.Timestamp) -> str:
    return date.strftime("%Y-%m")


def load_state(path: str = DEFAULT_PATH) -> dict:
    """Read the state file. Returns an empty structure if it doesn't exist
    or is unreadable -- this is an upload-bookkeeping mechanism, not a
    truthfulness-critical path, so a corrupt file should not fail the
    pipeline."""
    p = Path(path)
    if not p.exists():
        return {"months": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if "months" not in data:
            raise ValueError("malformed monthly report state file")
        return data
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  WARNING: monthly report state file at {path} is corrupt ({e}); starting fresh.")
        return {"months": {}}


def needs_upload(state: dict, month: str, is_provisional: bool) -> bool:
    """
    True if `month` has never had a Monthly Report uploaded, or if its
    is_provisional status has changed since the last recorded upload (e.g.
    a filled indicator was replaced by real data, correcting the score).
    """
    recorded = state.get("months", {}).get(month)
    if recorded is None:
        return True
    return recorded.get("is_provisional") != is_provisional


def record_upload(state: dict, month: str, is_provisional: bool,
                   as_of: pd.Timestamp = None, path: str = DEFAULT_PATH) -> dict:
    """Record that `month`'s Monthly Report was just (re)uploaded, and
    persist the state file."""
    as_of = as_of or pd.Timestamp.now()
    state.setdefault("months", {})[month] = {
        "is_provisional": is_provisional,
        "uploaded_at": as_of.strftime("%Y-%m-%d %H:%M:%S"),
    }

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state

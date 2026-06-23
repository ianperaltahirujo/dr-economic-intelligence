"""
Persists a weekly snapshot of the current in-progress month's estimated
vulnerability score, so the dashboard can show "this month's score" as the
average of however many weekly pipeline runs have happened so far this
month, rather than a single point-in-time read.

This deliberately lives outside data/processed/, which is gitignored and
does not exist on the GitHub Actions runner between scheduled runs (it is
regenerated from scratch every time). The snapshot file here is meant to
survive across weekly runs, so it is tracked in git and committed by the
workflow alongside docs/index.html.

Each entry is keyed by week-of-month (1-5), not by exact date, so a manual
re-run (workflow_dispatch) within the same week updates that week's entry
instead of skewing the average with a duplicate. The whole list resets
when the calendar month rolls over.
"""

import json
from pathlib import Path

import pandas as pd

DEFAULT_PATH = "data/state/current_month_snapshots.json"


def month_key(date: pd.Timestamp) -> str:
    return date.strftime("%Y-%m")


def week_of_month(date: pd.Timestamp) -> int:
    return (date.day - 1) // 7 + 1


def _empty(month: str) -> dict:
    return {"month": month, "snapshots": []}


def load_snapshots(path: str = DEFAULT_PATH) -> dict:
    """Read the snapshot file. Returns an empty structure if it doesn't
    exist or is unreadable -- this is an ancillary display mechanism, not
    a truthfulness-critical path, so a corrupt file should not fail the
    pipeline."""
    p = Path(path)
    if not p.exists():
        return _empty(month=None)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if "month" not in data or "snapshots" not in data:
            raise ValueError("malformed snapshot file")
        return data
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  WARNING: snapshot file at {path} is corrupt ({e}); starting fresh.")
        return _empty(month=None)


def record_weekly_snapshot(score: float, as_of: pd.Timestamp = None,
                            path: str = DEFAULT_PATH) -> dict:
    """
    Append (or update, if this week already has an entry) this run's
    current-month estimate, resetting the list if the calendar month has
    rolled over since the last recorded snapshot. Writes the result back
    to `path` and returns the updated structure.
    """
    as_of = as_of or pd.Timestamp.now()
    current_month = month_key(as_of)
    current_week = week_of_month(as_of)

    data = load_snapshots(path)
    if data["month"] != current_month:
        data = _empty(current_month)

    entry = {
        "week": current_week,
        "date": as_of.strftime("%Y-%m-%d"),
        "score": float(score),
    }
    data["snapshots"] = [s for s in data["snapshots"] if s["week"] != current_week]
    data["snapshots"].append(entry)
    data["snapshots"].sort(key=lambda s: s["week"])

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def average_score(data: dict) -> float:
    """Mean of all recorded snapshot scores for the month, or None if
    there are none."""
    scores = [s["score"] for s in data.get("snapshots", [])]
    if not scores:
        return None
    return sum(scores) / len(scores)

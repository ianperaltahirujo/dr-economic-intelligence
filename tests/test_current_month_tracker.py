"""
Tests for pipeline/current_month_tracker.py.

Covers: week-of-month math against the user's own stated example (June 23
-> week 4), append-vs-update-by-week dedup (so a manual re-run doesn't
skew the average), reset on month rollover, and graceful handling of a
missing/corrupt snapshot file.

Run with:
    pytest tests/test_current_month_tracker.py -v
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.current_month_tracker import (
    week_of_month,
    month_key,
    load_snapshots,
    record_weekly_snapshot,
    average_score,
)


class TestWeekOfMonth:
    def test_june_23_is_week_4(self):
        # The exact example given when this feature was requested.
        assert week_of_month(pd.Timestamp("2026-06-23")) == 4

    def test_first_day_of_month_is_week_1(self):
        assert week_of_month(pd.Timestamp("2026-06-01")) == 1

    def test_day_8_is_week_2(self):
        assert week_of_month(pd.Timestamp("2026-06-08")) == 2


class TestRecordAndAverage:
    def test_first_snapshot_of_a_month(self, tmp_path):
        path = tmp_path / "snapshots.json"
        data = record_weekly_snapshot(50.0, as_of=pd.Timestamp("2026-06-01"), path=str(path))
        assert data["month"] == "2026-06"
        assert len(data["snapshots"]) == 1
        assert average_score(data) == 50.0

    def test_subsequent_weeks_accumulate_and_average(self, tmp_path):
        path = tmp_path / "snapshots.json"
        record_weekly_snapshot(50.0, as_of=pd.Timestamp("2026-06-01"), path=str(path))
        record_weekly_snapshot(52.0, as_of=pd.Timestamp("2026-06-08"), path=str(path))
        data = record_weekly_snapshot(54.0, as_of=pd.Timestamp("2026-06-15"), path=str(path))
        assert len(data["snapshots"]) == 3
        assert average_score(data) == pytest.approx((50.0 + 52.0 + 54.0) / 3)

    def test_rerun_within_same_week_replaces_not_appends(self, tmp_path):
        path = tmp_path / "snapshots.json"
        record_weekly_snapshot(50.0, as_of=pd.Timestamp("2026-06-02"), path=str(path))
        data = record_weekly_snapshot(60.0, as_of=pd.Timestamp("2026-06-03"), path=str(path))
        # both 2026-06-02 and 2026-06-03 are week 1 -- must collapse to one entry
        assert len(data["snapshots"]) == 1
        assert average_score(data) == 60.0

    def test_new_month_resets_the_list(self, tmp_path):
        path = tmp_path / "snapshots.json"
        record_weekly_snapshot(50.0, as_of=pd.Timestamp("2026-06-22"), path=str(path))
        data = record_weekly_snapshot(70.0, as_of=pd.Timestamp("2026-07-01"), path=str(path))
        assert data["month"] == "2026-07"
        assert len(data["snapshots"]) == 1
        assert average_score(data) == 70.0

    def test_persists_to_disk_and_reloads(self, tmp_path):
        path = tmp_path / "snapshots.json"
        record_weekly_snapshot(48.0, as_of=pd.Timestamp("2026-06-01"), path=str(path))
        reloaded = load_snapshots(str(path))
        assert reloaded["month"] == "2026-06"
        assert average_score(reloaded) == 48.0


class TestMissingOrCorruptFile:
    def test_missing_file_returns_empty_structure(self, tmp_path):
        data = load_snapshots(str(tmp_path / "does_not_exist.json"))
        assert data["snapshots"] == []
        assert average_score(data) is None

    def test_corrupt_file_does_not_raise(self, tmp_path):
        path = tmp_path / "snapshots.json"
        path.write_text("{not valid json", encoding="utf-8")
        data = load_snapshots(str(path))
        assert data["snapshots"] == []

    def test_recording_over_a_corrupt_file_recovers(self, tmp_path):
        path = tmp_path / "snapshots.json"
        path.write_text("not json at all", encoding="utf-8")
        data = record_weekly_snapshot(55.0, as_of=pd.Timestamp("2026-06-01"), path=str(path))
        assert average_score(data) == 55.0

"""
Tests for pipeline/monthly_report_state.py.

Covers: a never-uploaded month always needs upload, an already-uploaded
month with unchanged provisional status does not, a status flip (e.g.
tourism's real data finally arriving) does trigger a re-upload, and
graceful handling of a missing/corrupt state file.

Run with:
    pytest tests/test_monthly_report_state.py -v
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.monthly_report_state import (
    month_key,
    load_state,
    needs_upload,
    record_upload,
)


class TestMonthKey:
    def test_formats_as_year_month(self):
        assert month_key(pd.Timestamp("2026-05-17")) == "2026-05"


class TestNeedsUpload:
    def test_never_uploaded_month_needs_upload(self):
        state = {"months": {}}
        assert needs_upload(state, "2026-05", is_provisional=True) is True

    def test_already_uploaded_with_same_status_does_not_need_upload(self):
        state = {"months": {"2026-05": {"is_provisional": True, "uploaded_at": "x"}}}
        assert needs_upload(state, "2026-05", is_provisional=True) is False

    def test_status_flip_triggers_reupload(self):
        # Tourism's real data arrived, the month went from provisional to confirmed.
        state = {"months": {"2026-05": {"is_provisional": True, "uploaded_at": "x"}}}
        assert needs_upload(state, "2026-05", is_provisional=False) is True


class TestRecordAndPersist:
    def test_record_upload_persists_to_disk(self, tmp_path):
        path = tmp_path / "state.json"
        state = record_upload({"months": {}}, "2026-05", is_provisional=True,
                               as_of=pd.Timestamp("2026-06-24"), path=str(path))
        assert state["months"]["2026-05"]["is_provisional"] is True

        reloaded = load_state(str(path))
        assert reloaded["months"]["2026-05"]["is_provisional"] is True

    def test_subsequent_record_updates_existing_entry(self, tmp_path):
        path = tmp_path / "state.json"
        record_upload({"months": {}}, "2026-05", is_provisional=True, path=str(path))
        state = load_state(str(path))
        state = record_upload(state, "2026-05", is_provisional=False, path=str(path))
        assert state["months"]["2026-05"]["is_provisional"] is False
        assert len(state["months"]) == 1


class TestMissingOrCorruptFile:
    def test_missing_file_returns_empty_structure(self, tmp_path):
        data = load_state(str(tmp_path / "does_not_exist.json"))
        assert data["months"] == {}

    def test_corrupt_file_does_not_raise(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("{not valid json", encoding="utf-8")
        data = load_state(str(path))
        assert data["months"] == {}

    def test_recording_over_a_corrupt_file_recovers(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("not json at all", encoding="utf-8")
        state = load_state(str(path))
        state = record_upload(state, "2026-05", is_provisional=True, path=str(path))
        assert state["months"]["2026-05"]["is_provisional"] is True

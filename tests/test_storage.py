import json
import sys

from app.data.models import AppSettings, DailySummary, WorkSessionRecord
from app.data.storage import PROJECT_ROOT, JsonStorage, get_default_storage_path


def test_settings_save_and_load(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")

    assert storage.load_settings().break_interval_minutes == 45

    storage.save_settings(AppSettings(break_interval_minutes=55))

    assert storage.load_settings().break_interval_minutes == 55


def test_work_minutes_save_and_load(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")

    storage.set_work_minutes("2026-05-21", 42)

    assert storage.get_work_minutes("2026-05-21") == 42
    assert storage.get_work_minutes("2026-05-22") == 0


def test_default_storage_path_uses_project_data_for_source_run(monkeypatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert get_default_storage_path() == PROJECT_ROOT / "data" / "daily_records.json"


def test_default_storage_path_uses_exe_folder_when_bundled(
    monkeypatch,
    tmp_path,
) -> None:
    executable_path = tmp_path / "HealthyWork.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable_path))

    assert get_default_storage_path() == tmp_path / "data" / "daily_records.json"


def test_work_session_records_save_load_and_old_file_default(tmp_path) -> None:
    file_path = tmp_path / "daily_records.json"
    file_path.write_text(
        json.dumps(
            {
                "settings": {"break_interval_minutes": 45},
                "break_records": [],
                "daily_summaries": [],
                "daily_work_minutes": {},
            }
        ),
        encoding="utf-8",
    )
    storage = JsonStorage(file_path)

    assert storage.list_work_session_records("2026-05-21") == []

    record = WorkSessionRecord(
        id="session-1",
        date="2026-05-21",
        start_time="2026-05-21T09:00:00",
        end_time="2026-05-21T10:00:00",
        duration_minutes=60,
        ended_by="break",
    )
    storage.add_work_session_record(record)

    records = storage.list_work_session_records("2026-05-21")
    assert len(records) == 1
    assert records[0].duration_minutes == 60
    assert records[0].ended_by == "break"


def test_daily_summary_from_old_format_defaults_new_fields() -> None:
    summary = DailySummary.from_dict(
        {
            "date": "2026-05-22",
            "work_minutes": 60,
            "break_minutes": 5,
            "break_count": 1,
            "water_ml": 100,
            "average_work_session_minutes": 60,
            "health_score": 80,
            "suggestions": ["ok"],
            "created_at": "2026-05-22T20:00:00",
        }
    )

    assert summary.basic_water_target_ml == 0
    assert summary.ideal_water_target_ml == 0
    assert summary.recommended_break_minutes == 0
    assert summary.longest_work_session_minutes is None
    assert summary.work_session_count == 0
    assert summary.health_score == 80


def test_daily_summary_allows_missing_health_score() -> None:
    summary = DailySummary(
        date="2026-05-22",
        work_minutes=0,
        break_minutes=0,
        break_count=0,
        water_ml=0,
        average_work_session_minutes=None,
        health_score=None,
    )

    assert summary.health_score is None
    assert summary.to_dict()["health_score"] is None

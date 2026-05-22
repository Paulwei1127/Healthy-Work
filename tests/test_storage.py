from app.data.models import AppSettings, DailySummary
from app.data.storage import JsonStorage


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

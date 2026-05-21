from app.data.models import AppSettings
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

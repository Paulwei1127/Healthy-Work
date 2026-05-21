import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.data.models import BreakRecord
from app.core.timer import TimerState
from app.data.storage import JsonStorage
import app.ui.main_window as main_window_module
from app.ui.main_window import MainWindow


def test_reminder_dialog_is_triggered_once_per_reminder_round(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    calls: list[str] = []
    window._show_reminder_dialog = lambda: calls.append("shown")  # type: ignore[method-assign]

    window.timer.start_work(1)
    snapshot = window.timer.tick(60)

    window._maybe_show_reminder_dialog(snapshot)
    window._maybe_show_reminder_dialog(snapshot)

    assert calls == ["shown"]

    window.timer.snooze()
    window._render(window.timer.snapshot())
    snapshot = window.timer.tick(300)
    window._maybe_show_reminder_dialog(snapshot)

    assert calls == ["shown", "shown"]
    window.qt_timer.stop()
    window.window.close()


def test_work_minutes_are_saved_without_waiting_for_end_day(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    window.timer.start_work(1)
    window.timer.tick(75)
    window._save_work_minutes_if_needed()

    assert storage.get_work_minutes(window.today) == 1
    window.qt_timer.stop()
    window.window.close()


def test_settings_are_saved_when_work_starts(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    window.interval_input.setText("55")
    window._on_start_work()

    assert storage.load_settings().break_interval_minutes == 55
    window.qt_timer.stop()
    window.window.close()


def test_date_rollover_saves_old_day_and_loads_new_day(tmp_path) -> None:
    current_date = date(2026, 5, 20)
    storage = JsonStorage(tmp_path / "daily_records.json")
    storage.set_work_minutes("2026-05-21", 7)

    def date_provider() -> date:
        return current_date

    window = MainWindow(storage=storage, date_provider=date_provider)
    window.timer.start_work(45)
    window.timer.tick(120)

    current_date = date(2026, 5, 21)

    assert window._check_date_rollover() is True
    assert storage.get_work_minutes("2026-05-20") == 2
    assert window.today == "2026-05-21"
    assert window.timer.snapshot().state == TimerState.IDLE
    assert window.timer.snapshot().total_work_seconds == 7 * 60
    window.qt_timer.stop()
    window.window.close()


def test_start_work_reopens_today_after_end_day(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    window.timer.start_work(1)
    window.timer.tick(30)
    window.timer.end_day()
    window._render(window.timer.snapshot())

    assert window.start_button.isEnabled()

    window.interval_input.setText("25")
    window._on_start_work()

    snapshot = window.timer.snapshot()
    assert snapshot.state == TimerState.WORKING
    assert snapshot.break_interval_minutes == 25
    assert snapshot.total_work_seconds == 30
    window.qt_timer.stop()
    window.window.close()


def test_end_day_can_finish_and_save_active_break(tmp_path, monkeypatch) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    shown_reports: list[object] = []

    class FakeReportDialog:
        def __init__(self, parent, summary) -> None:
            self.summary = summary

        def show(self) -> None:
            shown_reports.append(self.summary)

    monkeypatch.setattr(main_window_module, "ReportDialog", FakeReportDialog)

    def save_pending_break(resume_after_save: bool = True) -> bool:
        assert resume_after_save is False
        pending = window._pending_break
        assert pending is not None
        record = BreakRecord.create(
            start_time=pending.start_time,
            end_time=pending.end_time,
            duration_minutes=pending.duration_minutes,
        )
        storage.add_break_record(record)
        window._session_break_records.append(record)
        window._pending_break = None
        return True

    window._show_break_record_dialog = save_pending_break  # type: ignore[method-assign]

    window.timer.start_work(1)
    window.timer.start_break_early()
    window._on_end_day()

    assert window.timer.snapshot().state == TimerState.DAY_ENDED
    assert len(storage.list_break_records(window.today)) == 1
    assert shown_reports
    window.qt_timer.stop()
    window.window.close()

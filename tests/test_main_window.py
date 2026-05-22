import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QDialog

from app.data.models import BreakRecord
from app.core.timer import TimerState
from app.data.storage import JsonStorage
import app.ui.animation as animation_module
import app.ui.main_window as main_window_module
import app.ui.reminder_dialog as reminder_dialog_module
from app.ui.main_window import (
    ANIMATION_BOX_SIZE,
    LOTTIE_WEB_PLAYER_PATH,
    MainWindow,
    TIMER_STATE_TO_GIF,
    TIMER_STATE_TO_LOTTIE,
    get_resource_path,
)
from app.ui.reminder_dialog import (
    REMINDER_ANIMATION_BOX_SIZE,
    REMINDER_GIF_PATH,
    REMINDER_LOTTIE_PATH,
    ReminderAction,
    ReminderDialog,
)


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


def test_idle_primary_button_starts_work(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    assert window.start_button.text() == "開始工作"

    window.start_button.click()

    assert window.timer.snapshot().state == TimerState.WORKING
    assert window.start_button.text() == "開始工作"
    assert not window.start_button.isEnabled()
    assert window.start_button.toolTip() == "已在工作倒數中"
    window.qt_timer.stop()
    window.window.close()


def test_interval_input_is_read_only_while_working(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    assert not window.interval_input.isReadOnly()

    window._on_start_work()

    assert window.interval_input.isReadOnly()
    assert "工作倒數期間不可修改" in window.interval_input.toolTip()

    window._run_timer_action(window.timer.pause)

    assert not window.interval_input.isReadOnly()
    window.qt_timer.stop()
    window.window.close()


def test_control_area_does_not_create_legacy_resume_or_return_buttons(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    assert not hasattr(window, "resume_button")
    assert not hasattr(window, "return_work_button")
    window.qt_timer.stop()
    window.window.close()


def test_primary_button_has_disabled_stylesheet_rule(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    assert "QPushButton#PrimaryButton:disabled" in window.window.styleSheet()
    window.qt_timer.stop()
    window.window.close()


def test_each_timer_state_has_animation_gif_mapping() -> None:
    assert set(TIMER_STATE_TO_GIF) == set(TimerState)


def test_each_timer_state_has_lottie_json_mapping() -> None:
    assert set(TIMER_STATE_TO_LOTTIE) == set(TimerState)
    assert get_resource_path(LOTTIE_WEB_PLAYER_PATH).exists()
    for relative_path in TIMER_STATE_TO_LOTTIE.values():
        assert get_resource_path(relative_path).exists()


def test_each_timer_state_has_gif_fallback_file() -> None:
    for relative_path in TIMER_STATE_TO_GIF.values():
        assert get_resource_path(relative_path).exists()


def test_state_animation_is_not_rebuilt_when_state_is_unchanged(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    window._update_state_animation(TimerState.IDLE)
    first_movie = window._state_animation_movie
    first_mode = window._state_animation_mode
    first_lottie_path = window.lottie_animation_view._loaded_path
    window._update_state_animation(TimerState.IDLE)

    assert window._state_animation_movie is first_movie
    assert window._state_animation_mode == first_mode
    assert window.lottie_animation_view._loaded_path == first_lottie_path
    assert window.animation_label.size() == ANIMATION_BOX_SIZE
    window.qt_timer.stop()
    window.window.close()


def test_lottie_is_preferred_when_loader_succeeds(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    loaded_paths = []

    def fake_load_lottie(animation_path):
        loaded_paths.append(animation_path)
        window.lottie_animation_view._loaded_path = animation_path
        return True

    window._stop_state_animation()
    window._state_animation_state = None
    window.lottie_animation_view.load_lottie = fake_load_lottie  # type: ignore[method-assign]

    window._update_state_animation(TimerState.WORKING)

    assert window._state_animation_mode == "lottie"
    assert window._state_animation_movie is None
    assert loaded_paths == [get_resource_path(TIMER_STATE_TO_LOTTIE[TimerState.WORKING])]
    window.qt_timer.stop()
    window.window.close()


def test_lottie_is_not_reloaded_when_state_is_unchanged(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    loaded_paths = []

    def fake_load_lottie(animation_path):
        loaded_paths.append(animation_path)
        window.lottie_animation_view._loaded_path = animation_path
        return True

    window._stop_state_animation()
    window._state_animation_state = None
    window.lottie_animation_view.load_lottie = fake_load_lottie  # type: ignore[method-assign]

    window._update_state_animation(TimerState.PAUSED)
    window._update_state_animation(TimerState.PAUSED)

    assert window._state_animation_mode == "lottie"
    assert loaded_paths == [get_resource_path(TIMER_STATE_TO_LOTTIE[TimerState.PAUSED])]
    window.qt_timer.stop()
    window.window.close()


def test_missing_lottie_json_falls_back_to_gif_without_crashing(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setitem(
        main_window_module.TIMER_STATE_TO_LOTTIE,
        TimerState.IDLE,
        "gif/json/does-not-exist.json",
    )
    storage = JsonStorage(tmp_path / "daily_records.json")

    window = MainWindow(storage=storage)

    assert window._state_animation_state == TimerState.IDLE
    assert window._state_animation_mode == "gif"
    assert window.animation_label.size() == ANIMATION_BOX_SIZE
    window.qt_timer.stop()
    window.window.close()


def test_webengine_unavailable_falls_back_to_gif_without_crashing(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(animation_module, "QWebEngineView", None)
    storage = JsonStorage(tmp_path / "daily_records.json")

    window = MainWindow(storage=storage)

    assert window._state_animation_state == TimerState.IDLE
    assert window._state_animation_mode == "gif"
    assert window.animation_label.size() == ANIMATION_BOX_SIZE
    window.qt_timer.stop()
    window.window.close()


def test_invalid_lottie_json_returns_false_without_crashing(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{", encoding="utf-8")

    class FakeWebEngineView:
        def setHtml(self, *args, **kwargs):
            raise AssertionError("invalid JSON should not reach setHtml")

    window.lottie_animation_view._view = FakeWebEngineView()

    assert window.lottie_animation_view.load_lottie(invalid_json) is False
    window.lottie_animation_view._view = None
    window.qt_timer.stop()
    window.window.close()


def test_lottie_set_html_failure_falls_back_to_gif(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    class FailingWebEngineView:
        def setHtml(self, *args, **kwargs):
            raise RuntimeError("web engine failed")

    window._stop_state_animation()
    window._state_animation_state = None
    window.lottie_animation_view._view = FailingWebEngineView()

    window._update_state_animation(TimerState.IDLE)

    assert window._state_animation_mode == "gif"
    window.qt_timer.stop()
    window.window.close()


def test_reminder_dialog_initializes_animation_widget(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    dialog = ReminderDialog(window.window)

    assert dialog.animation_widget.size() == REMINDER_ANIMATION_BOX_SIZE
    assert dialog.animation_mode in {"lottie", "gif", "blank"}
    dialog.reject()
    window.qt_timer.stop()
    window.window.close()


def test_reminder_dialog_uses_reminder_animation_paths(tmp_path, monkeypatch) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    load_calls = []

    def fake_load(self, lottie_path, gif_path):
        load_calls.append((lottie_path, gif_path))
        return "lottie"

    monkeypatch.setattr(
        reminder_dialog_module.LottieGifAnimationWidget,
        "load",
        fake_load,
    )

    dialog = ReminderDialog(window.window)

    assert load_calls == [(REMINDER_LOTTIE_PATH, REMINDER_GIF_PATH)]
    assert dialog.animation_mode == "lottie"
    dialog.reject()
    window.qt_timer.stop()
    window.window.close()


def test_reminder_dialog_falls_back_to_gif_when_lottie_unavailable(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    dialog = ReminderDialog(window.window)

    assert dialog.animation_mode == "gif"
    dialog.reject()
    window.qt_timer.stop()
    window.window.close()


def test_reminder_dialog_uses_blank_animation_when_all_assets_missing(
    tmp_path,
    monkeypatch,
) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    monkeypatch.setattr(
        reminder_dialog_module,
        "REMINDER_LOTTIE_PATH",
        "gif/json/does-not-exist.json",
    )
    monkeypatch.setattr(
        reminder_dialog_module,
        "REMINDER_GIF_PATH",
        "gif/does-not-exist.gif",
    )

    dialog = ReminderDialog(window.window)

    assert dialog.animation_mode == "blank"
    dialog.reject()
    window.qt_timer.stop()
    window.window.close()


def test_reminder_dialog_reject_still_snoozes_when_animation_clear_fails(
    tmp_path,
) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    dialog = ReminderDialog(window.window)

    def fail_clear():
        raise RuntimeError("clear failed")

    dialog.animation_widget.clear = fail_clear  # type: ignore[method-assign]

    dialog.reject()

    assert dialog.action == ReminderAction.SNOOZE
    assert dialog.result() == QDialog.Accepted
    window.qt_timer.stop()
    window.window.close()


def test_missing_animation_gif_does_not_crash_window_init(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(
        main_window_module.TIMER_STATE_TO_GIF,
        TimerState.IDLE,
        "gif/does-not-exist.gif",
    )
    storage = JsonStorage(tmp_path / "daily_records.json")

    window = MainWindow(storage=storage)

    assert window._state_animation_state == TimerState.IDLE
    assert window._state_animation_movie is None
    assert window.animation_label.size() == ANIMATION_BOX_SIZE
    window.qt_timer.stop()
    window.window.close()


def test_editing_finished_valid_interval_saves_settings(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    window.interval_input.setText("50")
    window.interval_input.editingFinished.emit()

    assert storage.load_settings().break_interval_minutes == 50
    assert window.timer.snapshot().break_interval_minutes == 50
    assert window.timer.snapshot().remaining_seconds == 50 * 60
    window.qt_timer.stop()
    window.window.close()


def test_editing_finished_invalid_interval_restores_previous_valid_value(
    tmp_path,
    monkeypatch,
) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    warnings: list[str] = []
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "warning",
        lambda *args, **kwargs: warnings.append(str(args[2])),
    )

    window.interval_input.setText("50")
    window.interval_input.editingFinished.emit()
    window.interval_input.setText("")
    window.interval_input.editingFinished.emit()

    assert storage.load_settings().break_interval_minutes == 50
    assert window.timer.snapshot().break_interval_minutes == 50
    assert window.interval_input.text() == "50"
    assert window.timer.snapshot().state == TimerState.IDLE
    assert warnings
    window.qt_timer.stop()
    window.window.close()


def test_breaking_interval_change_applies_to_next_work_round(tmp_path, monkeypatch) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    class FakeBreakRecordDialog:
        def __init__(self, parent, completed_break) -> None:
            self.water_ml = 250
            self.note = "伸展一下"

        def exec_(self) -> int:
            return QDialog.Accepted

    monkeypatch.setattr(
        main_window_module,
        "BreakRecordDialog",
        FakeBreakRecordDialog,
    )

    window._on_start_work()
    window._on_start_break()
    assert window.timer.snapshot().state == TimerState.BREAKING
    assert not window.interval_input.isReadOnly()

    window.interval_input.setText("30")
    window.timer.tick(120)
    window.start_button.click()

    snapshot = window.timer.snapshot()
    assert snapshot.state == TimerState.WORKING
    assert snapshot.break_interval_minutes == 30
    assert snapshot.remaining_seconds == 30 * 60
    assert storage.load_settings().break_interval_minutes == 30
    assert storage.list_break_records(window.today)[0].water_ml == 250
    window.qt_timer.stop()
    window.window.close()


def test_breaking_primary_button_cancel_keeps_pending_break(tmp_path, monkeypatch) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    class CanceledBreakRecordDialog:
        water_ml = 0
        note = ""

        def __init__(self, parent, completed_break) -> None:
            pass

        def exec_(self) -> int:
            return QDialog.Rejected

    monkeypatch.setattr(
        main_window_module,
        "BreakRecordDialog",
        CanceledBreakRecordDialog,
    )

    window._on_start_work()
    window._on_start_break()
    assert window.timer.snapshot().state == TimerState.BREAKING
    assert window.start_button.text() == "回到工作"

    window.start_button.click()

    assert window.timer.snapshot().state == TimerState.PAUSED
    assert window._pending_break is not None
    assert window.start_button.text() == "回到工作"
    assert not storage.list_break_records(window.today)
    window.qt_timer.stop()
    window.window.close()


def test_paused_interval_change_is_saved_and_applied_on_resume(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    window._on_start_work()
    window._run_timer_action(window.timer.pause)
    window.interval_input.setText("35")

    assert window.start_button.text() == "繼續工作"

    window.start_button.click()

    snapshot = window.timer.snapshot()
    assert snapshot.state == TimerState.WORKING
    assert snapshot.break_interval_minutes == 35
    assert snapshot.remaining_seconds == 35 * 60
    assert storage.load_settings().break_interval_minutes == 35
    window.qt_timer.stop()
    window.window.close()


def test_reminder_primary_button_starts_break(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)

    window._on_start_work()
    window.timer.tick(45 * 60)
    window._render(window.timer.snapshot())

    assert window.timer.snapshot().state == TimerState.REMINDER
    assert window.start_button.text() == "開始休息"
    assert window.start_button.toolTip() == "開始本次休息。"
    assert not window.start_break_button.isEnabled()

    window.start_button.click()

    assert window.timer.snapshot().state == TimerState.BREAKING
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
    assert storage.load_settings().break_interval_minutes == 25
    assert window.interval_input.isReadOnly()
    window.qt_timer.stop()
    window.window.close()


def test_invalid_interval_does_not_save_or_change_paused_state(tmp_path, monkeypatch) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    warnings: list[str] = []
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "warning",
        lambda *args, **kwargs: warnings.append(str(args[2])),
    )

    window._on_start_work()
    window._run_timer_action(window.timer.pause)
    window.interval_input.setText("0")

    window.start_button.click()

    snapshot = window.timer.snapshot()
    assert snapshot.state == TimerState.PAUSED
    assert snapshot.break_interval_minutes == 45
    assert storage.load_settings().break_interval_minutes == 45
    assert warnings
    window.qt_timer.stop()
    window.window.close()


def test_reminder_dialog_close_defaults_to_snooze(tmp_path) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    dialog = ReminderDialog(window.window)

    dialog.reject()

    assert dialog.action == ReminderAction.SNOOZE
    assert dialog.result() == QDialog.Accepted
    window.qt_timer.stop()
    window.window.close()


def test_reminder_dialog_snooze_with_invalid_interval_does_not_stick_in_reminder(
    tmp_path,
    monkeypatch,
) -> None:
    storage = JsonStorage(tmp_path / "daily_records.json")
    window = MainWindow(storage=storage)
    warnings: list[str] = []

    class FakeReminderDialog:
        def __init__(self, parent) -> None:
            self.action = ReminderAction.SNOOZE

        def exec_(self) -> int:
            return QDialog.Accepted

    monkeypatch.setattr(main_window_module, "ReminderDialog", FakeReminderDialog)
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "warning",
        lambda *args, **kwargs: warnings.append(str(args[2])),
    )

    window._on_start_work()
    window.timer.tick(45 * 60)
    window._render(window.timer.snapshot())
    window.interval_input.setText("0")

    window._show_reminder_dialog()

    snapshot = window.timer.snapshot()
    assert snapshot.state == TimerState.WORKING
    assert snapshot.remaining_seconds == 5 * 60
    assert window.interval_input.text() == "45"
    assert warnings
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

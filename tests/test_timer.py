from datetime import datetime, timedelta

from app.core.timer import (
    MAX_RECORDED_BREAK_MINUTES,
    MAX_RECORDED_BREAK_SECONDS,
    TimerState,
    WorkTimer,
)


def test_elapsed_tick_counts_real_seconds() -> None:
    timer = WorkTimer(break_interval_minutes=45)

    timer.start_work()
    snapshot = timer.tick(125)

    assert snapshot.state == TimerState.WORKING
    assert snapshot.total_work_seconds == 125
    assert snapshot.remaining_seconds == (45 * 60) - 125


def test_elapsed_tick_caps_work_time_at_reminder_boundary() -> None:
    timer = WorkTimer(break_interval_minutes=1)

    timer.start_work()
    snapshot = timer.tick(75)

    assert snapshot.state == TimerState.REMINDER
    assert snapshot.total_work_seconds == 60
    assert snapshot.remaining_seconds == 0


def test_start_break_early_from_working_and_paused() -> None:
    timer = WorkTimer(break_interval_minutes=45)

    timer.start_work()
    timer.tick(30)
    snapshot = timer.start_break_early()

    assert snapshot.state == TimerState.BREAKING
    assert snapshot.total_work_seconds == 30
    assert snapshot.break_start_time is not None

    timer.return_to_work()
    timer.resume_work()
    timer.pause()
    snapshot = timer.start_break_early()

    assert snapshot.state == TimerState.BREAKING


def test_set_break_interval_is_allowed_in_non_working_states() -> None:
    timer = WorkTimer(break_interval_minutes=45)

    timer.set_break_interval(30)
    assert timer.snapshot().remaining_seconds == 30 * 60

    timer.start_work()
    timer.tick(30 * 60)
    assert timer.snapshot().state == TimerState.REMINDER
    timer.set_break_interval(25)
    assert timer.snapshot().break_interval_minutes == 25

    timer.start_break()
    timer.set_break_interval(20)
    assert timer.snapshot().break_interval_minutes == 20

    timer.return_to_work()
    timer.set_break_interval(15)
    assert timer.snapshot().remaining_seconds == 15 * 60


def test_completed_break_under_cap_keeps_actual_duration() -> None:
    break_start = datetime(2026, 5, 26, 10, 0, 0)
    break_end = break_start + timedelta(minutes=30)
    now_values = iter([break_start, break_end])
    timer = WorkTimer(now_provider=lambda: next(now_values))

    timer.start_work()
    timer.start_break_early()
    completed_break = timer.return_to_work()

    assert completed_break.duration_minutes == 30
    assert completed_break.duration_seconds == 30 * 60
    assert completed_break.actual_duration_minutes == 30
    assert completed_break.actual_duration_seconds == 30 * 60
    assert completed_break.was_duration_capped is False


def test_completed_break_over_cap_records_maximum_duration() -> None:
    break_start = datetime(2026, 5, 26, 10, 0, 0)
    break_end = break_start + timedelta(minutes=MAX_RECORDED_BREAK_MINUTES + 1)
    now_values = iter([break_start, break_end])
    timer = WorkTimer(now_provider=lambda: next(now_values))

    timer.start_work()
    timer.start_break_early()
    completed_break = timer.return_to_work()

    assert completed_break.duration_minutes == MAX_RECORDED_BREAK_MINUTES
    assert completed_break.duration_seconds == MAX_RECORDED_BREAK_SECONDS
    assert completed_break.actual_duration_minutes == MAX_RECORDED_BREAK_MINUTES + 1
    assert completed_break.was_duration_capped is True

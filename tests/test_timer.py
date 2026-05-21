from app.core.timer import TimerState, WorkTimer


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

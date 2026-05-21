"""Pure timer and application state management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import ceil
from typing import Callable


DEFAULT_BREAK_INTERVAL_MINUTES = 45
SNOOZE_MINUTES = 5
SECONDS_PER_MINUTE = 60


class TimerState(str, Enum):
    """Supported app states for the MVP timer."""

    IDLE = "Idle"
    WORKING = "Working"
    PAUSED = "Paused"
    REMINDER = "Reminder"
    BREAKING = "Breaking"
    DAY_ENDED = "DayEnded"


class TimerStateError(RuntimeError):
    """Raised when a timer action is not valid for the current state."""


@dataclass(frozen=True)
class CompletedBreak:
    """Result returned when a break is finished."""

    start_time: datetime
    end_time: datetime
    duration_seconds: int
    duration_minutes: int


@dataclass(frozen=True)
class TimerSnapshot:
    """Read-only timer state for UI or tests."""

    state: TimerState
    break_interval_minutes: int
    remaining_seconds: int
    total_work_seconds: int
    total_work_minutes: int
    break_elapsed_seconds: int
    break_start_time: datetime | None
    last_completed_break: CompletedBreak | None


class WorkTimer:
    """State machine for work countdowns and automatic break timing."""

    def __init__(
        self,
        break_interval_minutes: int = DEFAULT_BREAK_INTERVAL_MINUTES,
        initial_work_seconds: int = 0,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.break_interval_minutes = _validate_positive_int(
            break_interval_minutes,
            "break_interval_minutes",
        )
        self._state = TimerState.IDLE
        self._remaining_seconds = self.break_interval_minutes * SECONDS_PER_MINUTE
        self._total_work_seconds = _validate_non_negative_int(
            initial_work_seconds,
            "initial_work_seconds",
        )
        self._break_start_time: datetime | None = None
        self._break_elapsed_seconds = 0
        self._last_completed_break: CompletedBreak | None = None
        self._now_provider = now_provider or datetime.now

    @property
    def state(self) -> TimerState:
        return self._state

    @property
    def remaining_seconds(self) -> int:
        return self._remaining_seconds

    @property
    def total_work_seconds(self) -> int:
        return self._total_work_seconds

    @property
    def total_work_minutes(self) -> int:
        return self._total_work_seconds // SECONDS_PER_MINUTE

    @property
    def break_elapsed_seconds(self) -> int:
        return self._break_elapsed_seconds

    @property
    def break_start_time(self) -> datetime | None:
        return self._break_start_time

    @property
    def last_completed_break(self) -> CompletedBreak | None:
        return self._last_completed_break

    def snapshot(self) -> TimerSnapshot:
        return TimerSnapshot(
            state=self._state,
            break_interval_minutes=self.break_interval_minutes,
            remaining_seconds=self._remaining_seconds,
            total_work_seconds=self._total_work_seconds,
            total_work_minutes=self.total_work_minutes,
            break_elapsed_seconds=self._break_elapsed_seconds,
            break_start_time=self._break_start_time,
            last_completed_break=self._last_completed_break,
        )

    def set_break_interval(self, minutes: int) -> TimerSnapshot:
        self._ensure_state(
            {
                TimerState.IDLE,
                TimerState.PAUSED,
                TimerState.REMINDER,
                TimerState.BREAKING,
                TimerState.DAY_ENDED,
            },
            "set break interval",
        )
        self.break_interval_minutes = _validate_positive_int(
            minutes,
            "break_interval_minutes",
        )
        self._remaining_seconds = self.break_interval_minutes * SECONDS_PER_MINUTE
        return self.snapshot()

    def start_work(self, break_interval_minutes: int | None = None) -> TimerSnapshot:
        self._ensure_state({TimerState.IDLE}, "start work")
        if break_interval_minutes is not None:
            self.break_interval_minutes = _validate_positive_int(
                break_interval_minutes,
                "break_interval_minutes",
            )

        self._reset_countdown()
        self._state = TimerState.WORKING
        return self.snapshot()

    def pause(self) -> TimerSnapshot:
        self._ensure_state({TimerState.WORKING}, "pause")
        self._state = TimerState.PAUSED
        return self.snapshot()

    def resume_work(self) -> TimerSnapshot:
        self._ensure_state({TimerState.PAUSED}, "resume work")
        self._state = TimerState.WORKING
        return self.snapshot()

    def restart_countdown(
        self,
        break_interval_minutes: int | None = None,
    ) -> TimerSnapshot:
        self._ensure_state(
            {
                TimerState.IDLE,
                TimerState.WORKING,
                TimerState.PAUSED,
                TimerState.REMINDER,
            },
            "restart countdown",
        )
        if break_interval_minutes is not None:
            self.break_interval_minutes = _validate_positive_int(
                break_interval_minutes,
                "break_interval_minutes",
            )

        self._reset_countdown()
        self._state = TimerState.WORKING
        return self.snapshot()

    def snooze(self, minutes: int = SNOOZE_MINUTES) -> TimerSnapshot:
        self._ensure_state({TimerState.REMINDER}, "snooze")
        snooze_minutes = _validate_positive_int(minutes, "minutes")
        self._remaining_seconds = snooze_minutes * SECONDS_PER_MINUTE
        self._state = TimerState.WORKING
        return self.snapshot()

    def tick(self, seconds: int = 1) -> TimerSnapshot:
        elapsed_seconds = _validate_non_negative_int(seconds, "seconds")
        if elapsed_seconds == 0:
            return self.snapshot()

        if self._state == TimerState.WORKING:
            counted_seconds = min(elapsed_seconds, self._remaining_seconds)
            self._total_work_seconds += counted_seconds
            self._remaining_seconds = max(0, self._remaining_seconds - elapsed_seconds)
            if self._remaining_seconds == 0:
                self._state = TimerState.REMINDER
        elif self._state == TimerState.BREAKING:
            self._break_elapsed_seconds += elapsed_seconds

        return self.snapshot()

    def start_break(self) -> TimerSnapshot:
        self._ensure_state({TimerState.REMINDER}, "start break")
        self._begin_break()
        return self.snapshot()

    def start_break_early(self) -> TimerSnapshot:
        self._ensure_state(
            {
                TimerState.WORKING,
                TimerState.PAUSED,
            },
            "start break early",
        )
        self._begin_break()
        return self.snapshot()

    def _begin_break(self) -> None:
        self._break_start_time = self._now()
        self._break_elapsed_seconds = 0
        self._remaining_seconds = 0
        self._state = TimerState.BREAKING

    def return_to_work(self, auto_start_next_round: bool = False) -> CompletedBreak:
        self._ensure_state({TimerState.BREAKING}, "return to work")
        if self._break_start_time is None:
            raise TimerStateError("Cannot finish break without a start time.")

        break_end_time = self._now()
        wall_clock_seconds = max(
            0,
            int((break_end_time - self._break_start_time).total_seconds()),
        )
        duration_seconds = max(wall_clock_seconds, self._break_elapsed_seconds)
        completed_break = CompletedBreak(
            start_time=self._break_start_time,
            end_time=break_end_time,
            duration_seconds=duration_seconds,
            duration_minutes=_seconds_to_minutes_ceiling(duration_seconds),
        )

        self._last_completed_break = completed_break
        self._break_start_time = None
        self._break_elapsed_seconds = 0
        self._reset_countdown()
        self._state = TimerState.WORKING if auto_start_next_round else TimerState.PAUSED
        return completed_break

    def end_day(self) -> TimerSnapshot:
        self._ensure_state(
            {
                TimerState.IDLE,
                TimerState.WORKING,
                TimerState.PAUSED,
                TimerState.REMINDER,
            },
            "end day",
        )
        self._state = TimerState.DAY_ENDED
        self._remaining_seconds = 0
        return self.snapshot()

    def reset_day(
        self,
        break_interval_minutes: int | None = None,
        initial_work_seconds: int = 0,
    ) -> TimerSnapshot:
        if break_interval_minutes is not None:
            self.break_interval_minutes = _validate_positive_int(
                break_interval_minutes,
                "break_interval_minutes",
            )

        self._total_work_seconds = _validate_non_negative_int(
            initial_work_seconds,
            "initial_work_seconds",
        )
        self._break_start_time = None
        self._break_elapsed_seconds = 0
        self._last_completed_break = None
        self._reset_countdown()
        self._state = TimerState.IDLE
        return self.snapshot()

    def _reset_countdown(self) -> None:
        self._remaining_seconds = self.break_interval_minutes * SECONDS_PER_MINUTE

    def _ensure_state(self, allowed_states: set[TimerState], action: str) -> None:
        if self._state not in allowed_states:
            allowed = ", ".join(state.value for state in sorted(allowed_states, key=str))
            raise TimerStateError(
                f"Cannot {action} while timer is {self._state.value}. "
                f"Allowed states: {allowed}."
            )

    def _now(self) -> datetime:
        return self._now_provider()


def _seconds_to_minutes_ceiling(seconds: int) -> int:
    normalized_seconds = _validate_non_negative_int(seconds, "seconds")
    if normalized_seconds == 0:
        return 0
    return ceil(normalized_seconds / SECONDS_PER_MINUTE)


def _validate_positive_int(value: int, field_name: str) -> int:
    number = _validate_non_negative_int(value, field_name)
    if number < 1:
        raise ValueError(f"{field_name} must be at least 1.")
    return number


def _validate_non_negative_int(value: int, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")

    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc

    if number < 0:
        raise ValueError(f"{field_name} must be at least 0.")

    return number

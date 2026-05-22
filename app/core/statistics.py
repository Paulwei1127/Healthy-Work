"""Pure daily statistics calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.data.models import BreakRecord, WorkSessionRecord


@dataclass(frozen=True)
class DailyStatistics:
    """Calculated statistics for one day."""

    date: str
    work_minutes: int
    break_minutes: int
    break_count: int
    water_ml: int
    average_work_session_minutes: float | None
    basic_water_target_ml: int
    ideal_water_target_ml: int
    recommended_break_minutes: int
    longest_work_session_minutes: int | None = None
    work_session_count: int = 0


def calculate_work_minutes(work_minutes: int) -> int:
    """Normalize accumulated Working-state minutes."""

    return _coerce_non_negative_int(work_minutes, "work_minutes")


def calculate_break_minutes(records: Iterable[BreakRecord]) -> int:
    """Return total completed break minutes."""

    return sum(record.duration_minutes for record in records)


def calculate_break_count(records: Iterable[BreakRecord]) -> int:
    """Return number of completed break records."""

    return sum(1 for _ in records)


def calculate_water_ml(records: Iterable[BreakRecord]) -> int:
    """Return total water intake in milliliters."""

    return sum(record.water_ml for record in records)


def calculate_average_work_session_minutes(
    work_minutes: int,
    break_count: int,
) -> float | None:
    """Return work minutes divided by completed breaks, or None when unavailable."""

    normalized_work_minutes = calculate_work_minutes(work_minutes)
    normalized_break_count = _coerce_non_negative_int(break_count, "break_count")

    if normalized_break_count == 0:
        return None

    return round(normalized_work_minutes / normalized_break_count, 2)


def calculate_average_work_session_minutes_from_sessions(
    records: Iterable[WorkSessionRecord],
) -> float | None:
    """Return average duration across precise work sessions."""

    session_minutes = [record.duration_minutes for record in records]
    if not session_minutes:
        return None

    return round(sum(session_minutes) / len(session_minutes), 2)


def calculate_longest_work_session_minutes(
    records: Iterable[WorkSessionRecord],
) -> int | None:
    """Return the longest recorded continuous work session."""

    session_minutes = [record.duration_minutes for record in records]
    if not session_minutes:
        return None

    return max(session_minutes)


def calculate_basic_water_target_ml(work_minutes: int) -> int:
    """Return the proportional basic water target for recorded work time."""

    normalized_work_minutes = calculate_work_minutes(work_minutes)
    return round((normalized_work_minutes / 60) * 1500 / 16)


def calculate_ideal_water_target_ml(work_minutes: int) -> int:
    """Return the proportional ideal water target for recorded work time."""

    normalized_work_minutes = calculate_work_minutes(work_minutes)
    return round((normalized_work_minutes / 60) * 2000 / 16)


def calculate_recommended_break_minutes(work_minutes: int) -> int:
    """Return recommended total break minutes: at least 5 minutes per work hour."""

    normalized_work_minutes = calculate_work_minutes(work_minutes)
    return round((normalized_work_minutes / 60) * 5)


def calculate_daily_statistics(
    date: str,
    work_minutes: int,
    break_records: Iterable[BreakRecord],
    work_session_records: Iterable[WorkSessionRecord] | None = None,
) -> DailyStatistics:
    """Calculate all user-facing statistics for one date."""

    normalized_date = _coerce_date(date)
    normalized_work_minutes = calculate_work_minutes(work_minutes)
    records = _records_for_date(break_records, normalized_date)
    session_records = _work_sessions_for_date(
        work_session_records or [],
        normalized_date,
    )
    break_count = calculate_break_count(records)
    session_count = len(session_records)
    average_work_session_minutes = (
        calculate_average_work_session_minutes_from_sessions(session_records)
        if session_count
        else calculate_average_work_session_minutes(
            normalized_work_minutes,
            break_count,
        )
    )

    return DailyStatistics(
        date=normalized_date,
        work_minutes=normalized_work_minutes,
        break_minutes=calculate_break_minutes(records),
        break_count=break_count,
        water_ml=calculate_water_ml(records),
        average_work_session_minutes=average_work_session_minutes,
        basic_water_target_ml=calculate_basic_water_target_ml(normalized_work_minutes),
        ideal_water_target_ml=calculate_ideal_water_target_ml(normalized_work_minutes),
        recommended_break_minutes=calculate_recommended_break_minutes(
            normalized_work_minutes
        ),
        longest_work_session_minutes=calculate_longest_work_session_minutes(
            session_records
        ),
        work_session_count=session_count,
    )


def _records_for_date(
    records: Iterable[BreakRecord],
    target_date: str,
) -> list[BreakRecord]:
    return [record for record in records if record.date == target_date]


def _work_sessions_for_date(
    records: Iterable[WorkSessionRecord],
    target_date: str,
) -> list[WorkSessionRecord]:
    return [record for record in records if record.date == target_date]


def _coerce_date(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("date is required.")
    return text


def _coerce_non_negative_int(value: int, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")

    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc

    if number < 0:
        raise ValueError(f"{field_name} must be at least 0.")

    return number

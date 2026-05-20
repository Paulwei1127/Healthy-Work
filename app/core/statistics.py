"""Pure daily statistics calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.data.models import BreakRecord


@dataclass(frozen=True)
class DailyStatistics:
    """Calculated statistics for one day."""

    date: str
    work_minutes: int
    break_minutes: int
    break_count: int
    water_ml: int
    average_work_session_minutes: float | None


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


def calculate_daily_statistics(
    date: str,
    work_minutes: int,
    break_records: Iterable[BreakRecord],
) -> DailyStatistics:
    """Calculate all user-facing statistics for one date."""

    normalized_date = _coerce_date(date)
    normalized_work_minutes = calculate_work_minutes(work_minutes)
    records = _records_for_date(break_records, normalized_date)
    break_count = calculate_break_count(records)

    return DailyStatistics(
        date=normalized_date,
        work_minutes=normalized_work_minutes,
        break_minutes=calculate_break_minutes(records),
        break_count=break_count,
        water_ml=calculate_water_ml(records),
        average_work_session_minutes=calculate_average_work_session_minutes(
            normalized_work_minutes,
            break_count,
        ),
    )


def _records_for_date(
    records: Iterable[BreakRecord],
    target_date: str,
) -> list[BreakRecord]:
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

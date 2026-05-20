"""Data models for local healthy work records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


def _coerce_int(value: Any, field_name: str, min_value: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")

    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc

    if min_value is not None and number < min_value:
        raise ValueError(f"{field_name} must be at least {min_value}.")

    return number


def _coerce_optional_float(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number or None.")

    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number or None.") from exc


def _required_string(value: Any, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} is required.")

    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required.")

    return text


def _optional_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class BreakRecord:
    """A single completed break record."""

    id: str
    date: str
    start_time: str
    end_time: str
    duration_minutes: int
    water_ml: int = 0
    note: str = ""

    def __post_init__(self) -> None:
        self.id = _required_string(self.id, "id")
        self.date = _required_string(self.date, "date")
        self.start_time = _required_string(self.start_time, "start_time")
        self.end_time = _required_string(self.end_time, "end_time")
        self.duration_minutes = _coerce_int(
            self.duration_minutes, "duration_minutes", min_value=0
        )
        self.water_ml = _coerce_int(self.water_ml, "water_ml", min_value=0)
        self.note = _optional_string(self.note)

    @classmethod
    def create(
        cls,
        start_time: datetime,
        end_time: datetime,
        duration_minutes: int,
        water_ml: int = 0,
        note: str = "",
    ) -> "BreakRecord":
        return cls(
            id=str(uuid4()),
            date=start_time.date().isoformat(),
            start_time=start_time.isoformat(timespec="seconds"),
            end_time=end_time.isoformat(timespec="seconds"),
            duration_minutes=duration_minutes,
            water_ml=water_ml,
            note=note,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BreakRecord":
        if not isinstance(data, dict):
            raise ValueError("BreakRecord data must be a dictionary.")

        return cls(
            id=data.get("id"),
            date=data.get("date"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            duration_minutes=data.get("duration_minutes", 0),
            water_ml=data.get("water_ml", 0),
            note=data.get("note", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration_minutes,
            "water_ml": self.water_ml,
            "note": self.note,
        }


@dataclass
class DailySummary:
    """A saved end-of-day summary."""

    date: str
    work_minutes: int
    break_minutes: int
    break_count: int
    water_ml: int
    average_work_session_minutes: float | None
    health_score: int
    suggestions: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_iso_now)

    def __post_init__(self) -> None:
        self.date = _required_string(self.date, "date")
        self.work_minutes = _coerce_int(self.work_minutes, "work_minutes", min_value=0)
        self.break_minutes = _coerce_int(
            self.break_minutes, "break_minutes", min_value=0
        )
        self.break_count = _coerce_int(self.break_count, "break_count", min_value=0)
        self.water_ml = _coerce_int(self.water_ml, "water_ml", min_value=0)
        self.average_work_session_minutes = _coerce_optional_float(
            self.average_work_session_minutes, "average_work_session_minutes"
        )
        self.health_score = _coerce_int(self.health_score, "health_score", min_value=0)
        if self.health_score > 100:
            raise ValueError("health_score must be between 0 and 100.")

        if not isinstance(self.suggestions, list):
            raise ValueError("suggestions must be a list.")
        self.suggestions = [str(item).strip() for item in self.suggestions if str(item).strip()]
        self.created_at = _required_string(self.created_at, "created_at")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailySummary":
        if not isinstance(data, dict):
            raise ValueError("DailySummary data must be a dictionary.")

        return cls(
            date=data.get("date"),
            work_minutes=data.get("work_minutes", 0),
            break_minutes=data.get("break_minutes", 0),
            break_count=data.get("break_count", 0),
            water_ml=data.get("water_ml", 0),
            average_work_session_minutes=data.get("average_work_session_minutes"),
            health_score=data.get("health_score", 0),
            suggestions=data.get("suggestions", []),
            created_at=data.get("created_at", _iso_now()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "work_minutes": self.work_minutes,
            "break_minutes": self.break_minutes,
            "break_count": self.break_count,
            "water_ml": self.water_ml,
            "average_work_session_minutes": self.average_work_session_minutes,
            "health_score": self.health_score,
            "suggestions": list(self.suggestions),
            "created_at": self.created_at,
        }


@dataclass
class AppSettings:
    """User-adjustable app settings."""

    break_interval_minutes: int = 30

    def __post_init__(self) -> None:
        self.break_interval_minutes = _coerce_int(
            self.break_interval_minutes, "break_interval_minutes", min_value=1
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AppSettings":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("AppSettings data must be a dictionary.")

        return cls(
            break_interval_minutes=data.get("break_interval_minutes", 30),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "break_interval_minutes": self.break_interval_minutes,
        }

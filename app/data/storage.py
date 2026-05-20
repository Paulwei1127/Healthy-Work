"""JSON storage for local daily records."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import AppSettings, BreakRecord, DailySummary


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORAGE_PATH = PROJECT_ROOT / "data" / "daily_records.json"


class StorageError(RuntimeError):
    """Raised when the local records file cannot be read or written."""


def create_empty_data() -> dict[str, Any]:
    return {
        "settings": AppSettings().to_dict(),
        "break_records": [],
        "daily_summaries": [],
        "daily_work_minutes": {},
    }


class JsonStorage:
    """Small repository for the MVP JSON data file."""

    def __init__(self, file_path: str | Path = DEFAULT_STORAGE_PATH) -> None:
        self.file_path = Path(file_path)

    def initialize(self) -> dict[str, Any]:
        return self.load_data()

    def load_data(self) -> dict[str, Any]:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.file_path.exists():
            data = create_empty_data()
            self.save_data(data)
            return data

        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                raw_data = json.load(file)
        except json.JSONDecodeError:
            return self._backup_and_reset()
        except OSError as exc:
            raise StorageError(f"Unable to read storage file: {self.file_path}") from exc

        try:
            return self._normalize_data(raw_data)
        except (TypeError, ValueError):
            return self._backup_and_reset()

    def save_data(self, data: dict[str, Any]) -> None:
        normalized_data = self._normalize_data(data)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.file_path.with_suffix(self.file_path.suffix + ".tmp")

        try:
            with temp_path.open("w", encoding="utf-8") as file:
                json.dump(normalized_data, file, ensure_ascii=False, indent=2)
                file.write("\n")
            temp_path.replace(self.file_path)
        except OSError as exc:
            raise StorageError(f"Unable to write storage file: {self.file_path}") from exc

    def load_settings(self) -> AppSettings:
        data = self.load_data()
        return AppSettings.from_dict(data.get("settings"))

    def save_settings(self, settings: AppSettings) -> None:
        data = self.load_data()
        data["settings"] = settings.to_dict()
        self.save_data(data)

    def list_break_records(self, record_date: str | None = None) -> list[BreakRecord]:
        data = self.load_data()
        records = [BreakRecord.from_dict(item) for item in data["break_records"]]

        if record_date is None:
            return records

        return [record for record in records if record.date == record_date]

    def add_break_record(self, record: BreakRecord) -> None:
        data = self.load_data()
        data["break_records"].append(record.to_dict())
        self.save_data(data)

    def list_daily_summaries(self) -> list[DailySummary]:
        data = self.load_data()
        return [DailySummary.from_dict(item) for item in data["daily_summaries"]]

    def get_daily_summary(self, summary_date: str) -> DailySummary | None:
        for summary in self.list_daily_summaries():
            if summary.date == summary_date:
                return summary
        return None

    def save_daily_summary(self, summary: DailySummary) -> None:
        data = self.load_data()
        summaries = [
            item
            for item in data["daily_summaries"]
            if item.get("date") != summary.date
        ]
        summaries.append(summary.to_dict())
        data["daily_summaries"] = summaries
        self.save_data(data)

    def get_work_minutes(self, work_date: str) -> int:
        data = self.load_data()
        return int(data["daily_work_minutes"].get(work_date, 0))

    def set_work_minutes(self, work_date: str, minutes: int) -> None:
        if minutes < 0:
            raise ValueError("minutes must be at least 0.")

        data = self.load_data()
        data["daily_work_minutes"][str(work_date)] = int(minutes)
        self.save_data(data)

    def increment_work_minutes(self, work_date: str, minutes: int) -> int:
        if minutes < 0:
            raise ValueError("minutes must be at least 0.")

        total_minutes = self.get_work_minutes(work_date) + int(minutes)
        self.set_work_minutes(work_date, total_minutes)
        return total_minutes

    def _backup_and_reset(self) -> dict[str, Any]:
        if self.file_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = self.file_path.with_name(
                f"{self.file_path.stem}.invalid-{timestamp}{self.file_path.suffix}"
            )
            try:
                shutil.copy2(self.file_path, backup_path)
            except OSError as exc:
                raise StorageError(
                    f"Unable to back up invalid storage file: {self.file_path}"
                ) from exc

        data = create_empty_data()
        self.save_data(data)
        return data

    def _normalize_data(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("Storage data must be a dictionary.")

        settings = AppSettings.from_dict(data.get("settings")).to_dict()
        break_records = self._normalize_break_records(data.get("break_records", []))
        daily_summaries = self._normalize_daily_summaries(
            data.get("daily_summaries", [])
        )
        daily_work_minutes = self._normalize_daily_work_minutes(
            data.get("daily_work_minutes", {})
        )

        return {
            "settings": settings,
            "break_records": break_records,
            "daily_summaries": daily_summaries,
            "daily_work_minutes": daily_work_minutes,
        }

    def _normalize_break_records(self, records: Any) -> list[dict[str, Any]]:
        if not isinstance(records, list):
            raise ValueError("break_records must be a list.")

        return [BreakRecord.from_dict(record).to_dict() for record in records]

    def _normalize_daily_summaries(self, summaries: Any) -> list[dict[str, Any]]:
        if not isinstance(summaries, list):
            raise ValueError("daily_summaries must be a list.")

        return [DailySummary.from_dict(summary).to_dict() for summary in summaries]

    def _normalize_daily_work_minutes(self, work_minutes: Any) -> dict[str, int]:
        if not isinstance(work_minutes, dict):
            raise ValueError("daily_work_minutes must be a dictionary.")

        normalized: dict[str, int] = {}
        for work_date, minutes in work_minutes.items():
            if isinstance(minutes, bool):
                raise ValueError("work minutes must be an integer.")
            normalized_minutes = int(minutes)
            if normalized_minutes < 0:
                raise ValueError("work minutes must be at least 0.")
            normalized[str(work_date)] = normalized_minutes

        return normalized

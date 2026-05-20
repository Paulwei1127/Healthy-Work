"""End-of-day report dialog."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.data.models import DailySummary


REPORT_DIALOG_WIDTH = 420
REPORT_DIALOG_HEIGHT = 460


class ReportDialog:
    """Display a saved DailySummary in a compact modal window."""

    def __init__(self, parent: tk.Tk | tk.Toplevel, summary: DailySummary) -> None:
        self.parent = parent
        self.summary = summary
        self.dialog: tk.Toplevel | None = None

    def show(self) -> None:
        dialog = tk.Toplevel(self.parent)
        self.dialog = dialog
        dialog.title("今日健康工作報告")
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()

        body = ttk.Frame(dialog, padding=14)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            body,
            text="今日健康工作報告",
            font=("Microsoft JhengHei UI", 12, "bold"),
        ).pack(anchor=tk.W)

        report_text = tk.Text(
            body,
            height=19,
            width=48,
            wrap=tk.WORD,
            relief=tk.FLAT,
            borderwidth=0,
        )
        report_text.pack(fill=tk.BOTH, expand=True, pady=(12, 10))
        report_text.insert("1.0", format_daily_summary_report(self.summary))
        report_text.configure(state=tk.DISABLED)

        ttk.Button(body, text="關閉", command=self._close).pack(fill=tk.X)

        dialog.protocol("WM_DELETE_WINDOW", self._close)
        self._position_dialog(dialog)

    def _position_dialog(self, dialog: tk.Toplevel) -> None:
        self.parent.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        x = parent_x + max(0, (parent_width - REPORT_DIALOG_WIDTH) // 2)
        y = parent_y + max(0, (parent_height - REPORT_DIALOG_HEIGHT) // 2)
        dialog.geometry(f"{REPORT_DIALOG_WIDTH}x{REPORT_DIALOG_HEIGHT}+{x}+{y}")

    def _close(self) -> None:
        if self.dialog is None:
            return
        self.dialog.grab_release()
        self.dialog.destroy()
        self.dialog = None


def format_daily_summary_report(summary: DailySummary) -> str:
    average_work = (
        "N/A"
        if summary.average_work_session_minutes is None
        else f"{summary.average_work_session_minutes:.0f} 分鐘"
    )
    suggestions = "\n".join(f"- {suggestion}" for suggestion in summary.suggestions)

    return "\n".join(
        [
            f"日期：{summary.date}",
            f"工作總時間：{_format_minutes(summary.work_minutes)}",
            f"休息總時間：{_format_minutes(summary.break_minutes)}",
            f"休息次數：{summary.break_count} 次",
            f"平均每次工作時長：{average_work}",
            f"喝水總量：{summary.water_ml} ml",
            f"健康度評分：{summary.health_score} / 100",
            "",
            "建議：",
            suggestions if suggestions else "- 今天沒有可用建議。",
        ]
    )


def _format_minutes(minutes: int) -> str:
    normalized_minutes = max(0, int(minutes))
    hours, remaining_minutes = divmod(normalized_minutes, 60)

    if hours:
        return f"{hours} 小時 {remaining_minutes} 分鐘"
    return f"{remaining_minutes} 分鐘"

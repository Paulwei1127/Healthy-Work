"""Tkinter main window for the MVP desktop widget."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Callable

from app.core.scoring import create_daily_summary
from app.core.statistics import calculate_daily_statistics
from app.core.timer import (
    CompletedBreak,
    TimerSnapshot,
    TimerState,
    TimerStateError,
    WorkTimer,
)
from app.data.models import BreakRecord
from app.data.storage import JsonStorage, StorageError
from app.ui.report_dialog import ReportDialog


WINDOW_WIDTH = 360
WINDOW_HEIGHT = 580
WINDOW_MARGIN_X = 18
WINDOW_MARGIN_Y = 64
TICK_INTERVAL_MS = 1000

BREAK_DIALOG_WIDTH = 320
BREAK_DIALOG_HEIGHT = 250


STATE_LABELS = {
    TimerState.IDLE: "Idle（尚未開始）",
    TimerState.WORKING: "Working（工作中）",
    TimerState.PAUSED: "Paused（已暫停）",
    TimerState.REMINDER: "Reminder（提醒中）",
    TimerState.BREAKING: "Breaking（休息中）",
    TimerState.DAY_ENDED: "DayEnded（今日已結束）",
}


class MainWindow:
    """Small Tkinter window connected to WorkTimer and JsonStorage."""

    def __init__(
        self,
        root: tk.Tk | None = None,
        timer: WorkTimer | None = None,
        storage: JsonStorage | None = None,
    ) -> None:
        self.root = root or tk.Tk()
        self.storage = storage or JsonStorage()
        self.today = date.today().isoformat()
        self._startup_storage_message: str | None = None
        self._session_break_records, initial_work_minutes = self._load_today_data()

        self.timer = timer or WorkTimer(initial_work_seconds=initial_work_minutes * 60)
        if timer is not None:
            self.timer.reset_day(initial_work_seconds=initial_work_minutes * 60)

        self._after_id: str | None = None
        self._pending_break: CompletedBreak | None = None
        self._break_dialog: tk.Toplevel | None = None

        self.interval_var = tk.StringVar(
            value=str(self.timer.break_interval_minutes)
        )
        self.status_var = tk.StringVar()
        self.time_caption_var = tk.StringVar()
        self.time_var = tk.StringVar()
        self.work_total_var = tk.StringVar()
        self.break_total_var = tk.StringVar()
        self.break_count_var = tk.StringVar()
        self.water_total_var = tk.StringVar()
        self.current_break_var = tk.StringVar()
        self.last_break_var = tk.StringVar()

        self._configure_window()
        self._build_widgets()
        self._render(self.timer.snapshot())
        self._schedule_tick()
        self.root.after_idle(self._show_startup_storage_message)

    def run(self) -> None:
        self.root.mainloop()

    def _load_today_data(self) -> tuple[list[BreakRecord], int]:
        try:
            records = self.storage.list_break_records(self.today)
            work_minutes = self.storage.get_work_minutes(self.today)
        except (StorageError, ValueError) as exc:
            self._startup_storage_message = (
                "讀取今日資料時發生問題，已先用 0 初始化畫面。"
                f"\n原因：{exc}"
            )
            return [], 0

        recovery_message = self.storage.consume_recovery_message()
        if recovery_message:
            self._startup_storage_message = recovery_message

        return records, work_minutes

    def _show_startup_storage_message(self) -> None:
        if not self._startup_storage_message:
            return

        messagebox.showwarning(
            "資料讀取提醒",
            self._startup_storage_message,
            parent=self.root,
        )
        self._startup_storage_message = None

    def _configure_window(self) -> None:
        self.root.title("健康工作小工具")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("Microsoft JhengHei UI", 12, "bold"))
        style.configure("Timer.TLabel", font=("Consolas", 28, "bold"))
        style.configure("Status.TLabel", foreground="#2f5d50")

        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, screen_width - WINDOW_WIDTH - WINDOW_MARGIN_X)
        y = max(0, screen_height - WINDOW_HEIGHT - WINDOW_MARGIN_Y)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

    def _build_widgets(self) -> None:
        container = ttk.Frame(self.root, padding=14)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="健康工作小工具", style="Title.TLabel").pack(
            anchor=tk.W
        )

        interval_row = ttk.Frame(container)
        interval_row.pack(fill=tk.X, pady=(14, 8))
        ttk.Label(interval_row, text="休息間隔").pack(side=tk.LEFT)
        ttk.Entry(
            interval_row,
            textvariable=self.interval_var,
            width=7,
            justify=tk.RIGHT,
        ).pack(side=tk.LEFT, padx=(8, 4))
        ttk.Label(interval_row, text="分鐘").pack(side=tk.LEFT)

        timer_panel = ttk.Frame(container, padding=(0, 8))
        timer_panel.pack(fill=tk.X)
        ttk.Label(timer_panel, textvariable=self.time_caption_var).pack(anchor=tk.W)
        ttk.Label(timer_panel, textvariable=self.time_var, style="Timer.TLabel").pack(
            anchor=tk.CENTER,
            pady=(2, 4),
        )
        ttk.Label(
            timer_panel,
            textvariable=self.status_var,
            style="Status.TLabel",
        ).pack(anchor=tk.CENTER)

        controls = ttk.Frame(container)
        controls.pack(fill=tk.X, pady=(12, 4))
        controls.columnconfigure((0, 1), weight=1, uniform="controls")

        self.start_button = ttk.Button(
            controls,
            text="開始工作",
            command=self._on_start_work,
        )
        self.pause_button = ttk.Button(
            controls,
            text="暫停",
            command=lambda: self._run_timer_action(self.timer.pause),
        )
        self.resume_button = ttk.Button(
            controls,
            text="繼續",
            command=lambda: self._run_timer_action(self.timer.resume_work),
        )
        self.restart_button = ttk.Button(
            controls,
            text="重新開始",
            command=self._on_restart_countdown,
        )
        self.snooze_button = ttk.Button(
            controls,
            text="延後 5 分鐘",
            command=lambda: self._run_timer_action(self.timer.snooze),
        )
        self.start_break_button = ttk.Button(
            controls,
            text="開始休息",
            command=lambda: self._run_timer_action(self.timer.start_break),
        )
        self.return_work_button = ttk.Button(
            controls,
            text="回到工作",
            command=self._on_return_to_work,
        )
        self.end_day_button = ttk.Button(
            controls,
            text="結束今天",
            command=self._on_end_day,
        )

        buttons = [
            self.start_button,
            self.pause_button,
            self.resume_button,
            self.restart_button,
            self.snooze_button,
            self.start_break_button,
            self.return_work_button,
            self.end_day_button,
        ]
        for index, button in enumerate(buttons):
            button.grid(
                row=index // 2,
                column=index % 2,
                sticky=tk.EW,
                padx=4,
                pady=4,
            )

        stats_frame = ttk.LabelFrame(container, text="今日統計", padding=10)
        stats_frame.pack(fill=tk.X, pady=(14, 0))

        self._add_stat_row(stats_frame, "工作總時間", self.work_total_var, 0)
        self._add_stat_row(stats_frame, "休息總時間", self.break_total_var, 1)
        self._add_stat_row(stats_frame, "休息次數", self.break_count_var, 2)
        self._add_stat_row(stats_frame, "喝水總量", self.water_total_var, 3)
        self._add_stat_row(stats_frame, "目前休息", self.current_break_var, 4)
        self._add_stat_row(stats_frame, "上次休息", self.last_break_var, 5)

    def _add_stat_row(
        self,
        parent: ttk.Frame,
        label: str,
        value_var: tk.StringVar,
        row: int,
    ) -> None:
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Label(parent, textvariable=value_var).grid(
            row=row,
            column=1,
            sticky=tk.E,
            pady=2,
        )

    def _schedule_tick(self) -> None:
        self._after_id = self.root.after(TICK_INTERVAL_MS, self._on_tick)

    def _on_tick(self) -> None:
        snapshot = self.timer.tick(1)
        self._render(snapshot)
        self._schedule_tick()

    def _on_start_work(self) -> None:
        interval_minutes = self._read_interval_minutes()
        if interval_minutes is None:
            return

        self._run_timer_action(lambda: self.timer.start_work(interval_minutes))

    def _on_restart_countdown(self) -> None:
        interval_minutes = self._read_interval_minutes()
        if interval_minutes is None:
            return

        self._run_timer_action(lambda: self.timer.restart_countdown(interval_minutes))

    def _on_return_to_work(self) -> None:
        try:
            completed_break = self.timer.return_to_work(auto_start_next_round=False)
        except TimerStateError as exc:
            messagebox.showwarning("無法執行", str(exc), parent=self.root)
            return

        self._pending_break = completed_break
        self._render(self.timer.snapshot())
        self._show_break_record_dialog()

    def _run_timer_action(self, action: Callable[[], object]) -> None:
        try:
            action()
        except (TimerStateError, ValueError) as exc:
            messagebox.showwarning("無法執行", str(exc), parent=self.root)
        self._render(self.timer.snapshot())

    def _on_end_day(self) -> None:
        snapshot = self.timer.snapshot()
        if snapshot.state == TimerState.BREAKING:
            messagebox.showinfo(
                "尚在休息中",
                "請先按「回到工作」並儲存休息紀錄，再結束今天。",
                parent=self.root,
            )
            return

        if self._pending_break is not None:
            messagebox.showinfo(
                "休息紀錄尚未儲存",
                "請先儲存目前的休息紀錄，再結束今天。",
                parent=self.root,
            )
            self._show_break_record_dialog()
            return

        if self._break_dialog is not None and self._break_dialog.winfo_exists():
            self._break_dialog.lift()
            return

        try:
            statistics = calculate_daily_statistics(
                date=self.today,
                work_minutes=self.timer.snapshot().total_work_seconds // 60,
                break_records=self._session_break_records,
            )
            summary = create_daily_summary(statistics)
            self.storage.set_work_minutes(self.today, summary.work_minutes)
            self.storage.save_daily_summary(summary)
            self.timer.end_day()
        except (StorageError, TimerStateError, ValueError) as exc:
            messagebox.showerror("結束今天失敗", str(exc), parent=self.root)
            return

        self._render(self.timer.snapshot())
        ReportDialog(self.root, summary).show()

    def _show_break_record_dialog(self) -> None:
        if self._pending_break is None:
            return
        if self._break_dialog is not None and self._break_dialog.winfo_exists():
            self._break_dialog.lift()
            return

        dialog = tk.Toplevel(self.root)
        self._break_dialog = dialog
        dialog.title("休息紀錄")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        body = ttk.Frame(dialog, padding=14)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text="休息結束，請記錄這次休息。").pack(anchor=tk.W)
        ttk.Label(
            body,
            text=f"本次休息：{self._pending_break.duration_minutes} 分鐘",
        ).pack(anchor=tk.W, pady=(4, 12))

        water_var = tk.StringVar(value="0")
        water_row = ttk.Frame(body)
        water_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(water_row, text="喝水量").pack(side=tk.LEFT)
        water_entry = ttk.Entry(
            water_row,
            textvariable=water_var,
            width=10,
            justify=tk.RIGHT,
        )
        water_entry.pack(side=tk.LEFT, padx=(8, 4))
        ttk.Label(water_row, text="ml").pack(side=tk.LEFT)

        ttk.Label(body, text="備註（可選）").pack(anchor=tk.W)
        note_text = tk.Text(body, height=3, width=32, wrap=tk.WORD)
        note_text.pack(fill=tk.X, pady=(4, 10))

        save_button = ttk.Button(
            body,
            text="儲存休息紀錄",
            command=lambda: self._save_break_record_from_dialog(
                dialog=dialog,
                water_value=water_var.get(),
                note=note_text.get("1.0", tk.END).strip(),
            ),
        )
        save_button.pack(fill=tk.X)

        dialog.protocol("WM_DELETE_WINDOW", self._on_break_dialog_close_attempt)
        self._position_break_dialog(dialog)
        water_entry.focus_set()

    def _position_break_dialog(self, dialog: tk.Toplevel) -> None:
        self.root.update_idletasks()
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        x = root_x + max(0, (root_width - BREAK_DIALOG_WIDTH) // 2)
        y = root_y + max(0, (root_height - BREAK_DIALOG_HEIGHT) // 2)
        dialog.geometry(f"{BREAK_DIALOG_WIDTH}x{BREAK_DIALOG_HEIGHT}+{x}+{y}")

    def _on_break_dialog_close_attempt(self) -> None:
        messagebox.showinfo(
            "請先儲存",
            "請先儲存休息紀錄，再回到下一輪工作。",
            parent=self._break_dialog or self.root,
        )

    def _save_break_record_from_dialog(
        self,
        dialog: tk.Toplevel,
        water_value: str,
        note: str,
    ) -> None:
        water_ml = self._parse_water_ml(water_value, parent=dialog)
        if water_ml is None:
            return

        break_record = self._build_break_record(water_ml=water_ml, note=note)

        try:
            self.storage.add_break_record(break_record)
        except (StorageError, ValueError) as exc:
            messagebox.showerror("儲存失敗", str(exc), parent=dialog)
            return

        self._session_break_records.append(break_record)
        self._pending_break = None
        self._break_dialog = None
        dialog.grab_release()
        dialog.destroy()
        self._run_timer_action(self.timer.resume_work)

    def _read_interval_minutes(self) -> int | None:
        raw_value = self.interval_var.get().strip()
        if not raw_value:
            messagebox.showerror("輸入錯誤", "休息間隔不可空白。", parent=self.root)
            return None

        try:
            interval_minutes = int(raw_value)
        except ValueError:
            messagebox.showerror(
                "輸入錯誤",
                "休息間隔必須是正整數。",
                parent=self.root,
            )
            return None

        if interval_minutes < 1:
            messagebox.showerror(
                "輸入錯誤",
                "休息間隔不可小於 1 分鐘。",
                parent=self.root,
            )
            return None

        return interval_minutes

    def _parse_water_ml(self, raw_value: str, parent: tk.Misc) -> int | None:
        cleaned_value = raw_value.strip()
        if not cleaned_value:
            return 0

        try:
            water_ml = int(cleaned_value)
        except ValueError:
            messagebox.showerror(
                "輸入錯誤",
                "喝水量必須是 0 或正整數。",
                parent=parent,
            )
            return None

        if water_ml < 0:
            messagebox.showerror(
                "輸入錯誤",
                "喝水量不可小於 0。",
                parent=parent,
            )
            return None

        return water_ml

    def _build_break_record(self, water_ml: int, note: str) -> BreakRecord:
        completed_break = self._pending_break
        if completed_break is None:
            raise TimerStateError("Cannot build a break record without a completed break.")

        return BreakRecord.create(
            start_time=completed_break.start_time,
            end_time=completed_break.end_time,
            duration_minutes=completed_break.duration_minutes,
            water_ml=water_ml,
            note=note,
        )

    def _render(self, snapshot: TimerSnapshot) -> None:
        state = snapshot.state
        self.status_var.set(f"狀態：{STATE_LABELS[state]}")

        if state == TimerState.BREAKING:
            self.time_caption_var.set("休息已進行")
            self.time_var.set(_format_seconds(snapshot.break_elapsed_seconds))
        elif state == TimerState.REMINDER:
            self.time_caption_var.set("提醒時間到")
            self.time_var.set("00:00")
        else:
            self.time_caption_var.set("剩餘倒數")
            self.time_var.set(_format_seconds(snapshot.remaining_seconds))

        self._render_statistics(snapshot)
        self.current_break_var.set(_format_seconds(snapshot.break_elapsed_seconds))
        self.last_break_var.set(_format_last_break(snapshot))
        self._update_button_states(state)

    def _render_statistics(self, snapshot: TimerSnapshot) -> None:
        stats = calculate_daily_statistics(
            date=self.today,
            work_minutes=snapshot.total_work_seconds // 60,
            break_records=self._session_break_records,
        )
        self.work_total_var.set(_format_minutes(stats.work_minutes))
        self.break_total_var.set(_format_minutes(stats.break_minutes))
        self.break_count_var.set(f"{stats.break_count} 次")
        self.water_total_var.set(f"{stats.water_ml} ml")

    def _update_button_states(self, state: TimerState) -> None:
        pending_break = self._pending_break is not None
        self.start_button.state(["!disabled"] if state == TimerState.IDLE else ["disabled"])
        self.pause_button.state(["!disabled"] if state == TimerState.WORKING else ["disabled"])
        self.resume_button.state(
            ["!disabled"] if state == TimerState.PAUSED and not pending_break else ["disabled"]
        )
        self.restart_button.state(
            ["!disabled"]
            if state
            in {
                TimerState.IDLE,
                TimerState.WORKING,
                TimerState.PAUSED,
                TimerState.REMINDER,
            }
            and not pending_break
            else ["disabled"]
        )
        self.snooze_button.state(
            ["!disabled"] if state == TimerState.REMINDER else ["disabled"]
        )
        self.start_break_button.state(
            ["!disabled"] if state == TimerState.REMINDER else ["disabled"]
        )
        self.return_work_button.state(
            ["!disabled"] if state == TimerState.BREAKING else ["disabled"]
        )
        self.end_day_button.state(
            ["disabled"] if state == TimerState.DAY_ENDED else ["!disabled"]
        )

    def _on_close(self) -> None:
        if self._break_dialog is not None and self._break_dialog.winfo_exists():
            self._break_dialog.grab_release()
            self._break_dialog.destroy()
            self._break_dialog = None
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.root.destroy()


def _format_seconds(seconds: int) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
    return f"{minutes:02d}:{remaining_seconds:02d}"


def _format_last_break(snapshot: TimerSnapshot) -> str:
    if snapshot.last_completed_break is None:
        return "無"
    return f"{snapshot.last_completed_break.duration_minutes} 分鐘"


def _format_minutes(minutes: int) -> str:
    normalized_minutes = max(0, int(minutes))
    hours, remaining_minutes = divmod(normalized_minutes, 60)

    if hours:
        return f"{hours} 小時 {remaining_minutes} 分鐘"
    return f"{remaining_minutes} 分鐘"

"""Tkinter main window for the MVP desktop widget."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app.core.timer import TimerSnapshot, TimerState, TimerStateError, WorkTimer


WINDOW_WIDTH = 340
WINDOW_HEIGHT = 500
WINDOW_MARGIN_X = 18
WINDOW_MARGIN_Y = 80
TICK_INTERVAL_MS = 1000


STATE_LABELS = {
    TimerState.IDLE: "Idle（尚未開始）",
    TimerState.WORKING: "Working（工作中）",
    TimerState.PAUSED: "Paused（已暫停）",
    TimerState.REMINDER: "Reminder（提醒中）",
    TimerState.BREAKING: "Breaking（休息中）",
    TimerState.DAY_ENDED: "DayEnded（今日已結束）",
}


class MainWindow:
    """Small Tkinter window connected to the pure WorkTimer state machine."""

    def __init__(
        self,
        root: tk.Tk | None = None,
        timer: WorkTimer | None = None,
    ) -> None:
        self.root = root or tk.Tk()
        self.timer = timer or WorkTimer()
        self._after_id: str | None = None

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

    def run(self) -> None:
        self.root.mainloop()

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
        interval_entry = ttk.Entry(
            interval_row,
            textvariable=self.interval_var,
            width=7,
            justify=tk.RIGHT,
        )
        interval_entry.pack(side=tk.LEFT, padx=(8, 4))
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

        buttons = [
            self.start_button,
            self.pause_button,
            self.resume_button,
            self.restart_button,
            self.snooze_button,
            self.start_break_button,
            self.return_work_button,
        ]
        for index, button in enumerate(buttons):
            button.grid(
                row=index // 2,
                column=index % 2,
                sticky=tk.EW,
                padx=4,
                pady=4,
            )

        stats_frame = ttk.LabelFrame(container, text="今日統計（暫存）", padding=10)
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
        self._run_timer_action(
            lambda: self.timer.return_to_work(auto_start_next_round=True)
        )

    def _run_timer_action(self, action) -> None:
        try:
            action()
        except (TimerStateError, ValueError) as exc:
            messagebox.showwarning("無法執行", str(exc), parent=self.root)
        self._render(self.timer.snapshot())

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

        self.work_total_var.set(_format_seconds(snapshot.total_work_seconds))
        self.break_total_var.set("待串接資料儲存")
        self.break_count_var.set("待串接資料儲存")
        self.water_total_var.set("待串接資料儲存")
        self.current_break_var.set(_format_seconds(snapshot.break_elapsed_seconds))
        self.last_break_var.set(_format_last_break(snapshot))
        self._update_button_states(state)

    def _update_button_states(self, state: TimerState) -> None:
        self.start_button.state(["!disabled"] if state == TimerState.IDLE else ["disabled"])
        self.pause_button.state(["!disabled"] if state == TimerState.WORKING else ["disabled"])
        self.resume_button.state(["!disabled"] if state == TimerState.PAUSED else ["disabled"])
        self.restart_button.state(
            ["!disabled"]
            if state
            in {
                TimerState.IDLE,
                TimerState.WORKING,
                TimerState.PAUSED,
                TimerState.REMINDER,
            }
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

    def _on_close(self) -> None:
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

"""PyQt5 main window for the desktop widget."""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timedelta
from typing import Callable

try:
    from PyQt5.QtCore import QSize, Qt, QTimer
    from PyQt5.QtGui import QFont, QFontDatabase, QIntValidator, QMovie
    from PyQt5.QtWidgets import (
        QApplication,
        QDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - depends on local installation.
    raise RuntimeError(
        "PyQt5 is required for the current UI. "
        "Install it with: pip install -r requirements.txt"
    ) from exc

from app.core.scoring import create_daily_summary
from app.core.statistics import calculate_daily_statistics
from app.core.timer import (
    CompletedBreak,
    TimerSnapshot,
    TimerState,
    TimerStateError,
    WorkTimer,
)
from app.data.models import AppSettings, BreakRecord, WorkSessionRecord
from app.data.storage import JsonStorage, StorageError
from app.ui.animation import (
    LOTTIE_WEB_PLAYER_PATH,
    LottieGifAnimationWidget,
    get_resource_path,
)
from app.ui.reminder_dialog import ReminderAction, ReminderDialog
from app.ui.report_dialog import ReportDialog


WINDOW_WIDTH = 440
WINDOW_HEIGHT = 660
WINDOW_MIN_WIDTH = 380
WINDOW_MIN_HEIGHT = 520
WINDOW_MARGIN_X = 18
WINDOW_MARGIN_Y = 64
TICK_INTERVAL_MS = 1000

BREAK_DIALOG_WIDTH = 400
BREAK_DIALOG_HEIGHT = 360
ANIMATION_BOX_SIZE = QSize(150, 150)

BASE_FONT_POINT_SIZE = 11
FONT_CANDIDATES = (
    "Microsoft JhengHei UI",
    "Microsoft JhengHei",
    "Yu Gothic UI",
    "Segoe UI",
)


STATE_LABELS = {
    TimerState.IDLE: "尚未開始",
    TimerState.WORKING: "工作中",
    TimerState.PAUSED: "已暫停",
    TimerState.REMINDER: "提醒時間到",
    TimerState.BREAKING: "休息中",
    TimerState.DAY_ENDED: "今日已結束",
}


STATE_COLORS = {
    TimerState.IDLE: ("#6b7280", "#f3f4f6"),
    TimerState.WORKING: ("#166534", "#dcfce7"),
    TimerState.PAUSED: ("#92400e", "#fef3c7"),
    TimerState.REMINDER: ("#9f1239", "#ffe4e6"),
    TimerState.BREAKING: ("#075985", "#e0f2fe"),
    TimerState.DAY_ENDED: ("#5b21b6", "#ede9fe"),
}


TIMER_STATE_TO_GIF = {
    TimerState.IDLE: "gif/paws animation.gif",
    TimerState.WORKING: "gif/rolling cat animation.gif",
    TimerState.PAUSED: "gif/Loading Cat.gif",
    TimerState.REMINDER: "gif/Le Petit Chat _Cat_ Noir.gif",
    TimerState.BREAKING: "gif/Cat playing animation.gif",
    TimerState.DAY_ENDED: "gif/Cat is sleeping and rolling.gif",
}


TIMER_STATE_TO_LOTTIE = {
    TimerState.IDLE: "gif/json/paws animation.json",
    TimerState.WORKING: "gif/json/rolling cat animation.json",
    TimerState.PAUSED: "gif/json/Loading Cat.json",
    TimerState.REMINDER: "gif/json/Le Petit Chat _Cat_ Noir.json",
    TimerState.BREAKING: "gif/json/Cat playing animation.json",
    TimerState.DAY_ENDED: "gif/json/Cat is sleeping and rolling.json",
}


_HIGH_DPI_CONFIGURED = False


def _configure_high_dpi() -> None:
    """Enable PyQt5 high-DPI behavior before the QApplication is created."""
    global _HIGH_DPI_CONFIGURED
    if _HIGH_DPI_CONFIGURED:
        return

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    if QApplication.instance() is None:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    _HIGH_DPI_CONFIGURED = True


def _pick_font_family() -> str:
    available_families = set(QFontDatabase().families())
    for family in FONT_CANDIDATES:
        if family in available_families:
            return family
    return "Segoe UI"


class MainWindow:
    """Small PyQt5 window connected to WorkTimer and JsonStorage."""

    def __init__(
        self,
        timer: WorkTimer | None = None,
        storage: JsonStorage | None = None,
        date_provider: Callable[[], date] | None = None,
    ) -> None:
        _configure_high_dpi()
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.font_family = _pick_font_family()
        self.app.setFont(QFont(self.font_family, BASE_FONT_POINT_SIZE))
        self.storage = storage or JsonStorage()
        self._date_provider = date_provider or date.today
        self.today = self._current_date()
        self._startup_storage_message: str | None = None
        (
            self._session_break_records,
            self._session_work_records,
            initial_work_minutes,
            stored_interval_minutes,
        ) = self._load_startup_data()

        self.timer = timer or WorkTimer(
            break_interval_minutes=stored_interval_minutes,
            initial_work_seconds=initial_work_minutes * 60,
        )
        if timer is not None:
            self.timer.reset_day(
                break_interval_minutes=stored_interval_minutes,
                initial_work_seconds=initial_work_minutes * 60,
            )

        self._pending_break: CompletedBreak | None = None
        self._last_tick_monotonic = time.monotonic()
        self._last_saved_work_date = self.today
        self._last_saved_work_minutes = initial_work_minutes
        self._reminder_prompted_for_current_round = False
        self._reminder_dialog_open = False
        self._date_rollover_pending = False
        self._last_valid_interval_minutes = self.timer.break_interval_minutes
        self._active_work_session_start_time: datetime | None = None
        self._active_work_session_seconds = 0
        self._state_animation_movie: QMovie | None = None
        self._state_animation_state: TimerState | None = None
        self._state_animation_mode: str | None = None

        self.window = QMainWindow()
        self.window.setWindowTitle("健康工作小工具")
        self.window.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.window.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.window.closeEvent = self._on_window_close  # type: ignore[method-assign]
        self._apply_styles()
        self._build_widgets()
        self._position_bottom_right()

        self.qt_timer = QTimer(self.window)
        self.qt_timer.setInterval(TICK_INTERVAL_MS)
        self.qt_timer.timeout.connect(self._on_tick)

        self._render(self.timer.snapshot())
        QTimer.singleShot(0, self._show_startup_storage_message)

    def run(self) -> None:
        self.window.show()
        self.qt_timer.start()
        self.app.exec_()

    def _current_date(self) -> str:
        return self._date_provider().isoformat()

    def _load_startup_data(self) -> tuple[list[BreakRecord], list[WorkSessionRecord], int, int]:
        settings_interval = AppSettings().break_interval_minutes
        try:
            settings_interval = self.storage.load_settings().break_interval_minutes
            records = self.storage.list_break_records(self.today)
            work_records = self.storage.list_work_session_records(self.today)
            work_minutes = self.storage.get_work_minutes(self.today)
        except (StorageError, ValueError) as exc:
            self._startup_storage_message = (
                "讀取今日資料時發生問題，已先用 0 初始化畫面。\n"
                f"原因：{exc}"
            )
            return [], [], 0, settings_interval

        recovery_message = self.storage.consume_recovery_message()
        if recovery_message:
            self._startup_storage_message = recovery_message

        return records, work_records, work_minutes, settings_interval

    def _show_startup_storage_message(self) -> None:
        if not self._startup_storage_message:
            return

        QMessageBox.warning(
            self.window,
            "資料讀取提醒",
            self._startup_storage_message,
        )
        self._startup_storage_message = None

    def _apply_styles(self) -> None:
        self.window.setStyleSheet(
            """
            QMainWindow {
                background: #fff7fb;
            }
            QWidget {
                font-family: "Microsoft JhengHei UI", "Microsoft JhengHei", "Yu Gothic UI", "Segoe UI";
                font-size: 13px;
            }
            QWidget#Root {
                background: #fff7fb;
            }
            QScrollArea#MainScroll {
                background: #fff7fb;
                border: 0;
            }
            QScrollBar:vertical {
                background: #fff7fb;
                width: 9px;
                margin: 4px 0 4px 0;
            }
            QScrollBar::handle:vertical {
                background: #ead2df;
                border-radius: 4px;
                min-height: 28px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
            QFrame#Card {
                background: #ffffff;
                border: 1px solid #f0d9e7;
                border-radius: 14px;
            }
            QFrame#TimerCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ffffff, stop:1 #ecfeff);
                border: 1px solid #c7eef2;
                border-radius: 16px;
            }
            QWidget#AnimationContainer {
                background: transparent;
            }
            QLabel#AnimationLabel {
                background: transparent;
            }
            QLabel#Title {
                color: #2f2533;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#Subtitle {
                color: #7c6d80;
                font-size: 11px;
            }
            QLabel#SectionTitle {
                color: #8a5c75;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#TimerCaption {
                color: #7c6d80;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#TimerText {
                color: #263238;
                font-family: "Segoe UI", "Microsoft JhengHei UI", "Yu Gothic UI";
                font-size: 42px;
                font-weight: 900;
            }
            QLabel#StatusPill {
                border-radius: 13px;
                padding: 5px 14px;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#StatLabel {
                color: #8a5c75;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#StatValue {
                color: #2f2533;
                font-size: 15px;
                font-weight: 800;
            }
            QLineEdit {
                background: #ffffff;
                border: 1px solid #e6cadb;
                border-radius: 10px;
                min-height: 30px;
                padding: 5px 10px;
                color: #2f2533;
                font-size: 13px;
            }
            QTextEdit {
                background: #ffffff;
                border: 1px solid #e6cadb;
                border-radius: 12px;
                padding: 10px;
                color: #2f2533;
                font-size: 13px;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #e7cadb;
                border-radius: 12px;
                min-height: 34px;
                padding: 7px 10px;
                color: #3b2f3f;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #fff1f7;
                border-color: #f3a8c7;
            }
            QPushButton:disabled {
                color: #b3aab7;
                background: #f7f3f6;
                border-color: #eee4eb;
            }
            QPushButton#PrimaryButton {
                color: #ffffff;
                background: #ec6f9f;
                border-color: #ec6f9f;
            }
            QPushButton#PrimaryButton:hover {
                background: #df5d91;
                border-color: #df5d91;
            }
            QPushButton#PrimaryButton:disabled {
                color: #b8a9b2;
                background: #eadde4;
                border-color: #dcced6;
            }
            QPushButton#EndButton {
                color: #ffffff;
                background: #6aa6a1;
                border-color: #6aa6a1;
            }
            QPushButton#EndButton:hover {
                background: #57948f;
                border-color: #57948f;
            }
            """
        )

    def _build_widgets(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.window.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("MainScroll")
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root_layout.addWidget(scroll_area)

        content = QWidget()
        content.setObjectName("Root")
        scroll_area.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("健康工作小工具")
        title.setObjectName("Title")
        subtitle = QLabel("小小提醒你休息、喝水、照顧眼睛")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        settings_card = self._make_card()
        settings_layout = QHBoxLayout(settings_card)
        settings_card.setMinimumHeight(58)
        settings_layout.setContentsMargins(14, 10, 14, 10)
        settings_layout.setSpacing(10)
        settings_label = QLabel("每")
        self.interval_input = QLineEdit(str(self.timer.break_interval_minutes))
        self.interval_input.setValidator(QIntValidator(1, 999, self.interval_input))
        self.interval_input.setAlignment(Qt.AlignRight)
        self.interval_input.setFixedWidth(82)
        self.interval_input.editingFinished.connect(self._on_interval_editing_finished)
        settings_tail = QLabel("分鐘提醒休息")
        settings_tail.setWordWrap(True)
        settings_layout.addWidget(settings_label)
        settings_layout.addWidget(self.interval_input)
        settings_layout.addWidget(settings_tail)
        settings_layout.addStretch()
        layout.addWidget(settings_card)

        timer_card = QFrame()
        timer_card.setObjectName("TimerCard")
        timer_card.setMinimumHeight(176)
        timer_layout = QHBoxLayout(timer_card)
        timer_layout.setContentsMargins(18, 14, 18, 14)
        timer_layout.setSpacing(14)

        self.state_animation_widget = LottieGifAnimationWidget(ANIMATION_BOX_SIZE)
        self.animation_container = self.state_animation_widget
        self.animation_label = self.state_animation_widget.gif_label
        self.lottie_animation_view = self.state_animation_widget.lottie_view

        self.time_caption_label = QLabel()
        self.time_caption_label.setObjectName("TimerCaption")
        self.time_caption_label.setAlignment(Qt.AlignCenter)
        self.time_label = QLabel()
        self.time_label.setObjectName("TimerText")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setMinimumHeight(72)
        self.status_label = QLabel()
        self.status_label.setObjectName("StatusPill")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedHeight(34)

        timer_text_layout = QVBoxLayout()
        timer_text_layout.setContentsMargins(0, 0, 0, 0)
        timer_text_layout.setSpacing(7)
        timer_text_layout.addStretch()
        timer_text_layout.addWidget(self.time_caption_label)
        timer_text_layout.addWidget(self.time_label)
        timer_text_layout.addWidget(self.status_label, alignment=Qt.AlignCenter)
        timer_text_layout.addStretch()
        timer_layout.addWidget(self.animation_container, alignment=Qt.AlignCenter)
        timer_layout.addLayout(timer_text_layout, stretch=1)
        layout.addWidget(timer_card)

        control_card = self._make_card()
        control_layout = QGridLayout(control_card)
        control_layout.setContentsMargins(12, 12, 12, 12)
        control_layout.setHorizontalSpacing(10)
        control_layout.setVerticalSpacing(9)

        self.start_button = QPushButton("開始工作")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self._on_start_work)
        self.pause_button = QPushButton("暫停")
        self.pause_button.clicked.connect(
            lambda: self._run_timer_action(self.timer.pause, ended_by="pause")
        )
        self.restart_button = QPushButton("重新開始")
        self.restart_button.clicked.connect(self._on_restart_countdown)
        self.snooze_button = QPushButton("延後 5 分鐘")
        self.snooze_button.clicked.connect(self._on_snooze)
        self.start_break_button = QPushButton("立即休息")
        self.start_break_button.clicked.connect(self._on_start_break)
        self.end_day_button = QPushButton("結束今天")
        self.end_day_button.setObjectName("EndButton")
        self.end_day_button.clicked.connect(self._on_end_day)

        for button in [
            self.start_button,
            self.pause_button,
            self.restart_button,
            self.snooze_button,
            self.start_break_button,
            self.end_day_button,
        ]:
            button.setMinimumHeight(36)

        self.start_button.setMinimumHeight(42)
        control_layout.addWidget(self.start_button, 0, 0, 1, 2)
        control_layout.addWidget(self.pause_button, 1, 0)
        control_layout.addWidget(self.restart_button, 1, 1)
        control_layout.addWidget(self.snooze_button, 2, 0)
        control_layout.addWidget(self.start_break_button, 2, 1)
        control_layout.addWidget(self.end_day_button, 3, 0, 1, 2)
        control_layout.setColumnStretch(0, 1)
        control_layout.setColumnStretch(1, 1)
        layout.addWidget(control_card)

        stats_title = QLabel("今日統計")
        stats_title.setObjectName("SectionTitle")
        layout.addWidget(stats_title)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(9)
        stats_grid.setVerticalSpacing(9)
        self.work_total_value = self._add_stat_card(stats_grid, "工作總時間", 0, 0)
        self.break_total_value = self._add_stat_card(stats_grid, "休息總時間", 0, 1)
        self.break_count_value = self._add_stat_card(stats_grid, "休息次數", 1, 0)
        self.water_total_value = self._add_stat_card(stats_grid, "喝水總量", 1, 1)
        self.current_break_value = self._add_stat_card(stats_grid, "目前休息", 2, 0)
        self.last_break_value = self._add_stat_card(stats_grid, "上次休息", 2, 1)
        for column in range(2):
            stats_grid.setColumnStretch(column, 1)
        layout.addLayout(stats_grid)
        layout.addStretch()

    def _make_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        return card

    def _add_stat_card(
        self,
        parent_layout: QGridLayout,
        label: str,
        row: int,
        column: int,
    ) -> QLabel:
        card = self._make_card()
        card.setMinimumHeight(70)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(11, 9, 11, 9)
        card_layout.setSpacing(5)
        label_widget = QLabel(label)
        label_widget.setObjectName("StatLabel")
        value_widget = QLabel("0 分鐘")
        value_widget.setObjectName("StatValue")
        label_widget.setWordWrap(True)
        value_widget.setWordWrap(True)
        card_layout.addWidget(label_widget)
        card_layout.addWidget(value_widget)
        parent_layout.addWidget(card, row, column)
        return value_widget

    def _position_bottom_right(self) -> None:
        screen = self.app.primaryScreen().availableGeometry()
        x = max(0, screen.right() - WINDOW_WIDTH - WINDOW_MARGIN_X)
        y = max(0, screen.bottom() - WINDOW_HEIGHT - WINDOW_MARGIN_Y)
        self.window.move(x, y)

    def _check_date_rollover(self) -> bool:
        current_date = self._current_date()
        if current_date == self.today:
            return False

        self._advance_timer_to_now(render=False, show_reminder=False)
        snapshot = self.timer.snapshot()
        if snapshot.state == TimerState.BREAKING or self._pending_break is not None:
            self._date_rollover_pending = True
            return False

        if snapshot.state in {TimerState.WORKING, TimerState.REMINDER}:
            self._end_active_work_session("day_rollover")
        self._save_work_minutes_if_needed(force=True)
        self.today = current_date
        self._date_rollover_pending = False

        try:
            self._session_break_records = self.storage.list_break_records(self.today)
            self._session_work_records = self.storage.list_work_session_records(self.today)
            work_minutes = self.storage.get_work_minutes(self.today)
        except (StorageError, ValueError) as exc:
            QMessageBox.warning(
                self.window,
                "日期切換提醒",
                f"切換到新的一天時讀取資料失敗，今日統計將先從 0 開始。\n原因：{exc}",
            )
            self._session_break_records = []
            self._session_work_records = []
            work_minutes = 0

        self.timer.reset_day(
            break_interval_minutes=self.timer.break_interval_minutes,
            initial_work_seconds=work_minutes * 60,
        )
        self._last_saved_work_date = self.today
        self._last_saved_work_minutes = work_minutes
        self._last_tick_monotonic = time.monotonic()
        self._active_work_session_start_time = None
        self._active_work_session_seconds = 0
        self._reminder_prompted_for_current_round = False
        self._render(self.timer.snapshot())
        return True

    def _save_work_minutes_if_needed(
        self,
        force: bool = False,
        show_errors: bool = False,
    ) -> None:
        work_minutes = self.timer.snapshot().total_work_seconds // 60
        if (
            not force
            and self._last_saved_work_date == self.today
            and work_minutes == self._last_saved_work_minutes
        ):
            return

        try:
            self.storage.set_work_minutes(self.today, work_minutes)
        except (StorageError, ValueError) as exc:
            if show_errors:
                QMessageBox.warning(self.window, "工作時間保存失敗", str(exc))
            return

        self._last_saved_work_date = self.today
        self._last_saved_work_minutes = work_minutes

    def _save_current_settings(self, interval_minutes: int) -> None:
        try:
            self.storage.save_settings(
                AppSettings(break_interval_minutes=interval_minutes)
            )
        except (StorageError, ValueError) as exc:
            QMessageBox.warning(self.window, "設定保存失敗", str(exc))

    def _apply_interval_setting(self) -> int | None:
        if self.timer.snapshot().state == TimerState.WORKING:
            return self.timer.break_interval_minutes

        interval_minutes = self._read_interval_minutes(restore_on_error=True)
        if interval_minutes is None:
            return None

        try:
            self.timer.set_break_interval(interval_minutes)
        except (TimerStateError, ValueError) as exc:
            QMessageBox.warning(self.window, "無法套用休息間隔", str(exc))
            self._restore_interval_input()
            return None

        self._save_current_settings(interval_minutes)
        self._last_valid_interval_minutes = interval_minutes
        self._render(self.timer.snapshot())
        return interval_minutes

    def _on_interval_editing_finished(self) -> None:
        if self.timer.snapshot().state == TimerState.WORKING:
            self._restore_interval_input()
            return

        self._apply_interval_setting()

    def _restore_interval_input(self) -> None:
        previous_block_state = self.interval_input.blockSignals(True)
        self.interval_input.setText(str(self._last_valid_interval_minutes))
        self.interval_input.blockSignals(previous_block_state)

    def _restore_invalid_interval_after_action(self) -> None:
        if self._read_interval_minutes(show_errors=False) is not None:
            return

        QMessageBox.warning(
            self.window,
            "輸入錯誤",
            "休息間隔無效，已還原為上一個有效設定。",
        )
        self._restore_interval_input()

    def _advance_timer_to_now(
        self,
        render: bool = True,
        show_reminder: bool = True,
    ) -> TimerSnapshot:
        now = time.monotonic()
        elapsed_seconds = int(now - self._last_tick_monotonic)
        if elapsed_seconds <= 0:
            return self.timer.snapshot()

        previous_snapshot = self.timer.snapshot()
        self._last_tick_monotonic += elapsed_seconds
        snapshot = self.timer.tick(elapsed_seconds)
        self._sync_work_session_transition(previous_snapshot, snapshot)
        if render:
            self._render(snapshot)
        self._save_work_minutes_if_needed()
        if show_reminder:
            self._maybe_show_reminder_dialog(snapshot)
        return snapshot

    def _sync_work_session_transition(
        self,
        previous_snapshot: TimerSnapshot,
        current_snapshot: TimerSnapshot,
        ended_by: str = "unknown",
        restart_work_session: bool = False,
    ) -> None:
        work_delta = (
            current_snapshot.total_work_seconds
            - previous_snapshot.total_work_seconds
        )
        if previous_snapshot.state == TimerState.WORKING and work_delta > 0:
            self._add_active_work_seconds(work_delta)

        previous_state = previous_snapshot.state
        current_state = current_snapshot.state
        active_session_states = {TimerState.WORKING, TimerState.REMINDER}

        if restart_work_session and current_state == TimerState.WORKING:
            if previous_state in active_session_states:
                self._end_active_work_session(ended_by)
            self._begin_active_work_session()
            return

        if (
            previous_state == TimerState.WORKING
            and current_state == TimerState.REMINDER
        ):
            return

        if (
            previous_state == TimerState.REMINDER
            and current_state == TimerState.WORKING
        ):
            return

        if (
            previous_state in active_session_states
            and current_state not in active_session_states
        ):
            self._end_active_work_session(ended_by)
            return

        if (
            previous_state not in active_session_states
            and current_state == TimerState.WORKING
        ):
            self._begin_active_work_session()

    def _begin_active_work_session(self) -> None:
        if self._active_work_session_start_time is not None:
            return

        self._active_work_session_start_time = self._session_timestamp()
        self._active_work_session_seconds = 0

    def _add_active_work_seconds(self, seconds: int) -> None:
        if self._active_work_session_start_time is None:
            self._begin_active_work_session()
        self._active_work_session_seconds += max(0, int(seconds))

    def _end_active_work_session(self, ended_by: str) -> None:
        if self._active_work_session_start_time is None:
            return

        duration_seconds = max(0, int(self._active_work_session_seconds))
        duration_minutes = duration_seconds // 60
        start_time = self._active_work_session_start_time
        self._active_work_session_start_time = None
        self._active_work_session_seconds = 0

        if duration_minutes < 1:
            return

        record = WorkSessionRecord.create(
            start_time=start_time,
            end_time=start_time + timedelta(seconds=duration_seconds),
            duration_minutes=duration_minutes,
            ended_by=ended_by,
        )

        try:
            self.storage.add_work_session_record(record)
        except (StorageError, ValueError) as exc:
            QMessageBox.warning(self.window, "å·¥ä½œå€æ®µä¿å­˜å¤±æ•—", str(exc))
            return

        if record.date == self.today:
            self._session_work_records.append(record)

    def _session_timestamp(self) -> datetime:
        try:
            current_day = date.fromisoformat(self.today)
        except ValueError:
            return datetime.now().replace(microsecond=0)

        return datetime.combine(
            current_day,
            datetime.now().time(),
        ).replace(microsecond=0)

    def _on_window_close(self, event) -> None:  # type: ignore[no-untyped-def]
        self._advance_timer_to_now(render=False, show_reminder=False)
        if self.timer.snapshot().state in {TimerState.WORKING, TimerState.REMINDER}:
            self._end_active_work_session("unknown")
        self._stop_state_animation()
        self._save_work_minutes_if_needed(force=True, show_errors=True)
        event.accept()

    def _on_tick(self) -> None:
        if self._check_date_rollover():
            return

        self._advance_timer_to_now(render=True, show_reminder=True)

    def _on_start_work(self) -> None:
        self._check_date_rollover()
        state = self.timer.snapshot().state

        if self._pending_break is not None:
            self._show_break_record_dialog()
            return

        if state == TimerState.PAUSED:
            self._resume_work_after_pause()
            return

        if state == TimerState.BREAKING:
            self._finish_break_and_prompt_record()
            return

        if state == TimerState.REMINDER:
            self._on_start_break()
            return

        interval_minutes = self._apply_interval_setting()
        if interval_minutes is None:
            return

        if self._run_timer_action(lambda: self._start_work_from_current_state(interval_minutes)):
            self._last_valid_interval_minutes = interval_minutes

    def _start_work_from_current_state(self, interval_minutes: int) -> TimerSnapshot:
        if self.timer.snapshot().state == TimerState.DAY_ENDED:
            existing_work_seconds = self.timer.snapshot().total_work_seconds
            self.timer.reset_day(
                break_interval_minutes=interval_minutes,
                initial_work_seconds=existing_work_seconds,
            )

        return self.timer.start_work(interval_minutes)

    def _on_restart_countdown(self) -> None:
        self._check_date_rollover()
        interval_minutes = self._apply_interval_setting()
        if interval_minutes is None:
            if self.timer.snapshot().state != TimerState.REMINDER:
                return
            interval_minutes = self._last_valid_interval_minutes

        if self._run_timer_action(
            lambda: self.timer.restart_countdown(interval_minutes),
            ended_by="restart",
            restart_work_session=True,
        ):
            self._last_valid_interval_minutes = interval_minutes

    def _resume_work_after_pause(self) -> bool:
        if self._apply_interval_setting() is None:
            return False

        return self._run_timer_action(self.timer.resume_work)

    def _on_snooze(self) -> None:
        if self._run_timer_action(self.timer.snooze):
            self._restore_invalid_interval_after_action()

    def _finish_break_and_prompt_record(self) -> bool:
        try:
            completed_break = self.timer.return_to_work(auto_start_next_round=False)
        except TimerStateError as exc:
            QMessageBox.warning(self.window, "無法執行", str(exc))
            return False

        self._pending_break = completed_break
        self._last_tick_monotonic = time.monotonic()
        self._render(self.timer.snapshot())
        return self._show_break_record_dialog()

    def _on_start_break(self) -> None:
        snapshot = self.timer.snapshot()
        if snapshot.state == TimerState.PAUSED:
            if self._apply_interval_setting() is None:
                return

            snapshot = self.timer.snapshot()

        if snapshot.state == TimerState.REMINDER:
            if self._run_timer_action(self.timer.start_break, ended_by="break"):
                self._restore_invalid_interval_after_action()
            return

        self._run_timer_action(self.timer.start_break_early, ended_by="early_break")

    def _maybe_show_reminder_dialog(self, snapshot: TimerSnapshot) -> None:
        if snapshot.state != TimerState.REMINDER:
            if not self._reminder_dialog_open:
                self._reminder_prompted_for_current_round = False
            return

        if (
            self._reminder_prompted_for_current_round
            or self._reminder_dialog_open
        ):
            return

        self._reminder_prompted_for_current_round = True
        self._show_reminder_dialog()

    def _show_reminder_dialog(self) -> None:
        if self.timer.snapshot().state != TimerState.REMINDER:
            return

        action: ReminderAction | None = None
        self._reminder_dialog_open = True
        try:
            QApplication.beep()
            self.app.alert(self.window, 0)
            dialog = ReminderDialog(self.window)
            dialog.exec_()
            action = dialog.action
        finally:
            self._reminder_dialog_open = False

        if self.timer.snapshot().state != TimerState.REMINDER or action is None:
            return

        if action == ReminderAction.START_BREAK:
            self._on_start_break()
        elif action == ReminderAction.SNOOZE:
            self._on_snooze()
        elif action == ReminderAction.RESTART:
            self._on_restart_countdown()

    def _run_timer_action(
        self,
        action: Callable[[], object],
        ended_by: str = "unknown",
        restart_work_session: bool = False,
    ) -> bool:
        previous_snapshot = self.timer.snapshot()
        try:
            action()
        except (TimerStateError, ValueError) as exc:
            QMessageBox.warning(self.window, "無法執行", str(exc))
            return False

        self._last_tick_monotonic = time.monotonic()
        self._save_work_minutes_if_needed(force=True)
        snapshot = self.timer.snapshot()
        self._sync_work_session_transition(
            previous_snapshot,
            snapshot,
            ended_by=ended_by,
            restart_work_session=restart_work_session,
        )
        self._render(snapshot)
        self._maybe_show_reminder_dialog(snapshot)
        return True

    def _on_end_day(self) -> None:
        self._check_date_rollover()
        snapshot = self.timer.snapshot()
        if snapshot.state == TimerState.BREAKING:
            try:
                self._pending_break = self.timer.return_to_work(
                    auto_start_next_round=False
                )
            except TimerStateError as exc:
                QMessageBox.warning(self.window, "無法執行", str(exc))
                return

            self._last_tick_monotonic = time.monotonic()
            self._render(self.timer.snapshot())
            if not self._show_break_record_dialog(resume_after_save=False):
                return

        if self._pending_break is not None:
            if not self._show_break_record_dialog(resume_after_save=False):
                return

        try:
            if self.timer.snapshot().state in {TimerState.WORKING, TimerState.REMINDER}:
                self._end_active_work_session("end_day")
            self._save_work_minutes_if_needed(force=True)
            statistics = calculate_daily_statistics(
                date=self.today,
                work_minutes=self.timer.snapshot().total_work_seconds // 60,
                break_records=self._session_break_records,
                work_session_records=self._session_work_records,
            )
            summary = create_daily_summary(statistics)
            self.storage.set_work_minutes(self.today, summary.work_minutes)
            self.storage.save_daily_summary(summary)
            previous_snapshot = self.timer.snapshot()
            self.timer.end_day()
            self._sync_work_session_transition(
                previous_snapshot,
                self.timer.snapshot(),
                ended_by="end_day",
            )
        except (StorageError, TimerStateError, ValueError) as exc:
            QMessageBox.critical(self.window, "結束今天失敗", str(exc))
            return

        self._render(self.timer.snapshot())
        ReportDialog(self.window, summary).show()

    def _show_break_record_dialog(self, resume_after_save: bool = True) -> bool:
        if self._pending_break is None:
            return True

        dialog = BreakRecordDialog(self.window, self._pending_break)
        if dialog.exec_() != QDialog.Accepted:
            return False

        break_record = self._build_break_record(
            water_ml=dialog.water_ml,
            note=dialog.note,
        )

        try:
            self.storage.add_break_record(break_record)
        except (StorageError, ValueError) as exc:
            QMessageBox.critical(self.window, "儲存失敗", str(exc))
            return False

        self._session_break_records.append(break_record)
        self._pending_break = None
        if (
            resume_after_save
            and self._date_rollover_pending
            and self._check_date_rollover()
        ):
            return True

        if resume_after_save:
            self._resume_work_after_pause()
        else:
            self._render(self.timer.snapshot())
        return True

    def _read_interval_minutes(
        self,
        restore_on_error: bool = False,
        show_errors: bool = True,
    ) -> int | None:
        raw_value = self.interval_input.text().strip()
        if not raw_value:
            if show_errors:
                QMessageBox.warning(self.window, "輸入錯誤", "休息間隔不可空白。")
            if restore_on_error:
                self._restore_interval_input()
            return None

        try:
            interval_minutes = int(raw_value)
        except ValueError:
            if show_errors:
                QMessageBox.warning(self.window, "輸入錯誤", "休息間隔必須是正整數。")
            if restore_on_error:
                self._restore_interval_input()
            return None

        if interval_minutes < 1:
            if show_errors:
                QMessageBox.warning(self.window, "輸入錯誤", "休息間隔不可小於 1 分鐘。")
            if restore_on_error:
                self._restore_interval_input()
            return None

        return interval_minutes

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

    def _update_state_animation(self, state: TimerState) -> None:
        if self._state_animation_state == state:
            return

        self._stop_state_animation()
        self._state_animation_state = state
        self._state_animation_mode = self.state_animation_widget.load(
            TIMER_STATE_TO_LOTTIE.get(state),
            TIMER_STATE_TO_GIF.get(state),
        )
        self._state_animation_movie = self.state_animation_widget.movie

    def _stop_state_animation(self) -> None:
        self.state_animation_widget.clear()
        self._state_animation_movie = None
        self._state_animation_mode = None

    def _render(self, snapshot: TimerSnapshot) -> None:
        state = snapshot.state
        self._update_state_animation(state)
        if state != TimerState.REMINDER and not self._reminder_dialog_open:
            self._reminder_prompted_for_current_round = False

        self.status_label.setText(STATE_LABELS[state])
        foreground, background = STATE_COLORS[state]
        self.status_label.setStyleSheet(
            f"color: {foreground}; background: {background}; "
            "border-radius: 15px; padding: 6px 16px; "
            "font-size: 13px; font-weight: 700;"
        )

        if state == TimerState.BREAKING:
            self.time_caption_label.setText("休息已進行")
            self.time_label.setText(_format_seconds(snapshot.break_elapsed_seconds))
        elif state == TimerState.REMINDER:
            self.time_caption_label.setText("提醒時間到")
            self.time_label.setText("00:00")
        else:
            self.time_caption_label.setText("剩餘倒數")
            self.time_label.setText(_format_seconds(snapshot.remaining_seconds))

        self._render_statistics(snapshot)
        self._update_button_states(state)

    def _render_statistics(self, snapshot: TimerSnapshot) -> None:
        stats = calculate_daily_statistics(
            date=self.today,
            work_minutes=snapshot.total_work_seconds // 60,
            break_records=self._session_break_records,
            work_session_records=self._session_work_records,
        )
        self.work_total_value.setText(_format_minutes(stats.work_minutes))
        self.break_total_value.setText(_format_minutes(stats.break_minutes))
        self.break_count_value.setText(f"{stats.break_count} 次")
        self.water_total_value.setText(f"{stats.water_ml} ml")
        self.current_break_value.setText(_format_seconds(snapshot.break_elapsed_seconds))
        self.last_break_value.setText(_format_last_break(snapshot))

    def _update_button_states(self, state: TimerState) -> None:
        pending_break = self._pending_break is not None
        interval_locked = state == TimerState.WORKING
        self.interval_input.setReadOnly(interval_locked)
        if interval_locked:
            self.interval_input.setToolTip(
                "工作倒數期間不可修改；暫停或休息時可設定下一輪時間。"
            )
            self.interval_input.setStyleSheet(
                "background: #f7f3f6; color: #7c6d80; border-color: #eee4eb;"
            )
        else:
            self.interval_input.setToolTip("設定下一輪工作倒數的休息提醒間隔。")
            self.interval_input.setStyleSheet("")

        if pending_break or state == TimerState.BREAKING:
            self.start_button.setText("回到工作")
            self.start_button.setToolTip("儲存休息紀錄並回到工作倒數。")
        elif state == TimerState.PAUSED:
            self.start_button.setText("繼續工作")
            self.start_button.setToolTip("繼續工作倒數。")
        elif state == TimerState.REMINDER:
            self.start_button.setText("開始休息")
            self.start_button.setToolTip("開始本次休息。")
        else:
            self.start_button.setText("開始工作")
            if state == TimerState.WORKING:
                self.start_button.setToolTip("已在工作倒數中")
            else:
                self.start_button.setToolTip("開始工作倒數。")

        self.start_button.setEnabled(state != TimerState.WORKING)
        self.pause_button.setEnabled(state == TimerState.WORKING)
        self.restart_button.setEnabled(
            state
            in {
                TimerState.IDLE,
                TimerState.WORKING,
                TimerState.PAUSED,
                TimerState.REMINDER,
            }
            and not pending_break
        )
        self.snooze_button.setEnabled(state == TimerState.REMINDER)
        self.start_break_button.setEnabled(
            state
            in {
                TimerState.WORKING,
                TimerState.PAUSED,
            }
            and not pending_break
        )
        self.end_day_button.setEnabled(state != TimerState.DAY_ENDED)


class BreakRecordDialog(QDialog):
    """Collect water intake and notes for a completed break."""

    def __init__(self, parent: QWidget, completed_break: CompletedBreak) -> None:
        super().__init__(parent)
        self.completed_break = completed_break
        self.water_ml = 0
        self.note = ""

        self.setWindowTitle("休息紀錄")
        self.resize(BREAK_DIALOG_WIDTH, BREAK_DIALOG_HEIGHT)
        self.setMinimumSize(340, 300)
        self.setModal(True)
        font_family = QApplication.instance().font().family()
        self.setStyleSheet(
            """
            QDialog {
                background: #fff7fb;
                font-family: "__FONT_FAMILY__";
                font-size: 13px;
            }
            QLabel {
                color: #3b2f3f;
                font-size: 13px;
            }
            QLabel#DialogTitle {
                color: #2f2533;
                font-size: 20px;
                font-weight: 800;
            }
            QLabel#DialogHint {
                color: #7c6d80;
                font-size: 12px;
            }
            QLineEdit, QTextEdit {
                background: #ffffff;
                border: 1px solid #e6cadb;
                border-radius: 12px;
                min-height: 34px;
                padding: 8px 10px;
                color: #2f2533;
                font-size: 13px;
            }
            QPushButton {
                color: #ffffff;
                background: #ec6f9f;
                border: 1px solid #ec6f9f;
                border-radius: 14px;
                min-height: 40px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover { background: #df5d91; }
            """
            .replace("__FONT_FAMILY__", font_family)
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("休息紀錄")
        title.setObjectName("DialogTitle")
        hint = QLabel(f"本次休息：{completed_break.duration_minutes} 分鐘")
        hint.setObjectName("DialogHint")
        layout.addWidget(title)
        layout.addWidget(hint)

        water_row = QHBoxLayout()
        water_row.addWidget(QLabel("喝水量"))
        self.water_input = QLineEdit("0")
        self.water_input.setValidator(QIntValidator(0, 99999, self.water_input))
        self.water_input.setAlignment(Qt.AlignRight)
        water_row.addWidget(self.water_input)
        water_row.addWidget(QLabel("ml"))
        layout.addLayout(water_row)

        layout.addWidget(QLabel("備註（可選）"))
        self.note_input = QTextEdit()
        self.note_input.setFixedHeight(96)
        layout.addWidget(self.note_input)

        save_button = QPushButton("儲存休息紀錄")
        save_button.clicked.connect(self._accept_record)
        layout.addWidget(save_button)
        self.water_input.setFocus()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        QMessageBox.information(self, "請先儲存", "請先儲存休息紀錄，再回到下一輪工作。")
        event.ignore()

    def _accept_record(self) -> None:
        raw_water = self.water_input.text().strip()
        if not raw_water:
            raw_water = "0"

        try:
            water_ml = int(raw_water)
        except ValueError:
            QMessageBox.warning(self, "輸入錯誤", "喝水量必須是 0 或正整數。")
            return

        if water_ml < 0:
            QMessageBox.warning(self, "輸入錯誤", "喝水量不可小於 0。")
            return

        self.water_ml = water_ml
        self.note = self.note_input.toPlainText().strip()
        self.accept()


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

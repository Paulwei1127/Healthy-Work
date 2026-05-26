import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QRect, QSize, Qt
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QWidget

from app.data.models import DailySummary
from app.ui.report_dialog import (
    REPORT_DIALOG_HEIGHT,
    REPORT_DIALOG_MIN_HEIGHT,
    REPORT_DIALOG_MIN_WIDTH,
    REPORT_DIALOG_PARENT_OFFSET_X,
    REPORT_DIALOG_PARENT_OFFSET_Y,
    REPORT_DIALOG_SCREEN_MARGIN,
    REPORT_DIALOG_WIDTH,
    ReportDialog,
    _format_health_score,
    _position_dialog,
)


class FakeScreen:
    def __init__(self, available_geometry: QRect) -> None:
        self._available_geometry = available_geometry

    def availableGeometry(self) -> QRect:
        return self._available_geometry


class FakeParent:
    def __init__(self, geometry: QRect, screen: FakeScreen) -> None:
        self._geometry = geometry
        self._screen = screen

    def geometry(self) -> QRect:
        return self._geometry

    def screen(self) -> FakeScreen:
        return self._screen


class FakeDialog:
    def __init__(self, size: QSize) -> None:
        self._size = size
        self.moved_to: tuple[int, int] | None = None

    def size(self) -> QSize:
        return self._size

    def sizeHint(self) -> QSize:
        return self._size

    def move(self, x: int, y: int) -> None:
        self.moved_to = (x, y)


def test_report_dialog_stays_inside_screen_when_parent_is_bottom_right() -> None:
    available = QRect(0, 0, 1920, 1080)
    parent = FakeParent(QRect(1800, 900, 440, 660), FakeScreen(available))
    dialog = FakeDialog(QSize(REPORT_DIALOG_WIDTH, REPORT_DIALOG_HEIGHT))

    _position_dialog(dialog, parent)  # type: ignore[arg-type]

    assert dialog.moved_to is not None
    x, y = dialog.moved_to
    assert x + dialog.size().width() <= available.left() + available.width() - REPORT_DIALOG_SCREEN_MARGIN
    assert y + dialog.size().height() <= available.top() + available.height() - REPORT_DIALOG_SCREEN_MARGIN


def test_report_dialog_general_position_is_relative_to_parent() -> None:
    available = QRect(0, 0, 1920, 1080)
    parent_geometry = QRect(300, 200, 440, 660)
    parent = FakeParent(parent_geometry, FakeScreen(available))
    dialog = FakeDialog(QSize(REPORT_DIALOG_WIDTH, REPORT_DIALOG_HEIGHT))

    _position_dialog(dialog, parent)  # type: ignore[arg-type]

    expected_x = (
        parent_geometry.center().x()
        - dialog.size().width() // 2
        + REPORT_DIALOG_PARENT_OFFSET_X
    )
    expected_y = (
        parent_geometry.center().y()
        - dialog.size().height() // 2
        + REPORT_DIALOG_PARENT_OFFSET_Y
    )
    fixed_screen_center = (
        available.left() + (available.width() - dialog.size().width()) // 2,
        available.top() + (available.height() - dialog.size().height()) // 2,
    )

    assert dialog.moved_to == (expected_x, expected_y)
    assert dialog.moved_to != fixed_screen_center


def test_report_dialog_uses_compact_default_size_constants() -> None:
    assert REPORT_DIALOG_WIDTH == 420
    assert REPORT_DIALOG_HEIGHT == 520
    assert REPORT_DIALOG_MIN_WIDTH == 340
    assert REPORT_DIALOG_MIN_HEIGHT == 400
    assert REPORT_DIALOG_MIN_WIDTH <= REPORT_DIALOG_WIDTH
    assert REPORT_DIALOG_MIN_HEIGHT <= REPORT_DIALOG_HEIGHT


def test_health_score_formatter_keeps_user_facing_text() -> None:
    assert _format_health_score(_summary(work_minutes=0, health_score=None)) == "今天尚未工作"
    assert (
        _format_health_score(_summary(work_minutes=20, health_score=None))
        == "資料較少，暫不評分"
    )
    assert _format_health_score(_summary(work_minutes=60, health_score=88)) == "88 / 100"


def test_report_dialog_score_label_wraps_and_stays_centered(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(430, 560)
    captured: dict[str, object] = {}

    def fake_exec(dialog: QDialog) -> int:
        score_label = dialog.findChild(QLabel, "Score")
        assert score_label is not None
        captured["text"] = score_label.text()
        captured["word_wrap"] = score_label.wordWrap()
        captured["alignment"] = score_label.alignment()
        captured["minimum_height"] = score_label.minimumHeight()
        captured["size"] = dialog.size()
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec_", fake_exec)

    ReportDialog(parent, _summary(work_minutes=20, health_score=None)).show()

    assert captured["text"] == "資料較少，暫不評分"
    assert captured["word_wrap"] is True
    assert captured["alignment"] == Qt.AlignCenter
    assert captured["minimum_height"] == 48
    assert captured["size"] == QSize(REPORT_DIALOG_WIDTH, REPORT_DIALOG_HEIGHT)
    parent.close()
    app.processEvents()


def _summary(work_minutes: int, health_score: int | None) -> DailySummary:
    return DailySummary(
        date="2026-05-26",
        work_minutes=work_minutes,
        break_minutes=0,
        break_count=0,
        water_ml=0,
        average_work_session_minutes=None,
        health_score=health_score,
    )

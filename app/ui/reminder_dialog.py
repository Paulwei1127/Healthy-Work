"""PyQt5 reminder dialog for break time."""

from __future__ import annotations

from enum import Enum

try:
    from PyQt5.QtCore import QSize, Qt, QTimer
    from PyQt5.QtWidgets import (
        QApplication,
        QDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - depends on local installation.
    raise RuntimeError(
        "PyQt5 is required for the current UI. "
        "Install it with: pip install -r requirements.txt"
    ) from exc

from app.ui.animation import LottieGifAnimationWidget


REMINDER_ANIMATION_BOX_SIZE = QSize(100, 120)
REMINDER_LOTTIE_PATH = "gif/json/Le Petit Chat _Cat_ Noir.json"
REMINDER_GIF_PATH = "gif/Le Petit Chat _Cat_ Noir.gif"


class ReminderAction(str, Enum):
    """User actions available when work time is up."""

    START_BREAK = "start_break"
    SNOOZE = "snooze"
    RESTART = "restart"


class ReminderDialog(QDialog):
    """Small top-most dialog that nudges the user to take a break."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.action: ReminderAction | None = None

        self.setWindowTitle("該休息一下了")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.resize(460, 390)
        self.setMinimumSize(420, 360)

        font_family = QApplication.instance().font().family()
        self.setStyleSheet(
            """
            QDialog {
                background: #fff7fb;
                font-family: "__FONT_FAMILY__";
                font-size: 13px;
            }
            QFrame#Card {
                background: #ffffff;
                border: 1px solid #f0d9e7;
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
            QLabel#Body {
                color: #4b3f50;
                font-size: 13px;
            }
            QLabel#Hint {
                color: #7c6d80;
                font-size: 12px;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #e7cadb;
                border-radius: 12px;
                min-height: 36px;
                padding: 7px 10px;
                color: #3b2f3f;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #fff1f7;
                border-color: #f3a8c7;
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
            """
            .replace("__FONT_FAMILY__", font_family)
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        self.animation_widget = LottieGifAnimationWidget(REMINDER_ANIMATION_BOX_SIZE)
        self.animation_mode = self.animation_widget.load(
            REMINDER_LOTTIE_PATH,
            REMINDER_GIF_PATH,
        )

        title = QLabel("該休息一下了")
        title.setObjectName("Title")
        body = _make_message_label(
            "起來走走、喝點水，讓眼睛離開螢幕。",
            "Body",
        )
        eye_rest = _make_message_label(
            "20-20-20：看向遠方 20 秒，讓眼睛放鬆。",
            "Body",
        )
        hint = _make_message_label("伸展肩頸、走動一下，回來會更穩。", "Hint")

        card_layout.addWidget(self.animation_widget, alignment=Qt.AlignCenter)
        card_layout.addWidget(title)
        card_layout.addWidget(body)
        card_layout.addWidget(eye_rest)
        card_layout.addWidget(hint)
        layout.addWidget(card)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        start_break_button = QPushButton("立即休息")
        start_break_button.setObjectName("PrimaryButton")
        snooze_button = QPushButton("延後 5 分鐘")
        top_row.addWidget(start_break_button)
        top_row.addWidget(snooze_button)
        layout.addLayout(top_row)

        restart_button = QPushButton("重新開始倒數")
        layout.addWidget(restart_button)

        start_break_button.clicked.connect(
            lambda: self._finish(ReminderAction.START_BREAK)
        )
        snooze_button.clicked.connect(lambda: self._finish(ReminderAction.SNOOZE))
        restart_button.clicked.connect(lambda: self._finish(ReminderAction.RESTART))

        QTimer.singleShot(0, self._raise_and_focus)

    def _finish(self, action: ReminderAction) -> None:
        self.action = action
        self._clear_animation_safely()
        self.accept()

    def reject(self) -> None:  # type: ignore[override]
        self.action = ReminderAction.SNOOZE
        self._clear_animation_safely()
        super().accept()

    def _clear_animation_safely(self) -> None:
        try:
            self.animation_widget.clear()
        except RuntimeError:
            pass

    def _raise_and_focus(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()


def _make_message_label(text: str, object_name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setTextFormat(Qt.PlainText)
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return label

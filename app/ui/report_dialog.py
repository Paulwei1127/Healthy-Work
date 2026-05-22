"""PyQt5 end-of-day report dialog."""

from __future__ import annotations

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QDialog,
        QFrame,
        QGridLayout,
        QLabel,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - depends on local installation.
    raise RuntimeError(
        "PyQt5 is required for the current UI. "
        "Install it with: pip install -r requirements.txt"
    ) from exc

from app.data.models import DailySummary


REPORT_DIALOG_WIDTH = 500
REPORT_DIALOG_HEIGHT = 620
REPORT_DIALOG_MIN_WIDTH = 380
REPORT_DIALOG_MIN_HEIGHT = 500


class ReportDialog:
    """Display a saved DailySummary in a polished modal dialog."""

    def __init__(self, parent: QWidget, summary: DailySummary) -> None:
        self.parent = parent
        self.summary = summary

    def show(self) -> None:
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("今日健康工作報告")
        dialog.resize(REPORT_DIALOG_WIDTH, REPORT_DIALOG_HEIGHT)
        dialog.setMinimumSize(REPORT_DIALOG_MIN_WIDTH, REPORT_DIALOG_MIN_HEIGHT)
        dialog.setModal(True)
        font_family = self.parent.font().family()
        dialog.setStyleSheet(
            """
            QDialog {
                background: #fff7fb;
                font-family: "__FONT_FAMILY__";
                font-size: 13px;
            }
            QScrollArea#ReportScroll {
                background: #fff7fb;
                border: 0;
            }
            QWidget#ReportContent {
                background: #fff7fb;
            }
            QFrame#Card {
                background: #ffffff;
                border: 1px solid #f0d9e7;
                border-radius: 18px;
            }
            QLabel#Title {
                color: #2f2533;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#Subtle {
                color: #7c6d80;
                font-size: 12px;
            }
            QLabel#Score {
                color: #1f6f5b;
                font-family: "Segoe UI", "Microsoft JhengHei UI", "Yu Gothic UI";
                font-size: 42px;
                font-weight: 900;
            }
            QLabel#Section {
                color: #8a5c75;
                font-size: 13px;
                font-weight: 800;
            }
            QLabel#MetricLabel {
                color: #7c6d80;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#MetricValue {
                color: #2f2533;
                font-size: 15px;
                font-weight: 800;
            }
            QPushButton {
                color: #ffffff;
                background: #ec6f9f;
                border: 1px solid #ec6f9f;
                border-radius: 14px;
                min-height: 38px;
                padding: 7px 12px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover { background: #df5d91; }
            """
            .replace("__FONT_FAMILY__", font_family)
        )

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(12)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("ReportScroll")
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll_area, stretch=1)

        content = QWidget()
        content.setObjectName("ReportContent")
        scroll_area.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        title = QLabel("今日健康工作報告")
        title.setObjectName("Title")
        date_label = QLabel(f"日期：{self.summary.date}")
        date_label.setObjectName("Subtle")
        layout.addWidget(title)
        layout.addWidget(date_label)

        score_card = _make_card()
        score_layout = QVBoxLayout(score_card)
        score_layout.setContentsMargins(18, 16, 18, 16)
        score_layout.setSpacing(8)
        score_title = QLabel("健康度評分")
        score_title.setObjectName("Section")
        score = QLabel(f"{self.summary.health_score} / 100")
        score.setObjectName("Score")
        score.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(score_title)
        score_layout.addWidget(score)
        layout.addWidget(score_card)

        metrics_card = _make_card()
        metrics_layout = QGridLayout(metrics_card)
        metrics_layout.setContentsMargins(16, 16, 16, 16)
        metrics_layout.setHorizontalSpacing(14)
        metrics_layout.setVerticalSpacing(12)
        metrics = [
            ("工作總時間", _format_minutes(self.summary.work_minutes)),
            ("休息總時間", _format_minutes(self.summary.break_minutes)),
            ("休息次數", f"{self.summary.break_count} 次"),
            ("平均工作時長", _format_average_work(self.summary)),
            ("喝水總量", f"{self.summary.water_ml} ml"),
            ("基本喝水目標", f"{self.summary.basic_water_target_ml} ml"),
            ("理想喝水目標", f"{self.summary.ideal_water_target_ml} ml"),
            ("建議休息總量", _format_minutes(self.summary.recommended_break_minutes)),
        ]
        for index, (label, value) in enumerate(metrics):
            _add_metric(metrics_layout, label, value, index // 2, index % 2)
        for column in range(2):
            metrics_layout.setColumnStretch(column, 1)
        layout.addWidget(metrics_card)

        suggestions_card = _make_card()
        suggestions_layout = QVBoxLayout(suggestions_card)
        suggestions_layout.setContentsMargins(16, 16, 16, 16)
        suggestions_layout.setSpacing(9)
        suggestions_title = QLabel("健康建議")
        suggestions_title.setObjectName("Section")
        suggestions_layout.addWidget(suggestions_title)
        for suggestion in self.summary.suggestions or ["今天沒有可用建議。"]:
            item = QLabel(f"• {suggestion}")
            item.setWordWrap(True)
            item.setObjectName("Subtle")
            suggestions_layout.addWidget(item)
        layout.addWidget(suggestions_card, stretch=1)

        close_button = QPushButton("關閉")
        close_button.clicked.connect(dialog.accept)
        main_layout.addWidget(close_button)

        _position_dialog(dialog, self.parent)
        dialog.exec_()


def format_daily_summary_report(summary: DailySummary) -> str:
    average_work = _format_average_work(summary)
    suggestions = "\n".join(f"- {suggestion}" for suggestion in summary.suggestions)

    return "\n".join(
        [
            f"日期：{summary.date}",
            f"工作總時間：{_format_minutes(summary.work_minutes)}",
            f"休息總時間：{_format_minutes(summary.break_minutes)}",
            f"休息次數：{summary.break_count} 次",
            f"平均每次工作時長：{average_work}",
            f"喝水總量：{summary.water_ml} ml",
            f"基本喝水目標：{summary.basic_water_target_ml} ml",
            f"理想喝水目標：{summary.ideal_water_target_ml} ml",
            f"建議休息總量：{_format_minutes(summary.recommended_break_minutes)}",
            f"健康度評分：{summary.health_score} / 100",
            "",
            "建議：",
            suggestions if suggestions else "- 今天沒有可用建議。",
        ]
    )


def _make_card() -> QFrame:
    card = QFrame()
    card.setObjectName("Card")
    return card


def _add_metric(
    parent_layout: QGridLayout,
    label: str,
    value: str,
    row: int,
    column: int,
) -> None:
    metric = QFrame()
    metric.setMinimumHeight(62)
    metric_layout = QVBoxLayout(metric)
    metric_layout.setContentsMargins(8, 7, 8, 7)
    metric_layout.setSpacing(4)
    label_widget = QLabel(label)
    label_widget.setObjectName("MetricLabel")
    value_widget = QLabel(value)
    value_widget.setObjectName("MetricValue")
    metric_layout.addWidget(label_widget)
    metric_layout.addWidget(value_widget)
    parent_layout.addWidget(metric, row, column)


def _position_dialog(dialog: QDialog, parent: QWidget) -> None:
    parent_geometry = parent.geometry()
    x = parent_geometry.x() + max(0, (parent_geometry.width() - REPORT_DIALOG_WIDTH) // 2)
    y = parent_geometry.y() + max(0, (parent_geometry.height() - REPORT_DIALOG_HEIGHT) // 2)
    dialog.move(x, y)


def _format_minutes(minutes: int) -> str:
    normalized_minutes = max(0, int(minutes))
    hours, remaining_minutes = divmod(normalized_minutes, 60)

    if hours:
        return f"{hours} 小時 {remaining_minutes} 分鐘"
    return f"{remaining_minutes} 分鐘"


def _format_average_work(summary: DailySummary) -> str:
    if summary.average_work_session_minutes is None:
        return "N/A"
    return f"{summary.average_work_session_minutes:.0f} 分鐘"

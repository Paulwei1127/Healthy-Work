"""Shared Lottie-first animation widgets with GIF fallback."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    from PyQt5.QtCore import QSize, Qt, QUrl
    from PyQt5.QtGui import QColor, QMovie
    from PyQt5.QtWidgets import QLabel, QStackedLayout, QVBoxLayout, QWidget
except ImportError as exc:  # pragma: no cover - depends on local installation.
    raise RuntimeError(
        "PyQt5 is required for the current UI. "
        "Install it with: pip install -r requirements.txt"
    ) from exc

try:  # pragma: no cover - optional dependency, covered through fallback tests.
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover - depends on local installation.
    QWebEngineView = None  # type: ignore[assignment]


LOTTIE_WEB_PLAYER_PATH = "gif/json/lottie.min.js"


def get_resource_path(relative_path: str) -> Path:
    """Return a resource path for normal runs and PyInstaller bundles."""
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base_path / relative_path


def can_use_web_engine() -> bool:
    if QWebEngineView is None:
        return False

    return os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen"


class LottieAnimationWidget(QWidget):
    """Optional Lottie player backed by QtWebEngine and local lottie-web."""

    def __init__(self, box_size: QSize, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(box_size)
        self._box_size = box_size
        self._view = None
        self._loaded_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if can_use_web_engine():
            try:
                self._view = QWebEngineView(self)  # type: ignore[operator]
            except RuntimeError:
                self._view = None

        if self._view is not None:
            self._view.setFixedSize(box_size)
            self._view.setContextMenuPolicy(Qt.NoContextMenu)
            self._view.setStyleSheet("background: transparent; border: 0;")
            self._view.setAttribute(Qt.WA_TranslucentBackground, True)
            try:
                self._view.page().setBackgroundColor(QColor(Qt.transparent))
            except RuntimeError:
                self._view = None
            else:
                layout.addWidget(self._view)

        self.hide()

    def load_lottie(self, animation_path: Path) -> bool:
        if self._view is None:
            return False

        player_path = get_resource_path(LOTTIE_WEB_PLAYER_PATH)
        if not player_path.exists() or not animation_path.exists():
            return False

        try:
            player_script = player_path.read_text(encoding="utf-8")
            animation_data = json.dumps(
                json.loads(animation_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError):
            return False

        try:
            self._view.setHtml(
                _build_lottie_html(player_script, animation_data, self._box_size),
                QUrl.fromLocalFile(str(animation_path.parent.resolve()) + "/"),
            )
        except RuntimeError:
            return False

        self._loaded_path = animation_path
        self.show()
        return True

    def clear(self) -> None:
        self._loaded_path = None
        if self._view is not None:
            try:
                self._view.setHtml("")
            except RuntimeError:
                pass
        self.hide()


class LottieGifAnimationWidget(QWidget):
    """Fixed-size Lottie player that falls back to a GIF or blank state."""

    def __init__(self, box_size: QSize, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AnimationContainer")
        self.setFixedSize(box_size)
        self._box_size = box_size
        self.mode: str | None = None
        self.movie: QMovie | None = None

        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.setSpacing(0)

        self.gif_label = QLabel()
        self.gif_label.setObjectName("AnimationLabel")
        self.gif_label.setFixedSize(box_size)
        self.gif_label.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(self.gif_label)

        self.lottie_view = LottieAnimationWidget(box_size, self)
        self.stack.addWidget(self.lottie_view)

    def load(
        self,
        lottie_relative_path: str | None,
        gif_relative_path: str | None,
    ) -> str:
        self.clear()

        if lottie_relative_path and self._start_lottie(lottie_relative_path):
            self.mode = "lottie"
            return self.mode

        if gif_relative_path and self._start_gif(gif_relative_path):
            self.mode = "gif"
            return self.mode

        self.mode = "blank"
        return self.mode

    def clear(self) -> None:
        if self.movie is not None:
            self.movie.stop()
            self.movie = None

        self.lottie_view.clear()
        self.gif_label.clear()
        self.mode = None

    def _start_lottie(self, relative_path: str) -> bool:
        lottie_path = get_resource_path(relative_path)
        if not self.lottie_view.load_lottie(lottie_path):
            return False

        self.stack.setCurrentWidget(self.lottie_view)
        return True

    def _start_gif(self, relative_path: str) -> bool:
        gif_path = get_resource_path(relative_path)
        if not gif_path.exists():
            return False

        movie = QMovie(str(gif_path))
        if not movie.isValid():
            return False

        movie.jumpToFrame(0)
        source_size = movie.currentPixmap().size()
        if source_size.isEmpty():
            source_size = movie.frameRect().size()
        movie.setScaledSize(fit_animation_size(source_size, self._box_size))
        self.gif_label.setMovie(movie)
        self.movie = movie
        self.stack.setCurrentWidget(self.gif_label)
        movie.start()
        return True


def _build_lottie_html(player_script: str, animation_data: str, box_size: QSize) -> str:
    html = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        html, body {
          width: __WIDTH__px;
          height: __HEIGHT__px;
          margin: 0;
          padding: 0;
          overflow: hidden;
          background: transparent;
        }
        body {
          display: flex;
          align-items: center;
          justify-content: center;
        }
        #animation {
          width: __WIDTH__px;
          height: __HEIGHT__px;
        }
        #animation svg {
          max-width: 100%;
          max-height: 100%;
        }
      </style>
    </head>
    <body>
      <div id="animation"></div>
      <script>
        __PLAYER_SCRIPT__
      </script>
      <script>
        const animationData = __ANIMATION_DATA__;
        lottie.loadAnimation({
          container: document.getElementById("animation"),
          renderer: "svg",
          loop: true,
          autoplay: true,
          animationData: animationData,
          rendererSettings: {
            preserveAspectRatio: "xMidYMid meet"
          }
        });
      </script>
    </body>
    </html>
    """
    return (
        html.replace("__WIDTH__", str(box_size.width()))
        .replace("__HEIGHT__", str(box_size.height()))
        .replace("__PLAYER_SCRIPT__", player_script)
        .replace("__ANIMATION_DATA__", animation_data)
    )


def fit_animation_size(source_size: QSize, target_size: QSize) -> QSize:
    source_width = source_size.width()
    source_height = source_size.height()
    target_width = target_size.width()
    target_height = target_size.height()

    if source_width <= 0 or source_height <= 0:
        return target_size

    scale = min(target_width / source_width, target_height / source_height)
    return QSize(
        max(1, int(source_width * scale)),
        max(1, int(source_height * scale)),
    )

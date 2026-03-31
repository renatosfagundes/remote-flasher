"""
Reusable UI widgets — LogWidget, StatusIndicator.
"""
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit, QLabel


class LogWidget(QPlainTextEdit):
    """Read-only log output area with optional autoscroll."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 9))
        self.setMaximumBlockCount(5000)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #3c3c3c;"
        )
        self._autoscroll = True

    @property
    def autoscroll(self):
        return self._autoscroll

    @autoscroll.setter
    def autoscroll(self, value: bool):
        self._autoscroll = value

    def append_log(self, text: str):
        self.appendPlainText(text)
        if self._autoscroll:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class StatusIndicator(QLabel):
    """Small colored circle to indicate connection status."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.set_status("disconnected")

    def set_status(self, status):
        colors = {
            "disconnected": "#ff4444",
            "connecting": "#ffaa00",
            "connected": "#44ff44",
        }
        color = colors.get(status, "#888888")
        self.setStyleSheet(
            f"background-color: {color}; border-radius: 8px; border: 1px solid #555;"
        )

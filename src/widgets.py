"""
Reusable UI widgets — LogWidget, StatusIndicator, ToggleSwitch, helpers.
"""
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, Property, QRectF, QSize,
)
from PySide6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor, QPainter, QBrush
from PySide6.QtWidgets import (
    QPlainTextEdit, QLabel, QHBoxLayout, QPushButton, QWidget, QVBoxLayout,
    QAbstractButton,
)


class LogWidget(QPlainTextEdit):
    """Read-only log output area with optional autoscroll.

    Supports per-operation coloring via append_op(op_id, text): each distinct
    op_id is assigned a rotating color so output from concurrent workers is
    visually separable even when lines interleave in one pane.
    """

    _PALETTE = (
        "#4fc3f7", "#ffb74d", "#81c784", "#e57373",
        "#ba68c8", "#4dd0e1", "#fff176", "#f06292",
    )

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
        self._op_colors: dict[int, str] = {}
        self._palette_idx = 0

    @property
    def autoscroll(self):
        return self._autoscroll

    @autoscroll.setter
    def autoscroll(self, value: bool):
        self._autoscroll = value

    def _color_for(self, op_id: int) -> str:
        if op_id not in self._op_colors:
            self._op_colors[op_id] = self._PALETTE[self._palette_idx % len(self._PALETTE)]
            self._palette_idx += 1
        return self._op_colors[op_id]

    def _scroll_to_bottom(self):
        if self._autoscroll:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def append_log(self, text: str):
        self.appendPlainText(text)
        self._scroll_to_bottom()

    def append_op(self, op_id: int, text: str):
        # Cursor-based insertion (instead of appendHtml) keeps whitespace
        # intact — avrdude's progress bars rely on runs of spaces that an
        # HTML rendering path would collapse.
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        if cursor.position() > 0:
            cursor.insertText("\n")
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self._color_for(op_id)))
        cursor.insertText(text, fmt)
        self._scroll_to_bottom()


def make_log_with_clear(parent_layout, max_height=None):
    """Create a LogWidget with a 'Clear Log' button and add to parent_layout.
    Returns the LogWidget instance."""
    header = QHBoxLayout()
    header.addStretch()
    clear_btn = QPushButton("Clear Log")
    clear_btn.setFixedHeight(22)
    clear_btn.setStyleSheet(
        "QPushButton { background: #333; color: #aaa; border: 1px solid #555; "
        "border-radius: 2px; padding: 2px 10px; font-size: 10px; }"
        "QPushButton:hover { background: #444; color: #ddd; }"
    )
    header.addWidget(clear_btn)
    parent_layout.addLayout(header)

    log = LogWidget()
    if max_height:
        log.setMaximumHeight(max_height)
    clear_btn.clicked.connect(log.clear)
    parent_layout.addWidget(log)
    return log


class ToggleSwitch(QAbstractButton):
    """iOS-style slide toggle with optional text label.

    Drop-in replacement for QCheckBox's toggled API: isChecked, setChecked,
    toggled signal, setEnabled, blockSignals, setToolTip all work.
    """
    _TRACK_W = 40
    _TRACK_H = 20
    _PADDING = 2
    _TEXT_GAP = 8

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = text
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._thumb_pos = float(self._PADDING)
        self._anim = QPropertyAnimation(self, b"thumbPos", self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.toggled.connect(self._animate)

    def _get_thumb_pos(self):
        return self._thumb_pos

    def _set_thumb_pos(self, v):
        self._thumb_pos = v
        self.update()

    thumbPos = Property(float, _get_thumb_pos, _set_thumb_pos)

    def _thumb_end(self, checked):
        return (self._TRACK_W - self._TRACK_H + self._PADDING) if checked else self._PADDING

    def _animate(self, checked):
        self._anim.stop()
        self._anim.setEndValue(float(self._thumb_end(checked)))
        self._anim.start()

    def sizeHint(self):
        fm = self.fontMetrics()
        text_w = (fm.horizontalAdvance(self._text) + self._TEXT_GAP) if self._text else 0
        return QSize(self._TRACK_W + text_w, max(self._TRACK_H, fm.height()))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            track, thumb, text_c = QColor("#2a2a2a"), QColor("#555"), QColor("#666")
        elif self.isChecked():
            track, thumb, text_c = QColor("#2d7cd6"), QColor("#ffffff"), QColor("#ddd")
        else:
            track, thumb, text_c = QColor("#555"), QColor("#bbb"), QColor("#ccc")

        track_y = (self.height() - self._TRACK_H) // 2
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(track))
        p.drawRoundedRect(
            QRectF(0, track_y, self._TRACK_W, self._TRACK_H),
            self._TRACK_H / 2, self._TRACK_H / 2,
        )

        d = self._TRACK_H - (2 * self._PADDING)
        p.setBrush(QBrush(thumb))
        p.drawEllipse(QRectF(self._thumb_pos, track_y + self._PADDING, d, d))

        if self._text:
            p.setPen(text_c)
            text_x = self._TRACK_W + self._TEXT_GAP
            p.drawText(
                QRectF(text_x, 0, self.width() - text_x, self.height()),
                int(Qt.AlignLeft | Qt.AlignVCenter),
                self._text,
            )

    def resizeEvent(self, e):
        # Snap thumb to the correct end on resize / first show.
        self._thumb_pos = float(self._thumb_end(self.isChecked()))
        super().resizeEvent(e)


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

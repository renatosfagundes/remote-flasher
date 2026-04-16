"""
Python port of RadialBar — a QQuickPaintedItem that draws a circular
progress arc.  Original C++ by cppqtdev (Qt-HMI-Display-UI).
"""
from PySide6.QtCore import Property, Signal, Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtQuick import QQuickPaintedItem


class RadialBar(QQuickPaintedItem):
    # ── Signals ──────────────────────────────────────────────────────
    sizeChanged = Signal()
    startAngleChanged = Signal()
    spanAngleChanged = Signal()
    minValueChanged = Signal()
    maxValueChanged = Signal()
    valueChanged = Signal()
    dialWidthChanged = Signal()
    backgroundColorChanged = Signal()
    foregroundColorChanged = Signal()
    progressColorChanged = Signal()
    textColorChanged = Signal()
    suffixTextChanged = Signal()
    penStyleChanged = Signal()
    dialTypeChanged = Signal()
    textFontChanged = Signal()

    # ── DialType enum (mirrored in QML via Q_ENUM) ──────────────────
    FullDial = 0
    MinToMax = 1
    NoDial = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._size = 200.0
        self._startAngle = 40.0
        self._spanAngle = 280.0
        self._minValue = 0.0
        self._maxValue = 100.0
        self._value = 50.0
        self._dialWidth = 15
        self._backgroundColor = QColor(Qt.transparent)
        self._dialColor = QColor(80, 80, 80)
        self._progressColor = QColor(135, 26, 5)
        self._textColor = QColor(0, 0, 0)
        self._suffixText = ""
        self._showText = True
        self._penStyle = Qt.FlatCap
        self._dialType = self.MinToMax
        self._textFont = QFont()

        self.setWidth(200)
        self.setHeight(200)
        self.setSmooth(True)
        self.setAntialiasing(True)

    # ── QPainter rendering ───────────────────────────────────────────
    def paint(self, painter: QPainter):
        w = self.width()
        h = self.height()
        size = min(w, h)
        x = (w - size) / 2.0
        y = (h - size) / 2.0
        rect = QRectF(x, y, size, size)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen()
        # QML sends penStyle as int; cast to the enum Qt expects.
        try:
            pen.setCapStyle(Qt.PenCapStyle(self._penStyle))
        except (TypeError, ValueError):
            pen.setCapStyle(Qt.FlatCap)

        startAngle = -90.0 - self._startAngle
        spanAngle = -360.0 if self._dialType == self.FullDial else -self._spanAngle

        # Draw outer dial
        offset = self._dialWidth / 2.0
        adj = rect.adjusted(offset, offset, -offset, -offset)
        if self._dialType == self.MinToMax:
            pen.setWidthF(self._dialWidth)
            pen.setColor(self._dialColor)
            painter.setPen(pen)
            painter.drawArc(adj, int(startAngle * 16), int(spanAngle * 16))
        elif self._dialType == self.FullDial:
            pen.setWidthF(self._dialWidth)
            pen.setColor(self._dialColor)
            painter.setPen(pen)
            painter.drawArc(adj, int(-90 * 16), int(-360 * 16))

        # Draw background fill
        inner = offset * 2
        painter.setBrush(self._backgroundColor)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rect.adjusted(inner, inner, -inner, -inner))

        # Draw text
        painter.setFont(self._textFont)
        pen.setColor(self._textColor)
        painter.setPen(pen)
        if self._showText:
            painter.drawText(adj, Qt.AlignCenter,
                             f"{self._value:.0f}{self._suffixText}")
        else:
            painter.drawText(adj, Qt.AlignCenter, self._suffixText)

        # Draw progress arc
        if self._maxValue != self._minValue:
            valueAngle = ((self._value - self._minValue)
                          / (self._maxValue - self._minValue)) * spanAngle
        else:
            valueAngle = 0
        pen.setWidthF(self._dialWidth)
        pen.setColor(self._progressColor)
        painter.setPen(pen)
        painter.drawArc(adj, int(startAngle * 16), int(valueAngle * 16))

    # ── Property getters / setters ───────────────────────────────────
    def getSize(self):
        return self._size

    def setSize(self, v):
        if self._size == v:
            return
        self._size = v
        self.sizeChanged.emit()

    def getStartAngle(self):
        return self._startAngle

    def setStartAngle(self, v):
        if self._startAngle == v:
            return
        self._startAngle = v
        self.startAngleChanged.emit()

    def getSpanAngle(self):
        return self._spanAngle

    def setSpanAngle(self, v):
        if self._spanAngle == v:
            return
        self._spanAngle = v
        self.spanAngleChanged.emit()

    def getMinValue(self):
        return self._minValue

    def setMinValue(self, v):
        if self._minValue == v:
            return
        self._minValue = v
        self.minValueChanged.emit()

    def getMaxValue(self):
        return self._maxValue

    def setMaxValue(self, v):
        if self._maxValue == v:
            return
        self._maxValue = v
        self.maxValueChanged.emit()

    def getValue(self):
        return self._value

    def setValue(self, v):
        if self._value == v:
            return
        self._value = v
        self.update()
        self.valueChanged.emit()

    def getDialWidth(self):
        return self._dialWidth

    def setDialWidth(self, v):
        if self._dialWidth == v:
            return
        self._dialWidth = int(v)
        self.dialWidthChanged.emit()

    def getBackgroundColor(self):
        return self._backgroundColor

    def setBackgroundColor(self, v):
        if self._backgroundColor == v:
            return
        self._backgroundColor = QColor(v)
        self.backgroundColorChanged.emit()

    def getForegroundColor(self):
        return self._dialColor

    def setForegroundColor(self, v):
        if self._dialColor == v:
            return
        self._dialColor = QColor(v)
        self.foregroundColorChanged.emit()

    def getProgressColor(self):
        return self._progressColor

    def setProgressColor(self, v):
        if self._progressColor == v:
            return
        self._progressColor = QColor(v)
        self.progressColorChanged.emit()

    def getTextColor(self):
        return self._textColor

    def setTextColor(self, v):
        if self._textColor == v:
            return
        self._textColor = QColor(v)
        self.textColorChanged.emit()

    def getSuffixText(self):
        return self._suffixText

    def setSuffixText(self, v):
        if self._suffixText == v:
            return
        self._suffixText = v
        self.suffixTextChanged.emit()

    def isShowText(self):
        return self._showText

    def setShowText(self, v):
        if self._showText == v:
            return
        self._showText = v

    def getPenStyle(self):
        return self._penStyle

    def setPenStyle(self, v):
        v = int(v)
        if self._penStyle == v:
            return
        self._penStyle = v
        self.penStyleChanged.emit()

    def getDialType(self):
        return self._dialType

    def setDialType(self, v):
        if self._dialType == v:
            return
        self._dialType = v
        self.dialTypeChanged.emit()

    def getTextFont(self):
        return self._textFont

    def setTextFont(self, v):
        if self._textFont == v:
            return
        self._textFont = v
        self.textFontChanged.emit()

    # ── Qt Properties (exposed to QML) ───────────────────────────────
    size = Property(float, getSize, setSize, notify=sizeChanged)
    startAngle = Property(float, getStartAngle, setStartAngle, notify=startAngleChanged)
    spanAngle = Property(float, getSpanAngle, setSpanAngle, notify=spanAngleChanged)
    minValue = Property(float, getMinValue, setMinValue, notify=minValueChanged)
    maxValue = Property(float, getMaxValue, setMaxValue, notify=maxValueChanged)
    value = Property(float, getValue, setValue, notify=valueChanged)
    dialWidth = Property(int, getDialWidth, setDialWidth, notify=dialWidthChanged)
    backgroundColor = Property(QColor, getBackgroundColor, setBackgroundColor, notify=backgroundColorChanged)
    foregroundColor = Property(QColor, getForegroundColor, setForegroundColor, notify=foregroundColorChanged)
    progressColor = Property(QColor, getProgressColor, setProgressColor, notify=progressColorChanged)
    textColor = Property(QColor, getTextColor, setTextColor, notify=textColorChanged)
    suffixText = Property(str, getSuffixText, setSuffixText, notify=suffixTextChanged)
    showText = Property(bool, isShowText, setShowText)
    penStyle = Property(int, getPenStyle, setPenStyle, notify=penStyleChanged)
    dialType = Property(int, getDialType, setDialType, notify=dialTypeChanged)
    textFont = Property(QFont, getTextFont, setTextFont, notify=textFontChanged)

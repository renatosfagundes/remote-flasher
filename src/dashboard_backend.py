"""Dashboard backend — shared data parser, Qt properties for QML, CSV logging."""

import csv
import time
from collections import deque
from datetime import datetime

from PySide6.QtCore import QObject, QPointF, QTimer, Property, Signal, Slot


MAX_CHANNELS = 16
RING_BUFFER_SIZE = 2000
BATCH_INTERVAL_MS = 30


class DashboardBackend(QObject):
    """Central data hub consumed by both GaugesTab and PlotsTab.

    Receives raw serial lines via ``onSerialLine``, parses CSV numeric data,
    and exposes the latest values as Qt properties for QML gauge bindings.
    Maintains per-channel ring buffers that QML chart series can pull from.
    Optionally logs every sample to a timestamped CSV file.
    """

    channelsUpdated = Signal()
    channelCountChanged = Signal(int)
    loggingChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: list[float] = []
        self._channel_count: int = 0
        self._dirty: bool = False

        # Per-channel ring buffers (index → deque of float)
        self._series_buffers: list[deque] = [
            deque(maxlen=RING_BUFFER_SIZE) for _ in range(MAX_CHANNELS)
        ]
        # Global sample counter used as X axis for charts
        self._sample_index: int = 0

        # CSV logging state
        self._csv_file = None
        self._csv_writer = None
        self._logging: bool = False

        # Batch timer — fires at ~33 fps, emits channelsUpdated only if new
        # data arrived since last tick.
        self._batch_timer = QTimer(self)
        self._batch_timer.setInterval(BATCH_INTERVAL_MS)
        self._batch_timer.timeout.connect(self._on_batch_tick)
        self._batch_timer.start()

    # ------------------------------------------------------------------
    # Qt Properties (read by QML)
    # ------------------------------------------------------------------

    @Property("QVariantList", notify=channelsUpdated)
    def channelValues(self) -> list:
        return list(self._values)

    @Property(int, notify=channelCountChanged)
    def channelCount(self) -> int:
        return self._channel_count

    @Property(bool, notify=loggingChanged)
    def isLogging(self) -> bool:
        return self._logging

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(str)
    def onSerialLine(self, line: str):
        """Parse a single serial output line.  Called from SerialWorker.output."""
        stripped = line.strip()
        if not stripped:
            return
        # Skip non-data lines (status messages, VIO commands, prompts)
        if stripped[0] in ("[", "!", ">", "#"):
            return

        parts = stripped.split(",")
        try:
            values = [float(p.strip()) for p in parts]
        except ValueError:
            return  # not numeric CSV

        # Update channel count if it changed
        if len(values) != self._channel_count:
            self._channel_count = len(values)
            self.channelCountChanged.emit(self._channel_count)

        self._values = values
        self._dirty = True

        # Append to ring buffers
        for i, v in enumerate(values):
            if i < MAX_CHANNELS:
                self._series_buffers[i].append(v)
        self._sample_index += 1

        # CSV logging
        if self._csv_writer is not None:
            ts = time.time()
            self._csv_writer.writerow([f"{ts:.3f}"] + [str(v) for v in values])

    @Slot(str)
    def startLogging(self, filepath: str):
        """Open a CSV file and begin writing samples."""
        try:
            self._csv_file = open(filepath, "w", newline="", encoding="utf-8")
            self._csv_writer = csv.writer(self._csv_file)
            headers = ["timestamp"] + [f"ch{i}" for i in range(max(self._channel_count, 1))]
            self._csv_writer.writerow(headers)
            self._logging = True
            self.loggingChanged.emit(True)
        except OSError:
            self._csv_file = None
            self._csv_writer = None

    @Slot()
    def stopLogging(self):
        """Flush and close the CSV log file."""
        if self._csv_file is not None:
            try:
                self._csv_file.close()
            except OSError:
                pass
            self._csv_file = None
            self._csv_writer = None
        self._logging = False
        self.loggingChanged.emit(False)

    @Slot(int, "QVariant", result="QVariantMap")
    def updateSeriesFromChannel(self, channel: int, series_obj):
        """Replace *series_obj* data with the ring buffer for *channel*.

        Called from QML: ``backend.updateSeriesFromChannel(ch, mySeries)``.
        Returns ``{minY, maxY, minX, maxX}`` for axis auto-scaling.
        """
        empty = {"minY": 0, "maxY": 100, "minX": 0, "maxX": 500}
        if channel < 0 or channel >= MAX_CHANNELS:
            return empty
        buf = self._series_buffers[channel]
        n = len(buf)
        if n == 0:
            return empty

        start = self._sample_index - n
        points = [QPointF(float(start + i), v) for i, v in enumerate(buf)]
        series_obj.replace(points)

        min_y = min(buf)
        max_y = max(buf)
        return {
            "minY": min_y,
            "maxY": max_y,
            "minX": float(start),
            "maxX": float(self._sample_index),
        }

    @Slot()
    def reset(self):
        """Clear all buffers and counters."""
        self._values.clear()
        self._channel_count = 0
        self._sample_index = 0
        for buf in self._series_buffers:
            buf.clear()
        self._dirty = False
        self.channelCountChanged.emit(0)
        self.channelsUpdated.emit()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_batch_tick(self):
        if self._dirty:
            self._dirty = False
            self.channelsUpdated.emit()

    @staticmethod
    def default_log_path() -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"dashboard_{ts}.csv"

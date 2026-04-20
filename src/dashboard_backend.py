"""Dashboard backend — shared data parser, Qt properties for QML, CSV logging."""

import csv
import time
from collections import deque
from datetime import datetime

from PySide6.QtCore import QObject, QPointF, QTimer, Property, Signal, Slot

# Re-use the plotter's name→bridge-property map so the Dashboard and Plotter
# feeds route identical signal names to the same gauges.
from plotter.plotter_backend import _DASHBOARD_PROPS


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

        # HMI bridge reference — set by MainWindow so named signals ($name:val)
        # can be pushed directly to the gauges, matching the plotter's path.
        self._dashboard_bridge = None

        # Batch timer — fires at ~33 fps, emits channelsUpdated only if new
        # data arrived since last tick.
        self._batch_timer = QTimer(self)
        self._batch_timer.setInterval(BATCH_INTERVAL_MS)
        self._batch_timer.timeout.connect(self._on_batch_tick)
        self._batch_timer.start()

    def set_dashboard_bridge(self, bridge):
        """Wire the HMI bridge so named signals update gauge properties."""
        self._dashboard_bridge = bridge

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
        """Parse a single serial output line.  Called from SerialWorker.output.

        Accepts the same '$'-prefixed convention as the Plotter:
          - Named:      $rpm:4000,speed:100,checkEngine:1
          - Positional: $4000,100,1
        Named signals whose name matches the HMI bridge map auto-route to
        the Dashboard gauges/warnings/doors.
        """
        stripped = line.strip()
        if not stripped:
            return
        if not stripped.startswith("$"):
            return
        payload = stripped[1:].strip()
        if not payload:
            return

        # Named ($name:value,...) vs positional ($1.0,2.0,3.0)
        if ":" in payload and not payload[0].isdigit() and payload[0] != "-":
            self._parse_named(payload)
        else:
            self._parse_csv(payload)

    def _route_to_bridge(self, name: str, value: float):
        """Push a named signal to the HMI bridge if its name is recognized."""
        if self._dashboard_bridge is None:
            return
        prop = _DASHBOARD_PROPS.get(name.lower())
        if prop is None:
            return
        try:
            setattr(self._dashboard_bridge, prop, value)
        except Exception:
            pass

    def _parse_named(self, payload: str):
        """Parse key:value,key:value and route each recognized name."""
        for pair in payload.split(","):
            pair = pair.strip()
            if ":" not in pair:
                continue
            key, val_str = pair.split(":", 1)
            try:
                self._route_to_bridge(key.strip(), float(val_str.strip()))
            except ValueError:
                continue

    def _parse_csv(self, payload: str):
        """Parse positional CSV and update channelValues + ring buffers."""
        parts = payload.split(",")
        try:
            values = [float(p.strip()) for p in parts]
        except ValueError:
            return

        if len(values) != self._channel_count:
            self._channel_count = len(values)
            self.channelCountChanged.emit(self._channel_count)

        self._values = values
        self._dirty = True

        for i, v in enumerate(values):
            if i < MAX_CHANNELS:
                self._series_buffers[i].append(v)
        self._sample_index += 1

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

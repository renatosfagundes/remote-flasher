"""Plotter data backend — receives serial lines, parses named or CSV signals.

Supports two formats:
  Named:      speed:50.0,rpm:7200,coolantTemp:85.5
  Positional:  50.0,7200,85.5  (columns become CH0, CH1, CH2)

Named signals that match HMI dashboard property names are auto-routed
to the dashboard backend.
"""
import time

from PySide6.QtCore import QObject, Signal, Slot

from plotter.ring_buffer import RingBuffer
from plotter.signal_config import SignalConfig


DEFAULT_CAPACITY = 50_000


def is_signal_line(line: str) -> bool:
    """True if `line` is a dashboard/plotter signal message ('$' prefix)
    or a VIO command ('!' prefix). Used by the serial terminal's
    'Filter signals' option to hide these lines from the log."""
    s = line.strip()
    return s.startswith("$") or s.startswith("!")

# Dashboard property names that can be auto-routed from named serial signals.
# Maps signal_name (lowercase) → bridge property name.
_DASHBOARD_PROPS = {
    "speed": "speed",
    "rpm": "rpm",
    "coolanttemp": "coolantTemp",
    "fuellevel": "fuelLevel",
    "battery": "battery",
    "power": "power",
    "rangekm": "rangeKm",
    "distance": "distance",
    "avgspeed": "avgSpeed",
    "gear": "gear",
    "manualgear": "manualGear",
    # Doors
    "doorfl": "doorFL", "doorfr": "doorFR",
    "doorrl": "doorRL", "doorrr": "doorRR",
    "trunk": "trunk", "hood": "hood",
    # Warning lights
    "checkengine": "checkEngine", "oilpressure": "oilPressure",
    "batterywarn": "batteryWarn", "brakewarn": "brakeWarn",
    "abswarn": "absWarn", "airbagwarn": "airbagWarn",
    # Status lights
    "parkinglights": "parkingLights", "lowbeam": "lowBeam",
    "highbeam": "highBeam", "foglights": "fogLights",
    "seatbeltunbuckled": "seatbeltUnbuckled",
    "turnleft": "turnLeft", "turnright": "turnRight",
    "cruiseactive": "cruiseActive", "ecomode": "ecoMode",
    "evcharging": "evCharging",
    "servicedue": "serviceDue", "tirepressure": "tirePressure",
    "dooropen": "doorOpen", "tractioncontrol": "tractionControl",
}


class PlotterBackend(QObject):
    """Parses serial lines (named or CSV), stores ring buffers, routes to dashboard.

    Signals:
        channelCountChanged(int) — channel count changed.
        signalDiscovered(str) — a new named signal was found.
    """
    channelCountChanged = Signal(int)
    signalDiscovered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._signal_names: list[str] = []         # ordered signal names
        self._name_to_index: dict[str, int] = {}   # name → buffer index
        self._time_buf = RingBuffer(DEFAULT_CAPACITY)
        self._channel_bufs: list[RingBuffer] = []
        self._configs: list[SignalConfig] = []
        self._t0: float | None = None
        self._dirty = False
        self._paused = False
        self._dashboard_bridge = None  # set by MainWindow

    def set_dashboard_bridge(self, bridge):
        """Set the HMI bridge so named signals can be auto-routed."""
        self._dashboard_bridge = bridge

    @property
    def channel_count(self) -> int:
        return len(self._signal_names)

    @property
    def configs(self) -> list[SignalConfig]:
        return list(self._configs)

    @property
    def paused(self) -> bool:
        return self._paused

    @paused.setter
    def paused(self, v: bool):
        self._paused = v

    def time_buffer(self) -> RingBuffer:
        return self._time_buf

    def channel_buffer(self, index: int) -> RingBuffer:
        if 0 <= index < len(self._channel_bufs):
            return self._channel_bufs[index]
        return RingBuffer(0)

    def signal_names(self) -> list[str]:
        return list(self._signal_names)

    def update_config(self, index: int, cfg: SignalConfig):
        if 0 <= index < len(self._configs):
            self._configs[index] = cfg

    # Above this many signals, newly-discovered ones start hidden to keep the
    # plot readable — users opt in via the signal list checkbox.
    AUTO_HIDE_THRESHOLD = 5

    def _get_or_create_signal(self, name: str) -> int:
        """Return the buffer index for a signal, creating it if new.
        New signals are backfilled with zeros so their buffer aligns with
        time_buf — the caller will then append the current value.
        """
        if name in self._name_to_index:
            return self._name_to_index[name]
        idx = len(self._signal_names)
        # First N signals visible, rest start hidden.
        initial_visible = idx < self.AUTO_HIDE_THRESHOLD
        self._signal_names.append(name)
        self._name_to_index[name] = idx
        buf = RingBuffer(DEFAULT_CAPACITY)
        # Backfill so new signals appear at the correct point in time rather
        # than being misaligned with previously-recorded samples. Target:
        # one short of time_buf.count so the caller's append brings them even.
        target = max(0, self._time_buf.count - 1)
        for _ in range(target):
            buf.append(0.0)
        self._channel_bufs.append(buf)
        self._configs.append(SignalConfig(index=idx, name=name, visible=initial_visible))
        self.signalDiscovered.emit(name)
        self.channelCountChanged.emit(len(self._signal_names))
        return idx

    def _route_to_dashboard(self, name: str, value: float):
        """If the signal name matches a dashboard property, push the value."""
        if self._dashboard_bridge is None:
            return
        prop = _DASHBOARD_PROPS.get(name.lower())
        if prop is None:
            return
        try:
            setattr(self._dashboard_bridge, prop, value)
        except Exception:
            pass

    @Slot(str)
    def onSerialLine(self, line: str):
        """Parse a serial line. Only lines prefixed with '$' are treated as
        signal messages — mirrors the VIO '!' prefix convention so normal
        Serial.print output from user code never accidentally shows up in
        the plot/dashboard.
        """
        stripped = line.strip()
        if not stripped.startswith("$"):
            return
        payload = stripped[1:].strip()
        if not payload:
            return

        # Named format ($speed:50,rpm:7200) vs positional ($1.0,2.0,3.0).
        if ":" in payload and not payload[0].isdigit() and payload[0] != "-":
            self._parse_named(payload)
        else:
            self._parse_csv(payload)

    def _parse_named(self, line: str):
        """Parse key:value,key:value format."""
        # Pre-parse all pairs (cheap) before touching any buffer, so we know
        # which signals are updated this tick and can handle new ones cleanly.
        updates: dict[str, float] = {}
        for pair in line.split(","):
            pair = pair.strip()
            if ":" not in pair:
                continue
            key, val_str = pair.split(":", 1)
            key = key.strip()
            try:
                updates[key] = float(val_str.strip())
            except ValueError:
                continue

        if not updates:
            return

        now = time.perf_counter()
        if self._t0 is None:
            self._t0 = now
        self._time_buf.append(now - self._t0)

        # Create new signals first (they'll be backfilled to align with time_buf).
        for name in updates:
            self._get_or_create_signal(name)

        # Append one value per channel — updated ones get the new value, the
        # rest get their last value held. Invariant: every channel_buf.count
        # equals time_buf.count after this method returns.
        # Dashboard routing is NOT done here — that path belongs to
        # dashboard_backend.onSerialLine so the two feeds stay independent.
        for i, buf in enumerate(self._channel_bufs):
            name = self._signal_names[i]
            if name in updates:
                buf.append(updates[name])
            else:
                arr = buf.get_last(1)
                buf.append(arr[0] if len(arr) > 0 else 0.0)

        self._dirty = True

    def _parse_csv(self, line: str):
        """Parse positional CSV: 1.0,2.0,3.0 → CH0,CH1,CH2."""
        parts = line.split(",")
        try:
            values = [float(p.strip()) for p in parts]
        except ValueError:
            return

        now = time.perf_counter()
        if self._t0 is None:
            self._t0 = now
        self._time_buf.append(now - self._t0)

        for i, v in enumerate(values):
            name = f"CH{i}"
            idx = self._get_or_create_signal(name)
            self._channel_bufs[idx].append(v)

        self._dirty = True

    def check_dirty(self) -> bool:
        if self._dirty:
            self._dirty = False
            return True
        return False

    def reset(self):
        self._time_buf.clear()
        for buf in self._channel_bufs:
            buf.clear()
        self._channel_bufs.clear()
        self._configs.clear()
        self._signal_names.clear()
        self._name_to_index.clear()
        self._t0 = None
        self._dirty = False
        self.channelCountChanged.emit(0)

    def export_csv(self, filepath: str):
        import csv
        t = self._time_buf.get_array()
        n = len(t)
        if n == 0:
            return

        channels = []
        for i in range(len(self._signal_names)):
            arr = self._channel_bufs[i].get_array()
            if len(arr) < n:
                import numpy as np
                arr = np.pad(arr, (0, n - len(arr)), constant_values=0)
            channels.append(arr)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            headers = ["time_s"] + self._signal_names
            writer.writerow(headers)
            for j in range(n):
                row = [f"{t[j]:.4f}"] + [f"{ch[j]:.6g}" for ch in channels]
                writer.writerow(row)

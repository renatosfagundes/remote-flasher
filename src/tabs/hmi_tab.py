"""HMI Dashboard tab — embeds the adaptive car dashboard QML inside a QQuickWidget."""
import os
import sys
import logging

# Suppress harmless "qt.svg: Invalid path data; path truncated" from complex SVGs
logging.getLogger("qt.svg").setLevel(logging.CRITICAL)
os.environ.setdefault("QT_LOGGING_RULES", "qt.svg.warning=false")

from PySide6.QtCore import QObject, QUrl, Signal, Slot, Property
from PySide6.QtQml import qmlRegisterType
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget, QVBoxLayout

from radial_bar import RadialBar
from settings import load_settings, save_settings


# ── Helper to generate boilerplate for many float properties ─────────
def _make_float_prop(attr):
    """Return (getter, setter, signal) for a float QML property."""
    priv = f"_{attr}"
    sig_name = f"{attr}Changed"

    def getter(self):
        return getattr(self, priv)

    def setter(self, v):
        v = float(v)
        if getattr(self, priv) != v:
            setattr(self, priv, v)
            getattr(self, sig_name).emit()

    return getter, setter, sig_name


def _make_bool_prop(attr):
    priv = f"_{attr}"
    sig_name = f"{attr}Changed"

    def getter(self):
        return getattr(self, priv)

    def setter(self, v):
        v = bool(v)
        if getattr(self, priv) != v:
            setattr(self, priv, v)
            getattr(self, sig_name).emit()

    return getter, setter, sig_name


# ── Bridge: exposes all vehicle data as named QML properties ────────
class _HMIBridge(QObject):
    # Float signals
    speedChanged = Signal()
    rpmChanged = Signal()
    coolantTempChanged = Signal()
    fuelLevelChanged = Signal()
    batteryChanged = Signal()
    powerChanged = Signal()
    rangeKmChanged = Signal()
    distanceChanged = Signal()
    avgSpeedChanged = Signal()
    fuelAvgChanged = Signal()
    # Int signal
    gearChanged = Signal()
    # Bool signals (doors)
    doorFLChanged = Signal()
    doorFRChanged = Signal()
    doorRLChanged = Signal()
    doorRRChanged = Signal()
    trunkChanged = Signal()
    hoodChanged = Signal()
    # Mode
    vehicleModeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Float defaults
        self._speed = 0.0
        self._rpm = 0.0
        self._coolantTemp = 25.0
        self._fuelLevel = 50.0
        self._battery = 71.0
        self._power = 0.0
        self._rangeKm = 188.0
        self._distance = 0.0
        self._avgSpeed = 0.0
        self._fuelAvg = 0.0
        # Int
        self._gear = 7  # P
        # Bools (doors)
        self._doorFL = False
        self._doorFR = False
        self._doorRL = False
        self._doorRR = False
        self._trunk = False
        self._hood = False
        # Mode (0=Electric, 1=CombustionAuto, 2=CombustionManual)
        self._vehicleMode = int(load_settings().get("vehicle_mode", 1))

    # ── Float properties ───────────────────────────────────────────
    # speed
    _gs_speed = _make_float_prop("speed")
    speed = Property(float, _gs_speed[0], _gs_speed[1], notify=speedChanged)
    # rpm
    _gs_rpm = _make_float_prop("rpm")
    rpm = Property(float, _gs_rpm[0], _gs_rpm[1], notify=rpmChanged)
    # coolantTemp
    _gs_ct = _make_float_prop("coolantTemp")
    coolantTemp = Property(float, _gs_ct[0], _gs_ct[1], notify=coolantTempChanged)
    # fuelLevel
    _gs_fl = _make_float_prop("fuelLevel")
    fuelLevel = Property(float, _gs_fl[0], _gs_fl[1], notify=fuelLevelChanged)
    # battery
    _gs_bat = _make_float_prop("battery")
    battery = Property(float, _gs_bat[0], _gs_bat[1], notify=batteryChanged)
    # power
    _gs_pow = _make_float_prop("power")
    power = Property(float, _gs_pow[0], _gs_pow[1], notify=powerChanged)
    # rangeKm
    _gs_rng = _make_float_prop("rangeKm")
    rangeKm = Property(float, _gs_rng[0], _gs_rng[1], notify=rangeKmChanged)
    # distance
    _gs_dist = _make_float_prop("distance")
    distance = Property(float, _gs_dist[0], _gs_dist[1], notify=distanceChanged)
    # avgSpeed
    _gs_as = _make_float_prop("avgSpeed")
    avgSpeed = Property(float, _gs_as[0], _gs_as[1], notify=avgSpeedChanged)
    # fuelAvg
    _gs_fa = _make_float_prop("fuelAvg")
    fuelAvg = Property(float, _gs_fa[0], _gs_fa[1], notify=fuelAvgChanged)

    # ── Bool properties (doors) ────────────────────────────────────
    _gs_dfl = _make_bool_prop("doorFL")
    doorFL = Property(bool, _gs_dfl[0], _gs_dfl[1], notify=doorFLChanged)
    _gs_dfr = _make_bool_prop("doorFR")
    doorFR = Property(bool, _gs_dfr[0], _gs_dfr[1], notify=doorFRChanged)
    _gs_drl = _make_bool_prop("doorRL")
    doorRL = Property(bool, _gs_drl[0], _gs_drl[1], notify=doorRLChanged)
    _gs_drr = _make_bool_prop("doorRR")
    doorRR = Property(bool, _gs_drr[0], _gs_drr[1], notify=doorRRChanged)
    _gs_trk = _make_bool_prop("trunk")
    trunk = Property(bool, _gs_trk[0], _gs_trk[1], notify=trunkChanged)
    _gs_hd = _make_bool_prop("hood")
    hood = Property(bool, _gs_hd[0], _gs_hd[1], notify=hoodChanged)

    # ── Gear (int) ─────────────────────────────────────────────────
    def _get_gear(self):
        return self._gear

    def _set_gear(self, v):
        v = int(v)
        if self._gear != v:
            self._gear = v
            self.gearChanged.emit()

    gear = Property(int, _get_gear, _set_gear, notify=gearChanged)

    # ── Vehicle mode (int, persisted) ──────────────────────────────
    def _get_vehicleMode(self):
        return self._vehicleMode

    @Slot(int)
    def setVehicleMode(self, v):
        v = int(v)
        if self._vehicleMode != v:
            self._vehicleMode = v
            save_settings(vehicle_mode=v)
            self.vehicleModeChanged.emit()

    vehicleMode = Property(int, _get_vehicleMode, setVehicleMode, notify=vehicleModeChanged)


# ── Channel → property mapping ───────────────────────────────────────
_DEFAULT_CHANNEL_MAP = {
    # Floats
    "rpm": 0,
    "speed": 1,
    "coolantTemp": 2,
    "fuelLevel": 3,
    # gear is int, handled separately
    "battery": 5,
    "power": 6,
    "rangeKm": 7,
}

_GEAR_CHANNEL = 4

_DOOR_CHANNEL_MAP = {
    "doorFL": 8,
    "doorFR": 9,
    "doorRL": 10,
    "doorRR": 11,
    "trunk": 12,
    "hood": 13,
}

# Register the RadialBar QML type once
_registered = False


def _ensure_registered():
    global _registered
    if not _registered:
        qmlRegisterType(RadialBar, "CustomControls", 1, 0, "RadialBar")
        _registered = True


class HMIDashboardTab(QWidget):
    """Tab widget embedding the adaptive QML car dashboard."""

    def __init__(self, dashboard_backend=None, parent=None):
        super().__init__(parent)
        _ensure_registered()

        self._backend = dashboard_backend
        self._bridge = _HMIBridge(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._qml_widget = QQuickWidget()
        self._qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)

        ctx = self._qml_widget.rootContext()
        ctx.setContextProperty("dashboard", self._bridge)

        qml_dir = self._find_qml_dir()
        qml_url = QUrl.fromLocalFile(os.path.join(qml_dir, "main.qml"))
        self._qml_widget.setSource(qml_url)

        errors = self._qml_widget.errors()
        if errors:
            for e in errors:
                print(f"[HMI QML Error] {e.toString()}")

        layout.addWidget(self._qml_widget)

        if self._backend is not None:
            self._backend.channelsUpdated.connect(self._on_data)

    @staticmethod
    def _find_qml_dir():
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "qml", "hmi"),
            os.path.join(getattr(sys, "_MEIPASS", ""), "qml", "hmi"),
        ]
        for c in candidates:
            c = os.path.normpath(c)
            if os.path.isfile(os.path.join(c, "main.qml")):
                return c
        return os.path.normpath(candidates[0])

    def _on_data(self):
        vals = self._backend.channelValues
        # Float channels
        for name, ch in _DEFAULT_CHANNEL_MAP.items():
            if ch < len(vals):
                setattr(self._bridge, name, float(vals[ch]))
        # Gear (int)
        if _GEAR_CHANNEL < len(vals):
            self._bridge._set_gear(int(vals[_GEAR_CHANNEL]))
        # Doors (bool: >=1 means open)
        for name, ch in _DOOR_CHANNEL_MAP.items():
            if ch < len(vals):
                setattr(self._bridge, name, float(vals[ch]) >= 1.0)

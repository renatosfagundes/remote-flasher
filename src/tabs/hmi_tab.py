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
    # Warning lights
    checkEngineChanged = Signal()
    oilPressureChanged = Signal()
    batteryWarnChanged = Signal()
    brakeWarnChanged = Signal()
    absWarnChanged = Signal()
    airbagWarnChanged = Signal()
    serviceDueChanged = Signal()
    tirePressureChanged = Signal()
    doorOpenChanged = Signal()
    tractionControlChanged = Signal()
    # Status lights
    parkingLightsChanged = Signal()
    lowBeamChanged = Signal()
    highBeamChanged = Signal()
    fogLightsChanged = Signal()
    seatbeltUnbuckledChanged = Signal()
    cruiseActiveChanged = Signal()
    ecoModeChanged = Signal()
    evChargingChanged = Signal()
    # Turn signals
    turnLeftChanged = Signal()
    turnRightChanged = Signal()
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
        # Warning lights
        self._checkEngine = False
        self._oilPressure = False
        self._batteryWarn = False
        self._brakeWarn = False
        self._absWarn = False
        self._airbagWarn = False
        self._serviceDue = False
        self._tirePressure = False
        self._doorOpen = False
        self._tractionControl = False
        # Status lights
        self._parkingLights = False
        self._lowBeam = False
        self._highBeam = False
        self._fogLights = False
        self._seatbeltUnbuckled = False
        self._cruiseActive = False
        self._ecoMode = False
        self._evCharging = False
        # Turn signals
        self._turnLeft = False
        self._turnRight = False
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

    # ── Warning lights ─────────────────────────────────────────────
    _gs_ce = _make_bool_prop("checkEngine")
    checkEngine = Property(bool, _gs_ce[0], _gs_ce[1], notify=checkEngineChanged)
    _gs_op = _make_bool_prop("oilPressure")
    oilPressure = Property(bool, _gs_op[0], _gs_op[1], notify=oilPressureChanged)
    _gs_bw = _make_bool_prop("batteryWarn")
    batteryWarn = Property(bool, _gs_bw[0], _gs_bw[1], notify=batteryWarnChanged)
    _gs_brw = _make_bool_prop("brakeWarn")
    brakeWarn = Property(bool, _gs_brw[0], _gs_brw[1], notify=brakeWarnChanged)
    _gs_aw = _make_bool_prop("absWarn")
    absWarn = Property(bool, _gs_aw[0], _gs_aw[1], notify=absWarnChanged)
    _gs_abw = _make_bool_prop("airbagWarn")
    airbagWarn = Property(bool, _gs_abw[0], _gs_abw[1], notify=airbagWarnChanged)
    _gs_sd = _make_bool_prop("serviceDue")
    serviceDue = Property(bool, _gs_sd[0], _gs_sd[1], notify=serviceDueChanged)
    _gs_tp = _make_bool_prop("tirePressure")
    tirePressure = Property(bool, _gs_tp[0], _gs_tp[1], notify=tirePressureChanged)
    _gs_do = _make_bool_prop("doorOpen")
    doorOpen = Property(bool, _gs_do[0], _gs_do[1], notify=doorOpenChanged)
    _gs_tc = _make_bool_prop("tractionControl")
    tractionControl = Property(bool, _gs_tc[0], _gs_tc[1], notify=tractionControlChanged)

    # ── Status lights ──────────────────────────────────────────────
    _gs_pl = _make_bool_prop("parkingLights")
    parkingLights = Property(bool, _gs_pl[0], _gs_pl[1], notify=parkingLightsChanged)
    _gs_lb = _make_bool_prop("lowBeam")
    lowBeam = Property(bool, _gs_lb[0], _gs_lb[1], notify=lowBeamChanged)
    _gs_hb = _make_bool_prop("highBeam")
    highBeam = Property(bool, _gs_hb[0], _gs_hb[1], notify=highBeamChanged)
    _gs_fg = _make_bool_prop("fogLights")
    fogLights = Property(bool, _gs_fg[0], _gs_fg[1], notify=fogLightsChanged)
    _gs_sb = _make_bool_prop("seatbeltUnbuckled")
    seatbeltUnbuckled = Property(bool, _gs_sb[0], _gs_sb[1], notify=seatbeltUnbuckledChanged)
    _gs_ca = _make_bool_prop("cruiseActive")
    cruiseActive = Property(bool, _gs_ca[0], _gs_ca[1], notify=cruiseActiveChanged)
    _gs_em = _make_bool_prop("ecoMode")
    ecoMode = Property(bool, _gs_em[0], _gs_em[1], notify=ecoModeChanged)
    _gs_ec = _make_bool_prop("evCharging")
    evCharging = Property(bool, _gs_ec[0], _gs_ec[1], notify=evChargingChanged)

    # ── Turn signals ───────────────────────────────────────────────
    _gs_tl = _make_bool_prop("turnLeft")
    turnLeft = Property(bool, _gs_tl[0], _gs_tl[1], notify=turnLeftChanged)
    _gs_tr = _make_bool_prop("turnRight")
    turnRight = Property(bool, _gs_tr[0], _gs_tr[1], notify=turnRightChanged)

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

# Warning + status channels (bool: >= 1.0 means active)
_BOOL_CHANNEL_MAP = {
    "checkEngine": 14,
    "oilPressure": 15,
    "batteryWarn": 16,
    "brakeWarn": 17,
    "absWarn": 18,
    "airbagWarn": 19,
    "parkingLights": 20,
    "lowBeam": 21,
    "highBeam": 22,
    "fogLights": 23,
    "seatbeltUnbuckled": 24,
    "turnLeft": 25,
    "turnRight": 26,
    "cruiseActive": 27,
    "serviceDue": 28,
    "tirePressure": 29,
    "doorOpen": 30,
    "tractionControl": 31,
    "ecoMode": 32,
    "evCharging": 33,
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
        # Warning + status lights (bool: >=1 means active)
        for name, ch in _BOOL_CHANNEL_MAP.items():
            if ch < len(vals):
                setattr(self._bridge, name, float(vals[ch]) >= 1.0)

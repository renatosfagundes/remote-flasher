"""Preview Gemini QML files with CustomControls + dashboard stub.
Usage: python preview.py TestAllModes.qml
"""
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "remote_flasher" / "src"))

from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType

from radial_bar import RadialBar


_GEAR_SEQ = (7, -1, 0, 8, 1, 2, 3, 4, 5, 6)  # P R N D 1..6
_WARN_RATES = (0.4, 0.7, 1.1, 0.5, 0.9, 0.6)
_STATUS_RATES = (0.13, 0.21, 0.17, 0.27)  # slower toggles for status icons
# Extra warnings (service, tirePressure, doorOpen, tractionControl) — slower
# toggles, mostly OFF (sin > 0.6 instead of 0.3 → on ~25% of the time).
_EXTRA_WARN_RATES = (0.31, 0.43, 0.19, 0.55)
# Extra status indicators (highBeam, cruise, eco, evCharging)
_EXTRA_STATUS_RATES = (0.11, 0.09, 0.07, 0.05)
# Door states (FL, FR, RL, RR, hood, trunk) — very slow, mostly closed.
# Sin > 0.85 → on roughly 16% of the cycle.
_DOOR_RATES = (0.18, 0.23, 0.31, 0.27, 0.13, 0.16)

# Shared debug state (initialised in main)
DEBUG_LOG = None
EVENT_RING = None
RING_MAX = 500    # last N events before a stall
_last_event_t = [0.0]


def dlog(category, message):
    """Record an event into the ring buffer. On stall, we flush the whole
    ring to the debug file so we can see exactly what was happening."""
    import time
    if EVENT_RING is None:
        return
    now = time.perf_counter()
    delta_ms = (now - _last_event_t[0]) * 1000 if _last_event_t[0] else 0
    _last_event_t[0] = now
    stamp = time.strftime('%H:%M:%S') + f".{int((now%1)*1000):03d}"
    EVENT_RING.append((stamp, delta_ms, category, message))
    if len(EVENT_RING) > RING_MAX:
        EVENT_RING.pop(0)


def dump_ring_on_stall(gap_ms):
    """Flush the ring buffer to the debug file when a stall is detected."""
    import time
    if DEBUG_LOG is None or EVENT_RING is None:
        return
    DEBUG_LOG.write(f"\n\n========== STALL {gap_ms:.0f}ms  @ {time.strftime('%H:%M:%S')} ==========\n")
    DEBUG_LOG.write(f"Last {len(EVENT_RING)} events before the stall:\n")
    for stamp, delta_ms, cat, msg in EVENT_RING:
        DEBUG_LOG.write(f"  {stamp} | +{delta_ms:7.1f}ms | {cat:12s} | {msg}\n")
    DEBUG_LOG.write(f"========== END STALL DUMP ==========\n")
    DEBUG_LOG.flush()
    EVENT_RING.clear()


class DashboardStub(QObject):
    """Stub dashboard that cycles values so previews look alive."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._speed = 0
        self._rpm = 0
        self._cool = 85
        self._fuel = 62
        self._bat = 71
        self._pow = 0
        self._range = 188
        self._dist = 12450
        self._avg = 78
        self._gear = 3
        self._mode = 1
        self._t = 0
        self._warn_states = [False] * 6   # engine, oil, bat, brake, abs, airbag
        self._status_states = [False] * 4 # parking, lowbeam, fog, seatbelt
        # Extra warnings: service, tirePressure, doorOpen, tractionControl
        self._extra_warn_states = [False] * 4
        # Extra status indicators: highBeam, cruise, eco, evCharging
        self._extra_status_states = [False] * 4
        # Turn-signal state: which side intends to indicate, plus a blink phase
        self._turn_intent = 0   # -1 = right, 0 = none, +1 = left
        self._turn_blink = False
        # Door / hood / trunk states (FL, FR, RL, RR, hood, trunk) — slow,
        # mostly-closed toggles so the DoorStatus widget actually animates.
        self._door_states = [False] * 6
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)  # 10 Hz — target rate
        # Independent heartbeat timer: just logs that the event loop is alive.
        # If this timer also stalls during a STALL, it confirms the loop itself
        # is blocked (not just our tick).
        self._heartbeat = QTimer(self)
        self._heartbeat.timeout.connect(lambda: dlog('heartbeat', 'beat'))
        self._heartbeat.start(50)  # 20 Hz heartbeat (independent stall detector)

    def _tick(self):
        import math, time, os
        now = time.perf_counter()
        if hasattr(self, '_last_tick_t'):
            gap = (now - self._last_tick_t) * 1000
            if gap > 200:  # 100ms tick — flag anything >200ms
                stamp = time.strftime('%H:%M:%S') + f".{int((now%1)*1000):03d}"
                print(f"[{stamp}] !! event-loop STALL {gap:.0f}ms (expected ~100ms)")
                dump_ring_on_stall(gap)
        self._last_tick_t = now

        if os.environ.get('STATIC') == '1':
            return

        dlog('tick', 'start _tick')

        self._t += 0.1
        t0 = time.perf_counter()
        self._speed = 60 + 40 * math.sin(self._t * 0.3)
        self._rpm = 3000 + 2000 * math.sin(self._t * 0.4)
        self._pow = 80 * math.sin(self._t * 0.5)
        self._bat = 60 + 40 * math.sin(self._t * 0.08)
        self._fuel = 50 + 40 * math.sin(self._t * 0.1 + 1.0)
        self._cool = 85 + 15 * math.sin(self._t * 0.2)
        self._range = 5.0 * self._bat
        # Distance increases at simulated speed.
        # Real rate would be: km/h × (tick_ms/3600000) = km. At 60 km/h
        # that's 0.00167 km/tick — invisible after .toFixed(0). For demo
        # we accelerate by 100× so you can watch the odometer tick up.
        self._dist += max(0, self._speed) / 360.0
        # Avg speed: slow EMA-like drift around current speed
        self._avg = self._avg * 0.99 + self._speed * 0.01
        self._gear = _GEAR_SEQ[int(self._t / 2) % len(_GEAR_SEQ)]
        for i, r in enumerate(_WARN_RATES):
            self._warn_states[i] = (math.sin(self._t * r) > 0.3)
        for i, r in enumerate(_STATUS_RATES):
            self._status_states[i] = (math.sin(self._t * r) > 0.4)
        for i, r in enumerate(_EXTRA_WARN_RATES):
            self._extra_warn_states[i] = (math.sin(self._t * r) > 0.6)
        for i, r in enumerate(_EXTRA_STATUS_RATES):
            self._extra_status_states[i] = (math.sin(self._t * r) > 0.3)
        for i, r in enumerate(_DOOR_RATES):
            self._door_states[i] = (math.sin(self._t * r) > 0.85)
        # Turn signals: cycle intent every ~6s (left → none → right → none),
        # blink at ~1.4Hz while indicating.
        phase = int(self._t / 6) % 4
        self._turn_intent = (1, 0, -1, 0)[phase]
        self._turn_blink = (math.sin(self._t * 9.0) > 0)
        dlog('tick', f'recompute {(time.perf_counter()-t0)*1000:.2f}ms')

        t0 = time.perf_counter()
        self.changed.emit()
        dlog('tick', f'emit changed {(time.perf_counter()-t0)*1000:.2f}ms')

    def _r(self, v): return float(v)
    speed = Property(float, lambda s: s._speed, notify=changed)
    rpm = Property(float, lambda s: s._rpm, notify=changed)
    coolantTemp = Property(float, lambda s: s._cool, notify=changed)
    fuelLevel = Property(float, lambda s: s._fuel, notify=changed)
    battery = Property(float, lambda s: s._bat, notify=changed)
    power = Property(float, lambda s: s._pow, notify=changed)
    rangeKm = Property(float, lambda s: s._range, notify=changed)
    distance = Property(float, lambda s: s._dist, notify=changed)
    avgSpeed = Property(float, lambda s: s._avg, notify=changed)
    gear = Property(int, lambda s: s._gear, notify=changed)
    vehicleMode = Property(int, lambda s: s._mode, notify=changed)

    @Slot(int)
    def setVehicleMode(self, v):
        self._mode = v
        self.changed.emit()

    doorFL = Property(bool, lambda s: s._door_states[0], notify=changed)
    doorFR = Property(bool, lambda s: s._door_states[1], notify=changed)
    doorRL = Property(bool, lambda s: s._door_states[2], notify=changed)
    doorRR = Property(bool, lambda s: s._door_states[3], notify=changed)
    hood   = Property(bool, lambda s: s._door_states[4], notify=changed)
    trunk  = Property(bool, lambda s: s._door_states[5], notify=changed)
    # Warning lights — each toggles independently over time
    checkEngine = Property(bool, lambda s: s._warn_states[0], notify=changed)
    oilPressure = Property(bool, lambda s: s._warn_states[1], notify=changed)
    batteryWarn = Property(bool, lambda s: s._warn_states[2], notify=changed)
    brakeWarn   = Property(bool, lambda s: s._warn_states[3], notify=changed)
    absWarn     = Property(bool, lambda s: s._warn_states[4], notify=changed)
    airbagWarn  = Property(bool, lambda s: s._warn_states[5], notify=changed)
    # Status lights — slow toggles for parking, low-beam, fog, seatbelt
    parkingLights  = Property(bool, lambda s: s._status_states[0], notify=changed)
    lowBeam        = Property(bool, lambda s: s._status_states[1], notify=changed)
    fogLights      = Property(bool, lambda s: s._status_states[2], notify=changed)
    seatbeltUnbuckled = Property(bool, lambda s: s._status_states[3], notify=changed)
    # Extra warnings — exposed under camelCase names matching dashboard backend
    serviceDue       = Property(bool, lambda s: s._extra_warn_states[0], notify=changed)
    tirePressure     = Property(bool, lambda s: s._extra_warn_states[1], notify=changed)
    doorOpen         = Property(bool, lambda s: s._extra_warn_states[2], notify=changed)
    tractionControl  = Property(bool, lambda s: s._extra_warn_states[3], notify=changed)
    # Extra status indicators
    highBeam      = Property(bool, lambda s: s._extra_status_states[0], notify=changed)
    cruiseActive  = Property(bool, lambda s: s._extra_status_states[1], notify=changed)
    ecoMode       = Property(bool, lambda s: s._extra_status_states[2], notify=changed)
    evCharging    = Property(bool, lambda s: s._extra_status_states[3], notify=changed)
    # Turn signals: only "active" while indicating AND during the on-phase of blink
    turnLeft  = Property(bool, lambda s: (s._turn_intent ==  1) and s._turn_blink, notify=changed)
    turnRight = Property(bool, lambda s: (s._turn_intent == -1) and s._turn_blink, notify=changed)


def strip_cite_markers():
    """Remove [cite: N] markers that Gemini sometimes injects into QML.
    Must NOT consume newlines — doing so collapses `//` comments into
    adjacent QML tokens and causes syntax errors.
    """
    import re
    here = Path(__file__).parent
    cleaned = []
    for qml in here.glob("*.qml"):
        text = qml.read_text(encoding="utf-8")
        # Strip " [cite: ...]" but keep trailing newline intact
        new = re.sub(r"[ \t]*\[cite:[^\]\n]*\]", "", text)
        if new != text:
            qml.write_text(new, encoding="utf-8")
            cleaned.append(qml.name)
    if cleaned:
        print(f"[preview] Stripped cite markers from: {', '.join(cleaned)}")


def _wrap_item_in_window(qml_path):
    """If the given QML file's root is an Item (not a Window), create a
    temporary wrapper Window that loads it, so we can preview any
    component file directly. Returns the path to load."""
    with open(qml_path, 'r', encoding='utf-8') as f:
        text = f.read()
    # If the file already declares a Window at the top level, use it directly.
    import re
    first_element = re.search(r'^\s*(?:import[^\n]*\n|//[^\n]*\n|/\*.*?\*/|\s)*\s*(\w+)\s*\{',
                              text, re.DOTALL | re.MULTILINE)
    if first_element and first_element.group(1) == 'Window':
        return qml_path

    # Otherwise generate a Loader-based wrapper that loads the file by URL.
    # This works whether the file declares an explicit component type or not.
    comp_name = os.path.splitext(os.path.basename(qml_path))[0]
    wrapper_path = os.path.join(os.path.dirname(qml_path), f"_preview_{comp_name}.qml")
    src_url = "file:///" + qml_path.replace("\\", "/").lstrip("/")
    wrapper = f'''import QtQuick 2.15
import QtQuick.Window 2.15
Window {{
    id: win
    width: 1200
    height: 650
    // Floor so Qt layouts can't collapse to invalid (negative) sizes.
    // Below ~800x450 the QML modes start producing layout warnings.
    minimumWidth: 800
    minimumHeight: 450
    visible: true
    color: "black"
    title: "Preview: {comp_name}"

    // Scale-to-fit container: the loaded mode is always laid out at its
    // native 1200x650, then scaled down (never up) so it fits the window
    // while preserving aspect ratio.
    Item {{
        id: scaler
        anchors.centerIn: parent
        width: 1200
        height: 650
        scale: Math.min(win.width / 1200, win.height / 650, 1.0)
        Loader {{
            anchors.fill: parent
            source: "{src_url}"
        }}
    }}
}}
'''
    with open(wrapper_path, 'w', encoding='utf-8') as f:
        f.write(wrapper)
    return wrapper_path


def main():
    qml_path = sys.argv[1] if len(sys.argv) > 1 else "TestAllModes.qml"
    if not os.path.isabs(qml_path):
        qml_path = str(Path(__file__).parent / qml_path)

    strip_cite_markers()
    qml_path = _wrap_item_in_window(qml_path)

    # Allow forcing a specific Qt render loop via env var.
    # Try RENDER_LOOP=basic, windows, threaded
    if 'RENDER_LOOP' in os.environ:
        os.environ['QSG_RENDER_LOOP'] = os.environ['RENDER_LOOP']
        print(f"[preview] QSG_RENDER_LOOP = {os.environ['RENDER_LOOP']}")
    # Enable Qt QML JS engine GC trace
    if 'QML_GC' in os.environ:
        os.environ['QV4_MM_STATS'] = '1'
        print("[preview] QML JS GC stats enabled")
    # Enable Qt scene graph timing
    if 'SG_TIME' in os.environ:
        os.environ['QSG_RENDER_TIMING'] = '1'
        print("[preview] Scene graph render timing enabled")

    # Open a verbose debug log. Keep a ring-buffer in memory so when a
    # stall is detected we can dump the last ~500ms of activity around it.
    import time
    global DEBUG_LOG, EVENT_RING
    DEBUG_LOG = open(Path(__file__).parent / "debug_stall.log", "w",
                     encoding="utf-8", buffering=1)  # line-buffered
    EVENT_RING = []  # list of (timestamp, category, message)
    DEBUG_LOG.write(f"=== Verbose stall debug — started {time.strftime('%H:%M:%S')} ===\n")
    DEBUG_LOG.write(f"QML: {qml_path}\n")
    DEBUG_LOG.write("Columns: timestamp | delta_from_prev_ms | category | message\n\n")

    # Install Python GC debugger — prints every GC pause over 5ms so we
    # can correlate with !! STALL messages.
    import gc, time
    _gc_t0 = [time.perf_counter()]
    def _gc_cb(phase, info):
        if phase == 'start':
            _gc_t0[0] = time.perf_counter()
        elif phase == 'stop':
            dt = (time.perf_counter() - _gc_t0[0]) * 1000
            if dt > 5:
                now = time.perf_counter()
                stamp = time.strftime('%H:%M:%S') + f".{int((now%1)*1000):03d}"
                print(f"[{stamp}] >> Python GC gen={info.get('generation','?')} "
                      f"collected={info.get('collected','?')} uncollectable={info.get('uncollectable','?')} "
                      f"took {dt:.0f}ms")
    gc.callbacks.append(_gc_cb)

    app = QGuiApplication(sys.argv)
    qmlRegisterType(RadialBar, "CustomControls", 1, 0, "RadialBar")

    engine = QQmlApplicationEngine()
    dash = DashboardStub()
    engine.rootContext().setContextProperty("dashboard", dash)
    engine.load(QUrl.fromLocalFile(qml_path))

    if not engine.rootObjects():
        print("Failed to load QML — see messages above.")
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

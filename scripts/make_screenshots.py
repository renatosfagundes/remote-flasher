"""Generate documentation screenshots for Remote Firmware Flasher.

Boots the app offscreen (WA_DontShowOnScreen), injects synthetic state into
every tab/bridge/backend, and saves PNGs into docs/images/. No VPN, no SSH,
no real hardware — the tabs think they're live because we poked their
widgets directly.

Run:
    .venv\\Scripts\\python scripts\\make_screenshots.py

Output: docs/images/*.png

The script is deterministic: same inputs, same pixels. Re-run whenever the
UI changes and commit the refreshed PNGs alongside it.
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
import time
from pathlib import Path

# Redirect QSettings to a temp dir BEFORE any QSettings object is created,
# so this script cannot pollute the user's saved window state / credentials.
_TMP_SETTINGS = tempfile.mkdtemp(prefix="rf_shots_")
os.environ["APPDATA"] = _TMP_SETTINGS  # settings.py uses %APPDATA%\RemoteFlasher

from PySide6.QtCore import Qt, QSettings, QTimer  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QTabWidget  # noqa: E402

QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _TMP_SETTINGS)

# Resolve project root / src for import + run from any cwd
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# Pre-seed settings so the first-run dialog doesn't fire.
from settings import save_settings  # noqa: E402
save_settings(user_name="renato", remote_user_dir=r"C:\2026\renato",
              vpn_username="renato.fagundes", vpn_password="•••")

from main_window import MainWindow  # noqa: E402

OUT = ROOT / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────
# Scene injectors — each poses one tab / dialog / dashboard state.
# ─────────────────────────────────────────────────────────────────────────

def _pump(app: QApplication, n: int = 3) -> None:
    """Let Qt layout/style/paint events settle before grabbing."""
    for _ in range(n):
        app.processEvents()


def pose_vpn_connected(w: MainWindow) -> None:
    t = w.vpn_tab
    t.vpn_user.setText("renato.fagundes")
    t.vpn_pass.setText("••••••••")
    t.remember_cb.setChecked(True)
    t.status_indicator.set_status("connected")
    t.status_label.setText("Connected")
    t.connect_btn.setText("Disconnect VPN")
    t._connected = True
    t.log.clear()
    t.log.append_log("[VPN] Connecting to 'VPN_CIN' as 'renato.fagundes'...")
    t.log.append_log("[VPN] Connected successfully!")
    t.log.append_log("Connected to VPN_CIN.")


def pose_health_check(w: MainWindow) -> None:
    """Fill the health check grid with a realistic mix of statuses."""
    hc = w.vpn_tab._hc_indicators
    # Mark all plumbed boards OK except one frozen on PC 220 Placa 02.
    matrix = {
        ("PC 217", "Placa 01"): ("ok", "OK"),
        ("PC 217", "Placa 02"): ("ok", "OK"),
        ("PC 217", "Placa 03"): ("ok", "OK"),
        ("PC 217", "Placa 04"): ("ok", "OK"),
        ("PC 217", "camera"):   ("ok", "OK"),
        ("PC 220", "Placa 01"): ("ok", "OK"),
        ("PC 220", "Placa 02"): ("fail", "FROZEN"),
        ("PC 220", "Placa 03"): ("ok", "OK"),
        ("PC 220", "Placa 04"): ("ok", "OK"),
    }
    for key, (status, text) in matrix.items():
        pair = hc.get(key)
        if pair is None:
            continue
        ind, lbl = pair
        if status == "ok":
            ind.set_status("connected")
            lbl.setStyleSheet("font-size: 10px; color: #44ff44;")
        elif status == "fail":
            ind.set_status("disconnected")
            lbl.setStyleSheet("font-size: 10px; color: #ff4444; font-weight: bold;")
        else:
            ind.set_status("idle")
            lbl.setStyleSheet("font-size: 10px; color: #888;")
        lbl.setText(text)

    w.vpn_tab.log.clear()
    w.vpn_tab.log.append_log("[Health] Starting health check on all PCs...")
    w.vpn_tab.log.append_log("[Health] Checking PC 217 (172.20.36.217)...")
    w.vpn_tab.log.append_log("[Health] PC 217: all 4 boards responding")
    w.vpn_tab.log.append_log("[Health] PC 217: camera process running")
    w.vpn_tab.log.append_log("[Health] Checking PC 220 (172.20.36.220)...")
    w.vpn_tab.log.append_log("[Health] !! PC 220 Placa 02 (COM32): FROZEN / not responding")
    w.vpn_tab.log.append_log("[Health] Health check complete.")


def pose_flash_ready(w: MainWindow) -> None:
    t = w.flash_tab
    t.pc_combo.setCurrentIndex(0)  # PC 217
    _pump(QApplication.instance(), 1)
    t.board_combo.setCurrentIndex(0)  # Placa 01
    _pump(QApplication.instance(), 1)
    if t.ecu_combo.count():
        t.ecu_combo.setCurrentIndex(0)
    t.hex_path.setText(r"C:\Users\renato\Codigos\Pos\RTOS\examples\13_dashboard_full\build\dashboard_full.hex")
    t.remote_folder.setText(r"C:\2026\renato")
    t.log.clear()


def pose_flash_success(w: MainWindow) -> None:
    pose_flash_ready(w)
    t = w.flash_tab
    op = t._mint_op()
    t.log.append_op(op, "=== Starting full flash sequence ===")
    t.log.append_op(op, "[SCP] Connecting to 172.20.36.217...")
    t.log.append_op(op, "[SCP] Uploading dashboard_full.hex -> c:/2026/renato/dashboard_full.hex")
    t.log.append_op(op, "[SCP] Upload complete (6384 bytes)")
    t.log.append_op(op, "[All] Resetting board...")
    t.log.append_op(op, "[SSH] Running: reset.ps1 -Port COM61")
    t.log.append_op(op, "[All] Flashing firmware...")
    t.log.append_op(op, "[Flash] Executing: avrdude -C avrdude.conf -v -p atmega328p -c arduino -b 115200 -P COM25 -U flash:w:dashboard_full.hex:i")
    t.log.append_op(op, "avrdude: AVR device initialized and ready to accept instructions")
    t.log.append_op(op, "avrdude: Device signature = 0x1e950f (probably m328p)")
    t.log.append_op(op, "Writing | ################################################## | 100% 2.83s")
    t.log.append_op(op, "Reading | ################################################## | 100% 2.19s")
    t.log.append_op(op, "avrdude: 6384 bytes of flash verified")
    t.log.append_op(op, "avrdude done.  Thank you.")
    t.log.append_op(op, "[Flash] SUCCESS")


def pose_serial_single(w: MainWindow) -> None:
    t = w.serial_tab
    # A single panel already exists by default.
    panel = t.panels[0]
    panel.pc_combo.setCurrentIndex(0)
    _pump(QApplication.instance(), 1)
    panel.board_combo.setCurrentIndex(0)
    _pump(QApplication.instance(), 1)
    if panel.port_combo.count():
        panel.port_combo.setCurrentIndex(0)
    panel.baudrate.setCurrentText("115200")
    panel.log.clear()
    panel.log.append_log("[Serial] Connecting to 172.20.36.217...")
    panel.log.append_log("Opening COM25 at 115200 baud...")
    panel.log.append_log("Connected to COM25. Reading... (type to send)")
    for line in [
        "$speed:48.2,rpm:3847,coolantTemp:86.1,fuelLevel:62,battery:71,power:42.3,gear:3",
        "$speed:50.5,rpm:3901,coolantTemp:86.2,fuelLevel:62,battery:71,power:44.1,gear:3",
        "$speed:52.9,rpm:3955,coolantTemp:86.3,fuelLevel:62,battery:71,power:45.8,gear:3",
        "$speed:55.1,rpm:4009,coolantTemp:86.4,fuelLevel:62,battery:71,power:47.2,gear:3",
        "$speed:57.3,rpm:4063,coolantTemp:86.5,fuelLevel:62,battery:70,power:48.7,gear:3",
        "$speed:59.4,rpm:4118,coolantTemp:86.6,fuelLevel:61,battery:70,power:50.1,gear:3",
    ]:
        panel.log.append_log(line)
    # Simulate "connected" state visually
    panel.connect_btn.setText("Close Serial")
    panel.feed_dash_cb.setEnabled(True)
    panel.feed_plot_cb.setEnabled(True)
    panel.feed_dash_cb.setChecked(True)
    panel.feed_plot_cb.setChecked(True)


def pose_serial_2x2(w: MainWindow) -> None:
    t = w.serial_tab
    # Add panels until we have 4
    while len(t.panels) < 4:
        t._add_panel()
    _pump(QApplication.instance(), 2)

    sample_logs = [
        ["$speed:52,rpm:3987,gear:3", "$speed:54,rpm:4020,gear:3"],
        ["$rpm:1850,coolantTemp:72", "$rpm:1895,coolantTemp:73"],
        ["$battery:68,power:-12.4", "$battery:68,power:-8.1"],
        ["Arduino ready.", "Sensors OK.", "loop() tick 12847"],
    ]
    ports = ["COM25", "COM29", "COM33", "COM53"]
    boards = [0, 1, 2, 3]

    for i, panel in enumerate(t.panels):
        panel.pc_combo.setCurrentIndex(0)
        _pump(QApplication.instance(), 1)
        if panel.board_combo.count() > boards[i]:
            panel.board_combo.setCurrentIndex(boards[i])
        _pump(QApplication.instance(), 1)
        # Find the port in the combo (may be annotated)
        for j in range(panel.port_combo.count()):
            text = panel.port_combo.itemText(j)
            if ports[i] in text:
                panel.port_combo.setCurrentIndex(j)
                break
        panel.baudrate.setCurrentText("115200")
        panel.log.clear()
        panel.log.append_log(f"Opening {ports[i]} at 115200 baud...")
        panel.log.append_log(f"Connected to {ports[i]}. Reading...")
        for line in sample_logs[i]:
            panel.log.append_log(line)
        panel.connect_btn.setText("Close Serial")

    # First panel feeds dashboard + plotter
    t.panels[0].feed_dash_cb.setEnabled(True)
    t.panels[0].feed_plot_cb.setEnabled(True)
    t.panels[0].feed_dash_cb.setChecked(True)
    t.panels[0].feed_plot_cb.setChecked(True)
    # Animate VIO on panel 1 to look "live"
    vio = t.panels[0].vio_panel
    vio.set_led(0, 255)
    vio.set_led(2, 200)
    vio._sliders[0].setValue(620)
    vio._sliders[1].setValue(340)


def pose_hmi_electric(w: MainWindow) -> None:
    """Rich EV scene — full gauges, a few warnings, turn signals alternating."""
    bridge = w.gauges_tab._bridge
    bridge.vehicleMode = 0  # Electric
    bridge.speed = 72.0
    bridge.rpm = 0
    bridge.battery = 68.0
    bridge.power = 38.5
    bridge.rangeKm = 312.0
    bridge.distance = 12467
    bridge.avgSpeed = 58.0
    bridge.coolantTemp = 28.0       # EV motor
    bridge.fuelLevel = 0
    # Gear indicator in EV is D-like
    bridge.gear = 8  # D
    # Lights
    bridge.lowBeam = True
    bridge.parkingLights = True
    bridge.ecoMode = True
    bridge.cruiseActive = True
    bridge.seatbeltUnbuckled = False
    # One benign warning
    bridge.tirePressure = True
    # Turn signal on
    bridge.turnLeft = True
    bridge.turnRight = False


def pose_hmi_auto(w: MainWindow) -> None:
    bridge = w.gauges_tab._bridge
    bridge.vehicleMode = 1  # CombustionAuto
    bridge.speed = 84.0
    bridge.rpm = 2650
    bridge.coolantTemp = 91.0
    bridge.fuelLevel = 54.0
    bridge.battery = 100.0
    bridge.power = 0
    bridge.rangeKm = 460.0
    bridge.distance = 45812
    bridge.avgSpeed = 62.0
    bridge.gear = 8  # D
    bridge.lowBeam = True
    bridge.parkingLights = True
    bridge.cruiseActive = True
    bridge.seatbeltUnbuckled = False
    bridge.checkEngine = False
    bridge.oilPressure = False
    bridge.batteryWarn = False
    bridge.brakeWarn = False
    bridge.absWarn = False
    bridge.airbagWarn = False
    bridge.ecoMode = False
    bridge.evCharging = False
    bridge.turnLeft = False
    bridge.turnRight = False


def pose_hmi_manual(w: MainWindow) -> None:
    bridge = w.gauges_tab._bridge
    bridge.vehicleMode = 2  # CombustionManual
    bridge.speed = 67.0
    bridge.rpm = 4120
    bridge.coolantTemp = 95.0
    bridge.fuelLevel = 31.0
    bridge.battery = 100.0
    bridge.manualGear = 4
    bridge.gear = 0
    bridge.distance = 78421
    bridge.avgSpeed = 54.0
    bridge.lowBeam = True
    bridge.highBeam = False
    bridge.parkingLights = True
    bridge.fogLights = True
    bridge.cruiseActive = False
    bridge.seatbeltUnbuckled = False
    # Simulate a DTC popping
    bridge.checkEngine = True
    bridge.tirePressure = True
    # Door open
    bridge.doorFL = True
    bridge.hood = False
    bridge.trunk = False
    bridge.turnRight = True


def _feed_plotter_direct(w: MainWindow, duration_s: float,
                         hz: int, signals: list[tuple]) -> None:
    """Write synthetic samples straight into the plotter's ring buffers so
    timestamps reflect the intended duration (onSerialLine stamps everything
    at `time.perf_counter()`, which clumps a tight loop at ~0 seconds).

    `signals` is a list of (name, callable_of_t) pairs; each callable takes
    a time-in-seconds and returns a float.
    """
    backend = w.plotter_tab._backend
    backend.reset()
    # Prime the time-origin so new signals backfill correctly.
    backend._t0 = 0.0
    # Create all signals up-front so ring_buffer order is stable.
    for name, _ in signals:
        backend._get_or_create_signal(name)
    # Feed samples with explicit timestamps.
    N = int(duration_s * hz)
    time_buf = backend.time_buffer()
    for i in range(N):
        t = i / hz
        time_buf.append(t)
        for (name, fn), ch_idx in zip(signals, range(len(signals))):
            buf = backend.channel_buffer(ch_idx)
            buf.append(float(fn(t)))
    backend._dirty = True


def _feed_plotter_waveforms(w: MainWindow, duration_s: float = 12.0,
                            hz: int = 50, n_signals: int = 3) -> None:
    """3-signal scene: speed / rpm / coolantTemp."""
    all_sigs = [
        ("speed",       lambda t: 40 + 30 * math.sin(t * 0.7)),
        ("rpm",         lambda t: 3000 + 1500 * math.sin(t * 0.8 + 0.6)),
        ("coolantTemp", lambda t: 85 + 10 * math.sin(t * 0.12)),
    ]
    _feed_plotter_direct(w, duration_s, hz, all_sigs[:n_signals])


def _feed_plotter_many_signals(w: MainWindow, duration_s: float = 12.0,
                               hz: int = 50) -> None:
    """8-signal scene exercising the auto-hide-above-5 rule."""
    sigs = [
        ("speed",       lambda t: 40 + 30 * math.sin(t * 0.7)),
        ("rpm",         lambda t: 3000 + 1500 * math.sin(t * 0.8)),
        ("coolantTemp", lambda t: 85 + 10 * math.sin(t * 0.12)),
        ("fuelLevel",   lambda t, d=duration_s: 75 - 2 * t / d * 100),
        ("battery",     lambda t: 60 + 8 * math.sin(t * 0.25)),
        # Above-threshold (start hidden):
        ("throttle",    lambda t: 40 + 35 * math.sin(t * 1.1)),
        ("steering",    lambda t: 20 * math.sin(t * 0.4)),
        ("brakeForce",  lambda t: max(0, 30 * math.sin(t * 0.9))),
    ]
    _feed_plotter_direct(w, duration_s, hz, sigs)


def pose_plotter_empty(w: MainWindow) -> None:
    w.plotter_tab._backend.reset()


def pose_plotter_3sig(w: MainWindow) -> None:
    _feed_plotter_waveforms(w, duration_s=12, hz=50, n_signals=3)
    w.plotter_tab.window_combo.setCurrentIndex(1)  # 10s
    w.plotter_tab.cursors_btn.setChecked(False)
    w.plotter_tab.stats_btn.setChecked(False)


def pose_plotter_8sig(w: MainWindow) -> None:
    _feed_plotter_many_signals(w, duration_s=12, hz=50)
    w.plotter_tab.window_combo.setCurrentIndex(1)


def pose_plotter_cursors(w: MainWindow) -> None:
    _feed_plotter_waveforms(w, duration_s=20, hz=50, n_signals=3)
    w.plotter_tab.window_combo.setCurrentIndex(1)
    w.plotter_tab.cursors_btn.setChecked(True)


def pose_plotter_stats(w: MainWindow) -> None:
    _feed_plotter_waveforms(w, duration_s=20, hz=50, n_signals=3)
    w.plotter_tab.window_combo.setCurrentIndex(1)
    w.plotter_tab.stats_btn.setChecked(True)


def pose_ssh_terminal(w: MainWindow) -> None:
    t = w.ssh_tab
    if t.pc_combo.count():
        t.pc_combo.setCurrentIndex(0)
    t.cmd_input.setText("dir c:\\2026\\renato")
    t.local_path_input.setText(r"C:\Users\renato\firmware.hex")
    t.remote_path_input.setText(r"c:\2026\renato")
    t.log.clear()
    for line in [
        "[SSH] Connecting to 172.20.36.217...",
        "[SSH] Running: dir c:\\2026\\renato",
        " Volume in drive C is Windows",
        " Volume Serial Number is 1A2B-3C4D",
        "",
        " Directory of c:\\2026\\renato",
        "",
        "18/04/2026  10:44    <DIR>          .",
        "18/04/2026  10:44    <DIR>          ..",
        "18/04/2026  10:41             6.384 dashboard_full.hex",
        "18/04/2026  09:12             2.117 serialterm.py",
        "18/04/2026  08:03             1.853 reset.ps1",
        "               3 File(s)         10.354 bytes",
        "[SSH] Process exited with code 0",
    ]:
        t.log.append_log(line)


def pose_setup(w: MainWindow) -> None:
    t = w.setup_tab
    # Mark everything green if the helper exists
    for name in list(getattr(t, "_status_labels", {}).keys()):
        lbl = t._status_labels[name]
        lbl.setStyleSheet(
            "background: #44aa44; color: white; border-radius: 10px;"
            " padding: 2px 8px; font-weight: bold;"
        )
        lbl.setText("OK")
    if hasattr(t, "log"):
        t.log.clear()
        t.log.append_log("[Setup] Python 3.11.2 — OK")
        t.log.append_log("[Setup] arduino-cli 1.4.1 — OK")
        t.log.append_log("[Setup] tectonic 0.15.0 — OK")
        t.log.append_log("[Setup] Trampoline RTOS goil — OK")
        t.log.append_log("[Setup] All checks passed.")


# ─────────────────────────────────────────────────────────────────────────
# Shot list — (setter, subwidget-or-None, tab_index, filename, pre-delay)
#
# subwidget lets us grab just a portion of the window (for close-ups).
# When None, the full window is grabbed.
# ─────────────────────────────────────────────────────────────────────────

def grab(widget, out_path: Path) -> None:
    widget.grab().save(str(out_path))
    print(f"  saved {out_path.name}")


_CAM_PIXMAP: QPixmap | None = None


def set_camera_image(w: MainWindow) -> None:
    """Paint cameras.png into the CameraPanel's image_label so the live
    feed looks real in every shot where the panel is visible."""
    global _CAM_PIXMAP
    if _CAM_PIXMAP is None:
        path = OUT / "cameras.png"
        if not path.exists():
            return
        _CAM_PIXMAP = QPixmap(str(path))
    label = w.camera_panel.image_label
    if _CAM_PIXMAP.isNull() or label.size().width() < 2:
        return
    scaled = _CAM_PIXMAP.scaled(
        label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
    )
    label.setPixmap(scaled)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Remote Firmware Flasher")

    # Disable HiDPI scaling so every PNG has the same pixel dimensions.
    if hasattr(Qt, "AA_DisableHighDpiScaling"):
        app.setAttribute(Qt.AA_DisableHighDpiScaling)

    w = MainWindow()
    w.setAttribute(Qt.WA_DontShowOnScreen, True)
    w.resize(1500, 820)
    w.show()
    _pump(app, 5)

    tabs: QTabWidget = w.tabs

    # Tab indices (from main_window.py)
    IDX_VPN = 0
    IDX_FLASH = 1
    IDX_CAN = 2
    IDX_SERIAL = 3
    IDX_DASHBOARD = 4
    IDX_PLOTTER = 5
    IDX_SSH = 6
    IDX_SETUP = 7

    # ── VPN ──────────────────────────────────────────────────────────
    tabs.setCurrentIndex(IDX_VPN)
    pose_vpn_connected(w)
    _pump(app, 3)
    grab(w, OUT / "01_vpn_connected.png")

    pose_health_check(w)
    _pump(app, 3)
    grab(w, OUT / "02_vpn_health_check.png")

    # ── Flash ────────────────────────────────────────────────────────
    tabs.setCurrentIndex(IDX_FLASH)
    pose_flash_ready(w)
    _pump(app, 3)
    set_camera_image(w)
    _pump(app, 1)
    grab(w, OUT / "03_flash_ready.png")

    pose_flash_success(w)
    _pump(app, 3)
    set_camera_image(w)
    _pump(app, 1)
    grab(w, OUT / "04_flash_success.png")

    # ── Serial ──────────────────────────────────────────────────────
    tabs.setCurrentIndex(IDX_SERIAL)
    pose_serial_single(w)
    _pump(app, 3)
    set_camera_image(w)
    _pump(app, 1)
    grab(w, OUT / "05_serial_single.png")

    pose_serial_2x2(w)
    _pump(app, 4)
    set_camera_image(w)
    _pump(app, 1)
    grab(w, OUT / "06_serial_2x2.png")
    # VIO close-up from the first panel
    vio = w.serial_tab.panels[0].vio_panel
    _pump(app, 2)
    grab(vio, OUT / "07_serial_vio_closeup.png")

    # ── Dashboard HMI ───────────────────────────────────────────────
    tabs.setCurrentIndex(IDX_DASHBOARD)
    # Feed the dashboard backend once so the bridge has valid initial state.
    pose_hmi_electric(w)
    _pump(app, 6)  # QML needs a few extra pumps
    grab(w, OUT / "08_dashboard_electric.png")

    pose_hmi_auto(w)
    _pump(app, 6)
    grab(w, OUT / "09_dashboard_auto.png")

    pose_hmi_manual(w)
    _pump(app, 6)
    grab(w, OUT / "10_dashboard_manual.png")

    # ── Plotter ─────────────────────────────────────────────────────
    tabs.setCurrentIndex(IDX_PLOTTER)
    pose_plotter_empty(w)
    _pump(app, 3)
    grab(w, OUT / "11_plotter_empty.png")

    pose_plotter_3sig(w)
    _pump(app, 8)  # let the 30 Hz refresh paint the curves
    grab(w, OUT / "12_plotter_3signals.png")

    pose_plotter_8sig(w)
    _pump(app, 8)
    grab(w, OUT / "13_plotter_8signals_autohide.png")

    pose_plotter_cursors(w)
    _pump(app, 8)
    grab(w, OUT / "14_plotter_cursors.png")

    pose_plotter_stats(w)
    _pump(app, 8)
    grab(w, OUT / "15_plotter_stats.png")

    # ── SSH + Setup ─────────────────────────────────────────────────
    tabs.setCurrentIndex(IDX_SSH)
    pose_ssh_terminal(w)
    _pump(app, 3)
    set_camera_image(w)
    _pump(app, 1)
    grab(w, OUT / "16_ssh_terminal.png")

    tabs.setCurrentIndex(IDX_SETUP)
    pose_setup(w)
    _pump(app, 3)
    grab(w, OUT / "17_setup.png")

    print(f"\nDone. {len(list(OUT.glob('*.png')))} PNGs in {OUT}")


if __name__ == "__main__":
    main()

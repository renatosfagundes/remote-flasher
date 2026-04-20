"""Serial terminal tab — up to 4 independent connections with spatial layout."""
import os
import threading
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QFrame, QSplitter, QCheckBox,
    QSlider, QGroupBox, QMessageBox, QSizePolicy,
)

from lab_config import COMPUTERS, SERIAL_DEFAULTS
from settings import get_remote_user_dir
from widgets import LogWidget, ToggleSwitch
from workers import SerialWorker, SCPWorker


# ---------------------------------------------------------------------------
# Virtual I/O Panel
# ---------------------------------------------------------------------------

class VirtualIOPanel(QFrame):
    """Virtual I/O: 4 buttons (input) + 4 LEDs (output) + 2 potentiometers (input).

    Protocol — GUI → Arduino (inputs):
        !B1:1 / !B1:0   — button pressed / released
        !P1:512          — potentiometer value (0–1023)

    Protocol — Arduino → GUI (outputs):
        !L1:1 / !L1:0   — LED on / off
        !L1:128          — LED brightness (0–255, 0=off)
    """
    command = Signal(str)  # emits the command string to send

    # LED colors (matching button colors)
    _LED_COLORS = ["#e74c3c", "#3498db", "#f1c40f", "#2ecc71"]  # red, blue, yellow, green
    _BTN_COLORS = ["#c0392b", "#2980b9", "#f39c12", "#27ae60"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "VirtualIOPanel { border: 1px solid #444; border-radius: 3px; "
            "background: #2a2a2a; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        # --- Buttons (round, 3D pushbutton style) ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        self._buttons = []
        self._btn_states = [False] * 4
        for i in range(4):
            btn_col = QVBoxLayout()
            btn_col.setSpacing(2)
            btn_col.setAlignment(Qt.AlignCenter)

            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(36, 36)  # resized dynamically in _update_button_sizes
            btn.setToolTip(
                f"Virtual button B{i+1} — sends !B{i+1}:1 when pressed, "
                f"!B{i+1}:0 when released."
            )
            btn.setStyleSheet(self._btn_style(False, self._BTN_COLORS[i]))
            btn.toggled.connect(
                lambda checked, idx=i, c=self._BTN_COLORS[i]: self._on_btn_toggle(idx, checked, c)
            )
            btn_col.addWidget(btn, alignment=Qt.AlignCenter)

            lbl = QLabel(f"B{i+1}")
            lbl.setStyleSheet("color: #ccc; font-size: 9px; font-weight: bold;")
            lbl.setAlignment(Qt.AlignCenter)
            btn_col.addWidget(lbl)

            btn_layout.addLayout(btn_col)
            self._buttons.append(btn)
        layout.addLayout(btn_layout)

        # Separator
        layout.addWidget(self._make_separator())

        # --- LEDs (round indicators, controlled by Arduino) ---
        led_layout = QHBoxLayout()
        led_layout.setSpacing(6)
        self._leds = []
        self._led_values = [0] * 4
        for i in range(4):
            led_col = QVBoxLayout()
            led_col.setSpacing(2)
            led_col.setAlignment(Qt.AlignCenter)

            led = QLabel()
            led.setFixedSize(20, 20)
            led.setToolTip(
                f"Virtual LED L{i+1} — controlled by the Arduino via "
                f"!L{i+1}:<brightness> (0–255)."
            )
            led.setStyleSheet(self._led_style(0, self._LED_COLORS[i]))
            led_col.addWidget(led, alignment=Qt.AlignCenter)

            lbl = QLabel(f"L{i+1}")
            lbl.setStyleSheet("color: #ccc; font-size: 9px; font-weight: bold;")
            lbl.setAlignment(Qt.AlignCenter)
            led_col.addWidget(lbl)

            led_layout.addLayout(led_col)
            self._leds.append(led)
        layout.addLayout(led_layout)

        # Separator
        layout.addWidget(self._make_separator())

        # --- Potentiometers ---
        self._sliders = []
        self._slider_labels = []
        self._throttle_timers = []
        for i in range(2):
            pot_layout = QVBoxLayout()
            pot_layout.setSpacing(1)

            label = QLabel(f"POT{i+1}: 0")
            label.setStyleSheet("color: #aaa; font-size: 10px;")
            label.setAlignment(Qt.AlignCenter)
            label.setFixedWidth(90)
            pot_layout.addWidget(label)

            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 1023)
            slider.setValue(0)
            slider.setFixedWidth(90)
            slider.setToolTip(
                f"Virtual potentiometer P{i+1} — sends !P{i+1}:<0-1023> "
                "when the slider moves (throttled to 20 updates/s)."
            )
            slider.setStyleSheet(
                "QSlider::groove:horizontal { background: #3c3c3c; height: 6px; "
                "border-radius: 3px; }"
                "QSlider::handle:horizontal { background: #0d47a1; width: 14px; "
                "margin: -4px 0; border-radius: 7px; }"
                "QSlider::sub-page:horizontal { background: #1565c0; border-radius: 3px; }"
            )

            # Parent to `self` so Qt owns it and stops/destroys it together
            # with the VirtualIOPanel — avoids orphan timers firing after
            # the panel is gone and the sliders are deleted.
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(50)
            timer.timeout.connect(lambda idx=i: self._send_pot(idx))
            self._throttle_timers.append(timer)

            slider.valueChanged.connect(
                lambda val, idx=i, lbl=label: self._on_slider_change(idx, val, lbl)
            )
            pot_layout.addWidget(slider)

            layout.addLayout(pot_layout)
            self._sliders.append(slider)
            self._slider_labels.append(label)

        layout.addStretch()

    @staticmethod
    def _make_separator():
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #555;")
        return sep

    @staticmethod
    def _btn_style(pressed, color="#c0392b", diameter=36):
        # Half the diameter = circular border. Scales with the dynamic size.
        r = diameter // 2
        if pressed:
            return (
                f"QPushButton {{"
                f"  background: qradialgradient(cx:0.5, cy:0.5, radius:0.7, "
                f"    fx:0.5, fy:0.6, stop:0 {color}, stop:1 #1a1a1a);"
                f"  border: 3px solid #111;"
                f"  border-radius: {r}px;"
                f"  padding: 0;"
                f"}}"
            )
        return (
            f"QPushButton {{"
            f"  background: qradialgradient(cx:0.4, cy:0.35, radius:0.8, "
            f"    fx:0.4, fy:0.3, stop:0 #666, stop:0.6 #3c3c3c, stop:1 #222);"
            f"  border: 2px solid #555;"
            f"  border-radius: {r}px;"
            f"  padding: 0;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: qradialgradient(cx:0.4, cy:0.35, radius:0.8, "
            f"    fx:0.4, fy:0.3, stop:0 #888, stop:0.6 #4a4a4a, stop:1 #2a2a2a);"
            f"  border-color: #777;"
            f"}}"
        )

    @staticmethod
    def _led_style(brightness, color="#e74c3c"):
        """Generate LED style — off (dim) to on (glowing) based on brightness 0–255."""
        if brightness == 0:
            return (
                "QLabel {"
                "  background: qradialgradient(cx:0.5, cy:0.5, radius:0.6, "
                "    fx:0.5, fy:0.5, stop:0 #333, stop:1 #1a1a1a);"
                "  border: 2px solid #222;"
                "  border-radius: 10px;"
                "}"
            )
        # Scale the glow: blend from dim color to bright with white center
        t = brightness / 255.0  # 0.0 to 1.0
        # Parse hex color to RGB for blending
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        # Dim version (30% of color)
        dr, dg, db = int(r * 0.3), int(g * 0.3), int(b * 0.3)
        # Interpolate center color between dim and full
        cr = int(dr + (r - dr) * t)
        cg = int(dg + (g - dg) * t)
        cb = int(db + (b - db) * t)
        center = f"#{cr:02x}{cg:02x}{cb:02x}"
        # White highlight only at high brightness
        highlight = f"#{min(255,cr+int(80*t)):02x}{min(255,cg+int(80*t)):02x}{min(255,cb+int(80*t)):02x}"
        # Border brightness
        br_border = f"#{int(r*t):02x}{int(g*t):02x}{int(b*t):02x}"
        return (
            f"QLabel {{"
            f"  background: qradialgradient(cx:0.5, cy:0.4, radius:0.6, "
            f"    fx:0.5, fy:0.35, stop:0 {highlight}, stop:0.3 {center}, stop:1 #1a1a1a);"
            f"  border: 2px solid {br_border};"
            f"  border-radius: 10px;"
            f"}}"
        )

    def _on_btn_toggle(self, idx, checked, color="#c0392b"):
        self._btn_states[idx] = checked
        d = self._buttons[idx].width()  # use current dynamic diameter
        self._buttons[idx].setStyleSheet(self._btn_style(checked, color, d))
        self.command.emit(f"!B{idx+1}:{1 if checked else 0}")

    def _on_slider_change(self, idx, value, label):
        label.setText(f"POT{idx+1}: {value}")
        self._throttle_timers[idx].start()

    def _send_pot(self, idx):
        # Guard: the timer can fire after the panel is being destroyed, at
        # which point the Qt slider object may already be deleted even though
        # the Python wrapper still exists. Accessing it would raise
        # RuntimeError from shiboken.
        if idx >= len(self._sliders):
            return
        try:
            value = self._sliders[idx].value()
        except RuntimeError:
            return  # slider deleted — nothing to do
        self.command.emit(f"!P{idx+1}:{value}")

    def set_led(self, idx, brightness):
        """Set a virtual LED brightness (0–255). Called when Arduino sends !Ln:value."""
        if 0 <= idx < 4:
            self._led_values[idx] = brightness
            self._leds[idx].setStyleSheet(
                self._led_style(brightness, self._LED_COLORS[idx])
            )

    def parse_output_line(self, line):
        """Parse a serial output line for LED commands (!L1:255). Returns True if consumed."""
        line = line.strip()
        if line.startswith("!L") and ":" in line and len(line) >= 5:
            try:
                idx = int(line[2]) - 1
                value = int(line[4:])
                self.set_led(idx, max(0, min(255, value)))
                return True
            except (ValueError, IndexError):
                pass
        return False

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        for btn in self._buttons:
            btn.setEnabled(enabled)
        for slider in self._sliders:
            slider.setEnabled(enabled)

    # VIO button sizing: default diameter 36, shrink only when the panel is
    # too narrow to fit 4 full-size circles side-by-side.
    VIO_BTN_MAX = 36
    VIO_BTN_MIN = 20
    VIO_POT_MAX = 90
    VIO_POT_MIN = 50

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reserve for LEDs (4×20 + inner spacing), separators, outer layout
        # margins and outer-layout spacings. What's left is shared between
        # 4 buttons and 2 pot sliders.
        reserved = 175
        avail = max(0, self.width() - reserved)

        # Two-stage shrink: give pots their minimum first so sliders stay
        # usable, then give the rest to buttons. Both clamp to their max.
        pot_w = (avail - 4 * self.VIO_BTN_MIN) // 2
        pot_w = max(self.VIO_POT_MIN, min(self.VIO_POT_MAX, pot_w))
        d = (avail - 2 * pot_w) // 4
        d = max(self.VIO_BTN_MIN, min(self.VIO_BTN_MAX, d))

        for i, btn in enumerate(self._buttons):
            if btn.width() != d:
                btn.setFixedSize(d, d)
                btn.setStyleSheet(
                    self._btn_style(btn.isChecked(), self._BTN_COLORS[i], d)
                )

        for slider, label in zip(self._sliders, self._slider_labels):
            if slider.width() != pot_w:
                slider.setFixedWidth(pot_w)
                label.setFixedWidth(pot_w)

    def reset(self):
        """Reset all controls to default state."""
        for i, btn in enumerate(self._buttons):
            btn.setChecked(False)
            self._btn_states[i] = False
        for slider in self._sliders:
            slider.setValue(0)
        for i in range(4):
            self._led_values[i] = 0
            self._leds[i].setStyleSheet(self._led_style(0, self._LED_COLORS[i]))


class SerialPanel(QFrame):
    """Compact serial connection panel — config in grid, log takes the space."""
    port_usage_changed = Signal()
    close_requested = Signal(object)
    # (self, target, checked) — target is "dashboard" or "plotter"
    feed_toggled = Signal(object, str, bool)

    def __init__(self, parent_tab, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("SerialPanel { border: 1px solid #555; border-radius: 4px; }")
        self._workers = []
        self._parent_tab = parent_tab
        self._connected_port_key = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        g = QGridLayout()
        g.setSpacing(4)

        g.addWidget(QLabel("Computer:"), 0, 0)
        self.pc_combo = QComboBox()
        self.pc_combo.addItems(COMPUTERS.keys())
        self.pc_combo.setToolTip("Lab PC to open the serial session on.")
        self.pc_combo.currentTextChanged.connect(self._on_pc_changed)
        g.addWidget(self.pc_combo, 0, 1)

        g.addWidget(QLabel("Remote Folder:"), 0, 2)
        self.remote_dir = QLineEdit(get_remote_user_dir())
        self.remote_dir.setPlaceholderText("Your folder on the remote PC")
        self.remote_dir.setToolTip(
            "Working folder on the remote PC for serialterm.py.\n"
            "Typically C:\\2026\\<your-username>."
        )
        g.addWidget(self.remote_dir, 0, 3, 1, 3)

        g.addWidget(QLabel("Board:"), 1, 0)
        self.board_combo = QComboBox()
        self.board_combo.setToolTip("Board on the selected PC. Filters the COM port list below.")
        self.board_combo.currentTextChanged.connect(self._on_board_changed)
        g.addWidget(self.board_combo, 1, 1)

        g.addWidget(QLabel("COM Port:"), 1, 2)
        self.port_combo = QComboBox()
        self.port_combo.setToolTip(
            "COM port on the remote PC to open.\n"
            "Must not be in use by avrdude or another panel."
        )
        g.addWidget(self.port_combo, 1, 3)

        g.addWidget(QLabel("Baudrate:"), 1, 4)
        self.baudrate = QComboBox()
        self.baudrate.setEditable(True)
        self.baudrate.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baudrate.setCurrentText(SERIAL_DEFAULTS["baudrate"])
        self.baudrate.setToolTip("Serial baudrate. Type a custom value if not listed.")
        g.addWidget(self.baudrate, 1, 5)

        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("Open Serial")
        self.connect_btn.setToolTip("Open / close the serial session over SSH.")
        self.connect_btn.clicked.connect(self._toggle_serial)
        btn_row.addWidget(self.connect_btn)

        self.feed_dash_cb = ToggleSwitch("Feed Dashboard")
        self.feed_dash_cb.setToolTip(
            "Route this serial's signal lines ($...) to the HMI Dashboard gauges."
        )
        self.feed_dash_cb.setEnabled(False)  # enabled when connected
        self.feed_dash_cb.toggled.connect(
            lambda c: self.feed_toggled.emit(self, "dashboard", c)
        )
        btn_row.addWidget(self.feed_dash_cb)

        self.feed_plot_cb = ToggleSwitch("Feed Plotter")
        self.feed_plot_cb.setToolTip(
            "Route this serial's signal lines ($...) to the Plotter tab."
        )
        self.feed_plot_cb.setEnabled(False)
        self.feed_plot_cb.toggled.connect(
            lambda c: self.feed_toggled.emit(self, "plotter", c)
        )
        btn_row.addWidget(self.feed_plot_cb)

        self.upload_btn = QPushButton("Upload serialterm.py")
        self.upload_btn.setToolTip("Upload serialterm.py to remote folder")
        self.upload_btn.clicked.connect(self._upload_serialterm)
        btn_row.addWidget(self.upload_btn)

        self.clear_btn = QPushButton("Clear Log")
        self.clear_btn.setToolTip("Clear this panel's log output (doesn't affect the connection).")
        self.clear_btn.clicked.connect(lambda: self.log.clear())
        btn_row.addWidget(self.clear_btn)

        self.close_panel_btn = QPushButton("X")
        self.close_panel_btn.setFixedSize(24, 24)
        self.close_panel_btn.setToolTip("Close this serial panel")
        self.close_panel_btn.setStyleSheet(
            "QPushButton { background: #8b0000; color: white; font-weight: bold; "
            "border-radius: 3px; padding: 0; } QPushButton:hover { background: #b22222; }"
        )
        self.close_panel_btn.clicked.connect(lambda: self.close_requested.emit(self))
        btn_row.addWidget(self.close_panel_btn)

        g.addLayout(btn_row, 2, 0, 1, 6)
        layout.addLayout(g)

        self.log = LogWidget()
        layout.addWidget(self.log, stretch=1)

        send_row = QHBoxLayout()
        send_row.setSpacing(4)
        self.autoscroll_cb = QCheckBox("Autoscroll")
        self.autoscroll_cb.setChecked(True)
        self.autoscroll_cb.toggled.connect(lambda v: setattr(self.log, 'autoscroll', v))
        send_row.addWidget(self.autoscroll_cb)

        self.filter_signals_cb = QCheckBox("Filter Signals")
        self.filter_signals_cb.setToolTip(
            "Hide signal lines ($...) and VIO commands (!...) from the log.\n"
            "They're still routed to the Dashboard/Plotter if those are enabled."
        )
        self.filter_signals_cb.setChecked(False)
        send_row.addWidget(self.filter_signals_cb)

        self.timestamp_cb = QCheckBox("Timestamp")
        self.timestamp_cb.setToolTip(
            "Prepend [HH:MM:SS.mmm] to every incoming serial line.\n"
            "Stamps are generated when the line arrives at the GUI, not on\n"
            "the device — fine for timing relative to the host clock, off\n"
            "by the remote/SSH hop latency compared to absolute device time."
        )
        self.timestamp_cb.setChecked(False)
        send_row.addWidget(self.timestamp_cb)
        self.send_input = QLineEdit()
        self.send_input.setPlaceholderText("Type command to send over serial...")
        self.send_input.returnPressed.connect(self._send_command)
        self.send_input.setEnabled(False)
        send_row.addWidget(self.send_input)
        self.send_btn = QPushButton("Send")
        self.send_btn.setToolTip("Send the typed text to the remote serial (adds newline).")
        self.send_btn.clicked.connect(self._send_command)
        self.send_btn.setEnabled(False)
        send_row.addWidget(self.send_btn)
        layout.addLayout(send_row)

        # --- Virtual I/O panel ---
        self.vio_panel = VirtualIOPanel()
        self.vio_panel.setEnabled(False)
        self.vio_panel.command.connect(self._send_vio_command)
        layout.addWidget(self.vio_panel)

        self.serial_worker = None
        self._on_pc_changed(self.pc_combo.currentText())

    def get_connected_port_key(self):
        return self._connected_port_key

    def _get_pc_cfg(self):
        return COMPUTERS.get(self.pc_combo.currentText(), {})

    def _on_pc_changed(self, _text):
        pc = self._get_pc_cfg()
        self.board_combo.clear()
        self.board_combo.addItems(pc.get("boards", {}).keys())

    def _on_board_changed(self, _text):
        pc = self._get_pc_cfg()
        boards = pc.get("boards", {})
        board = boards.get(self.board_combo.currentText(), {})
        all_ports = board.get("ecu_ports", [])
        used = self._parent_tab.get_used_ports(exclude=self)
        pc_name = self.pc_combo.currentText()

        # Remember the currently selected port so we can restore it after
        # rebuilding the list — otherwise a refresh (e.g. after closing a
        # serial, which re-emits port_usage_changed) snaps the combo back
        # to index 0 and the user loses their selection.
        previous_port = self.port_combo.currentData() or self.port_combo.currentText()

        self.port_combo.clear()
        for p in all_ports:
            if (pc_name, p) in used:
                continue  # used by another local panel
            self.port_combo.addItem(p, userData=p)

        # Restore previous selection if the same port is still present.
        if previous_port:
            for i in range(self.port_combo.count()):
                if self.port_combo.itemData(i) == previous_port:
                    self.port_combo.setCurrentIndex(i)
                    break

    def refresh_ports(self):
        self._on_board_changed(None)

    def _toggle_serial(self):
        if self.serial_worker is not None:
            self._stop_serial()
        else:
            self._start_serial()

    # Auto-close after 10 minutes of no serial data
    IDLE_TIMEOUT_MS = 10 * 60 * 1000

    def _current_port(self) -> str:
        """Return the currently selected COM port name."""
        data = self.port_combo.currentData()
        if data:
            return str(data)
        return self.port_combo.currentText().strip()

    def _start_serial(self):
        pc = self._get_pc_cfg()
        port = self._current_port()
        if not port:
            return
        baud = self.baudrate.currentText()
        remote_dir = self.remote_dir.text().strip()
        self._connected_port_key = (self.pc_combo.currentText(), port)
        self.connect_btn.setText("Close Serial")
        self.send_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.vio_panel.setEnabled(True)
        self.feed_dash_cb.setEnabled(True)
        self.feed_plot_cb.setEnabled(True)
        self.pc_combo.setEnabled(False)
        self.board_combo.setEnabled(False)
        self.port_combo.setEnabled(False)
        self.baudrate.setEnabled(False)
        self.remote_dir.setEnabled(False)
        self.serial_worker = SerialWorker(
            pc["host"], pc["user"], pc["password"], port, baud, remote_dir
        )
        self.serial_worker.output.connect(self._on_serial_output)
        self.serial_worker.finished_signal.connect(self._on_serial_done)
        self._workers.append(self.serial_worker)
        self.serial_worker.start()
        self.port_usage_changed.emit()

        # Start idle timer — resets on every data received.
        if not hasattr(self, '_idle_timer'):
            self._idle_timer = QTimer(self)
            self._idle_timer.setSingleShot(True)
            self._idle_timer.timeout.connect(self._on_idle_timeout)
        self._idle_timer.start(self.IDLE_TIMEOUT_MS)

    def _send_command(self):
        if not self.serial_worker:
            return
        text = self.send_input.text()
        if not text:
            return
        self.log.append_log(f"> {text}")
        self.serial_worker.send_data(text)
        self.send_input.clear()

    def _on_serial_output(self, line):
        """Intercept serial output — parse VIO LED commands, pass rest to log."""
        # Reset idle timer on any data received
        if hasattr(self, '_idle_timer') and self._idle_timer.isActive():
            self._idle_timer.start(self.IDLE_TIMEOUT_MS)
        if self.vio_panel.parse_output_line(line):
            return  # VIO handled it
        # Optionally hide signal lines ($...) from the log; they still reach
        # the Dashboard/Plotter backends via the separate feed toggles.
        if self.filter_signals_cb.isChecked():
            s = line.strip()
            if s.startswith("$") or s.startswith("!"):
                return
        # Timestamp AFTER the filter so we don't stamp a line we drop.
        if self.timestamp_cb.isChecked():
            # HH:MM:SS.mmm — strftime has no ms specifier, so take %f
            # (microseconds, 6 digits) and trim to 3. Cheap enough at
            # serial rates (~20 Hz / panel).
            line = datetime.now().strftime("[%H:%M:%S.%f")[:-3] + "] " + line
        self.log.append_log(line)

    def _send_vio_command(self, cmd):
        """Send a Virtual I/O command (from buttons/sliders)."""
        if not self.serial_worker:
            return
        self.serial_worker.send_data(cmd)

    def _upload_serialterm(self):
        pc = self._get_pc_cfg()
        remote_dir = self.remote_dir.text().strip().replace("\\", "/")
        # serialterm.py lives next to this file's parent (src/)
        local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "serialterm.py")
        if not os.path.isfile(local_path):
            # Fallback: same directory as main.py
            local_path = os.path.join(os.path.dirname(__file__), "..", "serialterm.py")
        if not os.path.isfile(local_path):
            self.log.append_log("[Upload] serialterm.py not found!")
            return
        worker = SCPWorker(pc["host"], pc["user"], pc["password"], local_path, remote_dir)
        worker.output.connect(self.log.append_log)
        worker.finished_signal.connect(
            lambda ok: self.log.append_log(
                "[Upload] serialterm.py uploaded!" if ok else "[Upload] FAILED"
            )
        )
        self._workers.append(worker)
        worker.start()

    def _unlock_controls(self):
        self.connect_btn.setText("Open Serial")
        self.send_input.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.vio_panel.setEnabled(False)
        self.vio_panel.reset()
        self.feed_dash_cb.setEnabled(False)
        if self.feed_dash_cb.isChecked():
            self.feed_dash_cb.setChecked(False)
        self.feed_plot_cb.setEnabled(False)
        if self.feed_plot_cb.isChecked():
            self.feed_plot_cb.setChecked(False)
        self.pc_combo.setEnabled(True)
        self.board_combo.setEnabled(True)
        self.port_combo.setEnabled(True)
        self.baudrate.setEnabled(True)
        self.remote_dir.setEnabled(True)

    def _on_idle_timeout(self):
        """Auto-close serial connection after prolonged inactivity."""
        if self.serial_worker:
            self.log.append_log("[Serial] Auto-closed after 10 minutes of inactivity.")
            self._stop_serial()

    def _stop_serial(self):
        if hasattr(self, '_idle_timer'):
            self._idle_timer.stop()
        if self.serial_worker:
            self.serial_worker.stop()
            self.serial_worker.wait(3000)
            self.serial_worker = None
        self._connected_port_key = None
        self._unlock_controls()
        self.port_usage_changed.emit()

    def _on_serial_done(self):
        self._connected_port_key = None
        self.serial_worker = None
        self._unlock_controls()
        self.log.append_log("[Serial] Connection closed.")
        self.port_usage_changed.emit()

    def cleanup(self):
        self._stop_serial()


class SerialTab(QWidget):
    """Spatial serial layout: 1=full, 2=side-by-side, 3=2+1, 4=2x2 grid."""
    MAX_PANELS = 4
    panel_count_changed = Signal(int)
    # (panel, target, checked) where target is "dashboard" or "plotter"
    feed_toggled = Signal(object, str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.panels: list[SerialPanel] = []
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 4, 4, 0)
        self.add_btn = QPushButton("+ Add Serial")
        self.add_btn.setToolTip("Add a new serial connection (max 4)")
        self.add_btn.clicked.connect(self._add_panel)
        toolbar.addWidget(self.add_btn)
        toolbar.addStretch()
        self._outer.addLayout(toolbar)

        self._grid_container = QWidget()
        self._grid_layout = QVBoxLayout(self._grid_container)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._outer.addWidget(self._grid_container, stretch=1)

        self._add_panel()

    def _add_panel(self):
        if len(self.panels) >= self.MAX_PANELS:
            return
        panel = SerialPanel(parent_tab=self)
        panel.port_usage_changed.connect(self._refresh_all_ports)
        panel.close_requested.connect(self._remove_panel)
        panel.feed_toggled.connect(self._on_feed_toggled)
        self.panels.append(panel)
        self._rebuild_layout()
        self._update_add_btn()

    def _on_feed_toggled(self, panel, target, checked):
        """Ensure only one panel feeds a given target at a time, then bubble
        to MainWindow. Dashboard and plotter are independent targets."""
        attr = "feed_dash_cb" if target == "dashboard" else "feed_plot_cb"
        if checked:
            for p in self.panels:
                if p is not panel:
                    cb = getattr(p, attr, None)
                    if cb is not None and cb.isChecked():
                        cb.blockSignals(True)
                        cb.setChecked(False)
                        cb.blockSignals(False)
        self.feed_toggled.emit(panel, target, checked)

    def _remove_panel(self, panel):
        if panel in self.panels:
            panel.cleanup()
            self.panels.remove(panel)
            panel.setParent(None)
            panel.deleteLater()
        self._rebuild_layout()
        self._update_add_btn()
        if not self.panels:
            self._add_panel()

    def _rebuild_layout(self):
        old_layout = self._grid_container.layout()
        if old_layout is not None:
            for p in self.panels:
                p.setParent(None)
            while old_layout.count():
                item = old_layout.takeAt(0)
                w = item.widget()
                if w and w not in self.panels:
                    w.setParent(None)
                    w.deleteLater()
            QWidget().setLayout(old_layout)

        n = len(self.panels)
        EQUAL = 10000
        if n == 0:
            layout = QVBoxLayout(self._grid_container)
            layout.setContentsMargins(0, 0, 0, 0)
        elif n == 1:
            layout = QVBoxLayout(self._grid_container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.panels[0])
        elif n == 2:
            layout = QVBoxLayout(self._grid_container)
            layout.setContentsMargins(0, 0, 0, 0)
            h_split = QSplitter(Qt.Horizontal)
            h_split.addWidget(self.panels[0])
            h_split.addWidget(self.panels[1])
            h_split.setSizes([EQUAL, EQUAL])
            layout.addWidget(h_split)
        elif n == 3:
            layout = QVBoxLayout(self._grid_container)
            layout.setContentsMargins(0, 0, 0, 0)
            v_split = QSplitter(Qt.Vertical)
            top_split = QSplitter(Qt.Horizontal)
            top_split.addWidget(self.panels[0])
            top_split.addWidget(self.panels[1])
            top_split.setSizes([EQUAL, EQUAL])
            v_split.addWidget(top_split)
            v_split.addWidget(self.panels[2])
            v_split.setSizes([EQUAL, EQUAL])
            layout.addWidget(v_split)
        elif n == 4:
            layout = QVBoxLayout(self._grid_container)
            layout.setContentsMargins(0, 0, 0, 0)
            v_split = QSplitter(Qt.Vertical)
            top_split = QSplitter(Qt.Horizontal)
            top_split.addWidget(self.panels[0])
            top_split.addWidget(self.panels[1])
            top_split.setSizes([EQUAL, EQUAL])
            bot_split = QSplitter(Qt.Horizontal)
            bot_split.addWidget(self.panels[2])
            bot_split.addWidget(self.panels[3])
            bot_split.setSizes([EQUAL, EQUAL])
            v_split.addWidget(top_split)
            v_split.addWidget(bot_split)
            v_split.setSizes([EQUAL, EQUAL])
            layout.addWidget(v_split)

        for p in self.panels:
            p.close_panel_btn.setVisible(n > 1)
        self.panel_count_changed.emit(n)

    def _update_add_btn(self):
        self.add_btn.setEnabled(len(self.panels) < self.MAX_PANELS)

    def get_used_ports(self, exclude=None):
        used = set()
        for panel in self.panels:
            if panel is exclude:
                continue
            key = panel.get_connected_port_key()
            if key:
                used.add(key)
        return used

    def _refresh_all_ports(self):
        for panel in self.panels:
            if panel.serial_worker is None:
                panel.refresh_ports()

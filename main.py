"""
Remote Firmware Flasher — PySide6 desktop application.
Connect via VPN + SSH to flash Arduino boards in the lab and watch cameras.
"""
import sys
import os
import time
import subprocess
import threading
from pathlib import Path
from io import BytesIO

import json
import base64
import re

import paramiko
import requests
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QPixmap, QImage, QFont, QIcon, QColor
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QTabWidget,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QFileDialog,
    QSplitter,
    QStatusBar,
    QMessageBox,
    QCheckBox,
    QSpinBox,
    QPlainTextEdit,
    QFrame,
    QSizePolicy,
)

from lab_config import COMPUTERS, AVRDUDE_DEFAULTS, SERIAL_DEFAULTS, REMOTE_BASE_DIR, REMOTE_SCRIPTS_DIR, REMOTE_USER_DIR

# App directory — where the script/exe lives (used for icon, etc.)
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

# User settings — stored in AppData so the exe can live anywhere
_SETTINGS_DIR = os.path.join(os.environ.get("APPDATA", _APP_DIR), "RemoteFlasher")
os.makedirs(_SETTINGS_DIR, exist_ok=True)
_SETTINGS_FILE = os.path.join(_SETTINGS_DIR, "settings.json")


def _load_settings() -> dict:
    """Load saved user settings from the local .user_settings.json file."""
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Decode obfuscated password (base64, not encryption — just avoids plain text)
        if "vpn_password" in data:
            data["vpn_password"] = base64.b64decode(data["vpn_password"]).decode("utf-8")
        return data
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return {}


def _save_settings(**kwargs):
    """Save settings to the local .user_settings.json file (merges with existing)."""
    data = _load_settings()
    # Re-encode password before merging
    if "vpn_password" in data:
        data["vpn_password"] = base64.b64encode(data["vpn_password"].encode("utf-8")).decode("ascii")
    for k, v in kwargs.items():
        if k == "vpn_password":
            data[k] = base64.b64encode(v.encode("utf-8")).decode("ascii")
        else:
            data[k] = v
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _get_remote_user_dir() -> str:
    """Get the user's remote folder, falling back to lab_config default."""
    settings = _load_settings()
    return settings.get("remote_user_dir", REMOTE_USER_DIR)


# Legacy compat aliases
_CREDENTIALS_FILE = _SETTINGS_FILE

def _load_credentials() -> dict:
    return _load_settings()

def _save_credentials(username: str, password: str):
    _save_settings(vpn_username=username, vpn_password=password)


def _clear_credentials():
    """Remove the saved credentials file."""
    try:
        os.remove(_CREDENTIALS_FILE)
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Helper threads
# ---------------------------------------------------------------------------

class SSHWorker(QThread):
    """Run a command over SSH in a background thread."""
    output = Signal(str)
    finished_signal = Signal(str)  # exit status as string (avoids int overflow)

    def __init__(self, host, user, password, command, parent=None):
        super().__init__(parent)
        self.host = host
        self.user = user
        self.password = password
        self.command = command
        self._stop = False

    def run(self):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.output.emit(f"[SSH] Connecting to {self.host}...")
            client.connect(
                self.host, username=self.user, password=self.password, timeout=15
            )
            self.output.emit(f"[SSH] Running: {self.command}")
            stdin, stdout, stderr = client.exec_command(self.command, timeout=120)
            # Read raw bytes and decode with fallback for Windows cp850/cp1252 output
            raw_out = stdout.read()
            raw_err = stderr.read()
            for line in raw_out.decode("utf-8", errors="replace").splitlines():
                if self._stop:
                    break
                self.output.emit(line)
            for line in raw_err.decode("utf-8", errors="replace").splitlines():
                if self._stop:
                    break
                self.output.emit(f"[STDERR] {line}")
            exit_status = stdout.channel.recv_exit_status()
            # Convert to signed 32-bit if needed (Windows returns large unsigned values)
            if exit_status > 0x7FFFFFFF:
                exit_status = exit_status - 0x100000000
            client.close()
            self.finished_signal.emit(str(exit_status))
        except Exception as e:
            self.output.emit(f"[ERROR] {e}")
            self.finished_signal.emit("-1")

    def stop(self):
        self._stop = True


class SCPWorker(QThread):
    """Upload a file via SFTP (SCP) in a background thread."""
    output = Signal(str)
    finished_signal = Signal(bool)

    def __init__(self, host, user, password, local_path, remote_path, parent=None):
        super().__init__(parent)
        self.host = host
        self.user = user
        self.password = password
        self.local_path = local_path
        self.remote_path = remote_path

    def run(self):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.output.emit(f"[SCP] Connecting to {self.host}...")
            client.connect(
                self.host, username=self.user, password=self.password, timeout=15
            )
            sftp = client.open_sftp()
            filename = os.path.basename(self.local_path)
            remote_file = f"{self.remote_path}/{filename}"
            self.output.emit(f"[SCP] Uploading {filename} -> {remote_file}")
            sftp.put(self.local_path, remote_file)
            sftp.close()
            client.close()
            self.output.emit(f"[SCP] Upload complete: {remote_file}")
            self.finished_signal.emit(True)
        except Exception as e:
            self.output.emit(f"[SCP ERROR] {e}")
            self.finished_signal.emit(False)


class CameraWorker(QThread):
    """Fetch MJPEG frames from a camera URL."""
    frame_ready = Signal(QImage)
    error = Signal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self._running = True

    def run(self):
        try:
            resp = requests.get(self.url, stream=True, timeout=10)
            buf = b""
            for chunk in resp.iter_content(chunk_size=4096):
                if not self._running:
                    break
                buf += chunk
                # Look for JPEG frame boundaries
                start = buf.find(b"\xff\xd8")
                end = buf.find(b"\xff\xd9")
                if start != -1 and end != -1 and end > start:
                    jpg = buf[start : end + 2]
                    buf = buf[end + 2 :]
                    img = QImage()
                    img.loadFromData(jpg)
                    if not img.isNull():
                        self.frame_ready.emit(img)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._running = False


class SerialWorker(QThread):
    """Open a remote serial terminal via SSH and stream output."""
    output = Signal(str)
    finished_signal = Signal()

    def __init__(self, host, user, password, com_port, baudrate, remote_dir, parent=None):
        super().__init__(parent)
        self.host = host
        self.user = user
        self.password = password
        self.com_port = com_port
        self.baudrate = baudrate
        self.remote_dir = remote_dir
        self._running = True
        self._client = None
        self._channel = None

    # Regex to strip ANSI escape sequences and OSC window-title sequences
    _ANSI_RE = re.compile(
        r'\x1b\[[0-9;]*[A-Za-z]'   # CSI sequences: ESC[ ... letter
        r'|\x1b\][^\x07]*\x07'     # OSC sequences: ESC] ... BEL
        r'|\x1b\][\x20-\x7e]*'     # truncated OSC
        r'|\x1b[()][0-9A-Za-z]'    # charset selects
        r'|\x1b\[\?[0-9;]*[A-Za-z]'  # private mode: ESC[? ... letter
    )

    def _clean(self, text: str) -> str:
        """Remove ANSI/VT100 escape sequences from text."""
        return self._ANSI_RE.sub("", text)

    def run(self):
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.output.emit(f"[Serial] Connecting to {self.host}...")
            self._client.connect(
                self.host,
                username=self.user,
                password=self.password,
                timeout=15,
            )
            cmd = (
                f"cd {self.remote_dir}"
                f" && copy {REMOTE_BASE_DIR}\\serialterm.py . >nul 2>&1"
                f" & python serialterm.py --port {self.com_port} --baudrate {self.baudrate}"
            )
            self.output.emit(f"[Serial] Running: {cmd}")
            self._channel = self._client.get_transport().open_session()
            self._channel.get_pty()  # allocate a PTY so remote output is not buffered
            self._channel.exec_command(cmd)
            while self._running:
                if self._channel.recv_ready():
                    data = self._channel.recv(4096).decode("utf-8", errors="replace")
                    cleaned = self._clean(data)
                    for line in cleaned.splitlines():
                        line = line.strip()
                        if line:
                            self.output.emit(line)
                elif self._channel.recv_stderr_ready():
                    data = self._channel.recv_stderr(4096).decode("utf-8", errors="replace")
                    cleaned = self._clean(data)
                    for line in cleaned.splitlines():
                        line = line.strip()
                        if line:
                            self.output.emit(f"[STDERR] {line}")
                elif self._channel.exit_status_ready():
                    # Drain remaining output
                    while self._channel.recv_ready():
                        data = self._channel.recv(4096).decode("utf-8", errors="replace")
                        cleaned = self._clean(data)
                        for line in cleaned.splitlines():
                            line = line.strip()
                            if line:
                                self.output.emit(line)
                    exit_code = self._channel.recv_exit_status()
                    self.output.emit(f"[Serial] Process exited with code {exit_code}")
                    break
                else:
                    time.sleep(0.05)
            self._client.close()
        except Exception as e:
            self.output.emit(f"[Serial ERROR] {e}")
        self.finished_signal.emit()

    def stop(self):
        self._running = False
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# UI Widgets
# ---------------------------------------------------------------------------

class LogWidget(QPlainTextEdit):
    """Read-only log output area."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 9))
        self.setMaximumBlockCount(5000)
        self.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #3c3c3c;"
        )

    def append_log(self, text: str):
        self.appendPlainText(text)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


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


# ---------------------------------------------------------------------------
# VPN Tab
# ---------------------------------------------------------------------------

class VPNTab(QWidget):
    vpn_status_changed = Signal(bool)
    _log_signal = Signal(str)
    _status_signal = Signal(str, str, bool)  # indicator_status, label_text, connected

    # Default Windows SSTP VPN settings for CIN
    DEFAULT_VPN_NAME = "VPN_CIN"
    DEFAULT_VPN_ADDRESS = "vpn.cin.ufpe.br"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        layout = QVBoxLayout(self)

        # VPN Config
        grp = QGroupBox("VPN CIN (SSTP — Windows built-in)")
        g = QGridLayout(grp)

        g.addWidget(QLabel("Connection Name:"), 0, 0)
        self.vpn_name = QLineEdit(self.DEFAULT_VPN_NAME)
        g.addWidget(self.vpn_name, 0, 1, 1, 2)

        g.addWidget(QLabel("Server Address:"), 1, 0)
        self.vpn_address = QLineEdit(self.DEFAULT_VPN_ADDRESS)
        self.vpn_address.setReadOnly(True)
        g.addWidget(self.vpn_address, 1, 1, 1, 2)

        g.addWidget(QLabel("Username:"), 2, 0)
        self.vpn_user = QLineEdit()
        self.vpn_user.setPlaceholderText("Your CIN username")
        g.addWidget(self.vpn_user, 2, 1, 1, 2)

        g.addWidget(QLabel("Password:"), 3, 0)
        self.vpn_pass = QLineEdit()
        self.vpn_pass.setEchoMode(QLineEdit.Password)
        self.vpn_pass.setPlaceholderText("Your CIN password")
        g.addWidget(self.vpn_pass, 3, 1, 1, 2)

        self.remember_cb = QCheckBox("Remember me")
        self.remember_cb.setToolTip(
            "Save credentials locally in .credentials.json (not shared with source code)"
        )
        self.remember_cb.toggled.connect(self._on_remember_toggled)
        g.addWidget(self.remember_cb, 4, 1)

        # Load saved credentials if they exist
        saved = _load_credentials()
        if saved.get("vpn_username"):
            self.vpn_user.setText(saved["vpn_username"])
            self.vpn_pass.setText(saved.get("vpn_password", ""))
            self.remember_cb.setChecked(True)

        btn_row = QHBoxLayout()
        self.status_indicator = StatusIndicator()
        btn_row.addWidget(self.status_indicator)
        self.status_label = QLabel("Disconnected")
        btn_row.addWidget(self.status_label)
        btn_row.addStretch()

        self.connect_btn = QPushButton("Connect VPN")
        self.connect_btn.clicked.connect(self._toggle_vpn)
        btn_row.addWidget(self.connect_btn)

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self.test_btn)

        self.setup_btn = QPushButton("Setup VPN Profile")
        self.setup_btn.setToolTip(
            "Create the Windows SSTP VPN profile automatically (only needed once)"
        )
        self.setup_btn.clicked.connect(self._setup_vpn_profile)
        btn_row.addWidget(self.setup_btn)

        g.addLayout(btn_row, 5, 0, 1, 3)
        layout.addWidget(grp)

        # Hint
        hint = QGroupBox("Info")
        hl = QVBoxLayout(hint)
        hl.addWidget(
            QLabel(
                "Click 'Setup VPN Profile' once to create the Windows SSTP VPN connection.\n"
                "After that, enter your CIN credentials and click 'Connect VPN'.\n\n"
                "If you're already connected, click 'Test Connection' to verify."
            )
        )
        layout.addWidget(hint)

        self.log = LogWidget()
        layout.addWidget(self.log)

        # Connect thread-safe signals
        self._log_signal.connect(self.log.append_log)
        self._status_signal.connect(self._apply_status)

    def _on_remember_toggled(self, checked):
        if checked:
            user = self.vpn_user.text().strip()
            passwd = self.vpn_pass.text().strip()
            if user and passwd:
                _save_credentials(user, passwd)
        else:
            _clear_credentials()

    def _apply_status(self, indicator: str, label: str, connected: bool):
        """Apply status update on the main thread."""
        self.status_indicator.set_status(indicator)
        self.status_label.setText(label)
        self._connected = connected
        self.connect_btn.setText("Disconnect VPN" if connected else "Connect VPN")
        self.vpn_status_changed.emit(connected)

    def _toggle_vpn(self):
        if self._connected:
            self._disconnect_vpn()
        else:
            self._connect_vpn()

    def _setup_vpn_profile(self):
        """Create the Windows SSTP VPN profile via PowerShell."""
        name = self.vpn_name.text().strip()
        address = self.vpn_address.text().strip()
        if not name or not address:
            self.log.append_log("[VPN Setup] Name and address are required.")
            return

        self.log.append_log(f"[VPN Setup] Creating SSTP profile '{name}' -> {address}...")
        threading.Thread(
            target=self._do_setup_vpn, args=(name, address), daemon=True
        ).start()

    def _do_setup_vpn(self, name, address):
        # First check if it already exists
        check_cmd = (
            f'Get-VpnConnection -Name "{name}" -ErrorAction SilentlyContinue'
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", check_cmd],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if name in result.stdout:
                self._log_signal.emit(
                    f"[VPN Setup] Profile '{name}' already exists. Removing to recreate..."
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f'Remove-VpnConnection -Name "{name}" -Force'],
                    capture_output=True, text=True, timeout=15,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
        except Exception:
            pass

        # Create the SSTP VPN connection
        create_cmd = (
            f'Add-VpnConnection'
            f' -Name "{name}"'
            f' -ServerAddress "{address}"'
            f' -TunnelType Sstp'
            f' -AuthenticationMethod MSChapv2'
            f' -EncryptionLevel Required'
            f' -RememberCredential'
            f' -Force'
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", create_cmd],
                capture_output=True, text=True, timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                self._log_signal.emit(
                    f"[VPN Setup] Profile '{name}' created successfully!"
                )
                self._log_signal.emit(
                    "[VPN Setup] You can now enter your credentials and click 'Connect VPN'."
                )
            else:
                self._log_signal.emit(f"[VPN Setup] Failed (exit={result.returncode})")
                if result.stdout.strip():
                    self._log_signal.emit(result.stdout.strip())
                if result.stderr.strip():
                    self._log_signal.emit(result.stderr.strip())
        except Exception as e:
            self._log_signal.emit(f"[VPN Setup] Error: {e}")

    def _connect_vpn(self):
        name = self.vpn_name.text().strip()
        user = self.vpn_user.text().strip()
        passwd = self.vpn_pass.text().strip()

        if not name:
            self.log.append_log("[VPN] Please enter the VPN connection name.")
            return
        if not user or not passwd:
            self.log.append_log("[VPN] Please enter username and password.")
            return

        # Save credentials if remember is checked
        if self.remember_cb.isChecked():
            _save_credentials(user, passwd)

        self.status_indicator.set_status("connecting")
        self.status_label.setText("Connecting...")
        self.log.append_log(f"[VPN] Connecting to '{name}' as '{user}'...")

        # Run rasdial in a background thread to avoid freezing UI
        threading.Thread(
            target=self._rasdial_connect, args=(name, user, passwd), daemon=True
        ).start()

    def _rasdial_connect(self, name, user, passwd):
        try:
            result = subprocess.run(
                ["rasdial", name, user, passwd],
                capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                self._log_signal.emit("[VPN] Connected successfully!")
                self._log_signal.emit(result.stdout.strip())
                self._status_signal.emit("connected", "Connected", True)
            else:
                self._log_signal.emit(f"[VPN] Connection failed (exit={result.returncode})")
                self._log_signal.emit(result.stdout.strip())
                if result.stderr.strip():
                    self._log_signal.emit(result.stderr.strip())
                self._status_signal.emit("disconnected", "Failed", False)
        except subprocess.TimeoutExpired:
            self._log_signal.emit("[VPN] Connection timed out (30s).")
            self._status_signal.emit("disconnected", "Timeout", False)
        except Exception as e:
            self._log_signal.emit(f"[VPN] Error: {e}")
            self._status_signal.emit("disconnected", "Error", False)

    def _disconnect_vpn(self):
        name = self.vpn_name.text().strip()
        self.log.append_log(f"[VPN] Disconnecting '{name}'...")
        try:
            result = subprocess.run(
                ["rasdial", name, "/disconnect"],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.log.append_log(result.stdout.strip())
        except Exception as e:
            self.log.append_log(f"[VPN] Disconnect error: {e}")

        self._connected = False
        self.connect_btn.setText("Connect VPN")
        self.status_indicator.set_status("disconnected")
        self.status_label.setText("Disconnected")
        self.vpn_status_changed.emit(False)

    def _test_connection(self):
        self.log.append_log("[VPN] Testing connection to 172.20.36.217...")
        threading.Thread(target=self._do_test, daemon=True).start()

    def _do_test(self):
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "3000", "172.20.36.217"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                self._log_signal.emit("[VPN] SUCCESS — 172.20.36.217 is reachable!")
                self._status_signal.emit("connected", "Reachable", True)
            else:
                self._log_signal.emit("[VPN] FAILED — host not reachable. Is the VPN connected?")
                self._log_signal.emit(result.stdout.strip())
                self._status_signal.emit("disconnected", "Not reachable", False)
        except Exception as e:
            self._log_signal.emit(f"[VPN] Test error: {e}")


# ---------------------------------------------------------------------------
# Flash Tab
# ---------------------------------------------------------------------------

class FlashTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        layout = QVBoxLayout(self)

        # Top controls
        ctrl = QGroupBox("Firmware Flash")
        g = QGridLayout(ctrl)

        g.addWidget(QLabel("Computer:"), 0, 0)
        self.pc_combo = QComboBox()
        self.pc_combo.addItems(COMPUTERS.keys())
        self.pc_combo.currentTextChanged.connect(self._on_pc_changed)
        g.addWidget(self.pc_combo, 0, 1)

        g.addWidget(QLabel("Board:"), 1, 0)
        self.board_combo = QComboBox()
        g.addWidget(self.board_combo, 1, 1)
        self.board_combo.currentTextChanged.connect(self._on_board_changed)

        g.addWidget(QLabel("ECU COM Port:"), 2, 0)
        self.ecu_combo = QComboBox()
        g.addWidget(self.ecu_combo, 2, 1)

        g.addWidget(QLabel("HEX File:"), 3, 0)
        hex_row = QHBoxLayout()
        self.hex_path = QLineEdit()
        self.hex_path.setPlaceholderText("Select .hex firmware file...")
        hex_row.addWidget(self.hex_path)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_hex)
        hex_row.addWidget(browse)
        g.addLayout(hex_row, 3, 1)

        g.addWidget(QLabel("Remote Folder:"), 4, 0)
        self.remote_folder = QLineEdit(_get_remote_user_dir())
        self.remote_folder.setPlaceholderText("Your folder on the remote PC")
        g.addWidget(self.remote_folder, 4, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        self.upload_btn = QPushButton("1. Upload HEX")
        self.upload_btn.clicked.connect(self._upload_hex)
        btn_row.addWidget(self.upload_btn)

        self.reset_btn = QPushButton("2. Reset Board")
        self.reset_btn.clicked.connect(self._reset_board)
        btn_row.addWidget(self.reset_btn)

        self.flash_btn = QPushButton("3. Flash Firmware")
        self.flash_btn.clicked.connect(self._flash_firmware)
        btn_row.addWidget(self.flash_btn)

        self.flash_all_btn = QPushButton("Upload + Reset + Flash")
        self.flash_all_btn.setStyleSheet("background-color: #2d5a27; color: white; font-weight: bold;")
        self.flash_all_btn.clicked.connect(self._do_all)
        btn_row.addWidget(self.flash_all_btn)

        g.addLayout(btn_row, 5, 0, 1, 2)
        layout.addWidget(ctrl)

        self.log = LogWidget()
        layout.addWidget(self.log)

        # Initialize combos
        self._on_pc_changed(self.pc_combo.currentText())

    def _get_pc_cfg(self):
        return COMPUTERS.get(self.pc_combo.currentText(), {})

    def _get_board_cfg(self):
        pc = self._get_pc_cfg()
        boards = pc.get("boards", {})
        return boards.get(self.board_combo.currentText(), {})

    def _on_pc_changed(self, _text):
        pc = self._get_pc_cfg()
        self.board_combo.clear()
        self.board_combo.addItems(pc.get("boards", {}).keys())

    def _on_board_changed(self, _text):
        board = self._get_board_cfg()
        self.ecu_combo.clear()
        self.ecu_combo.addItems(board.get("ecu_ports", []))

    def _browse_hex(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select HEX file", "", "HEX Files (*.hex);;All (*)"
        )
        if path:
            self.hex_path.setText(path)

    def _upload_hex(self):
        pc = self._get_pc_cfg()
        local = self.hex_path.text().strip()
        if not local or not os.path.isfile(local):
            self.log.append_log("[Upload] Please select a valid .hex file.")
            return
        remote = self.remote_folder.text().strip().replace("\\", "/")
        worker = SCPWorker(
            pc["host"], pc["user"], pc["password"], local, remote
        )
        worker.output.connect(self.log.append_log)
        worker.finished_signal.connect(lambda ok: self.log.append_log(
            "[Upload] Done!" if ok else "[Upload] FAILED"
        ))
        self._workers.append(worker)
        worker.start()

    def _reset_board(self):
        pc = self._get_pc_cfg()
        board = self._get_board_cfg()
        reset_script = board.get("reset_script")
        reset_port = board.get("reset_port")

        if reset_script:
            cmd = f'cd {_get_remote_user_dir()} && copy {REMOTE_SCRIPTS_DIR}\\{reset_script} . >nul 2>&1 & powershell -ExecutionPolicy Bypass -File {reset_script}'
        elif reset_port and pc.get("flash_method") == "flash.py":
            # For PC 220 style, the reset is handled by flash.py
            self.log.append_log("[Reset] This PC uses flash.py — reset is integrated into flash.")
            return
        else:
            self.log.append_log("[Reset] No reset method configured for this board.")
            return

        self.log.append_log(f"[Reset] Sending reset signal...")
        worker = SSHWorker(pc["host"], pc["user"], pc["password"], cmd)
        worker.output.connect(self.log.append_log)
        worker.finished_signal.connect(
            lambda s: self.log.append_log(f"[Reset] Exit status: {s}")
        )
        self._workers.append(worker)
        worker.start()

    def _flash_firmware(self):
        pc = self._get_pc_cfg()
        board = self._get_board_cfg()
        ecu_port = self.ecu_combo.currentText()
        hex_name = os.path.basename(self.hex_path.text().strip())
        remote_dir = self.remote_folder.text().strip()

        if not hex_name:
            self.log.append_log("[Flash] No hex file specified.")
            return

        if pc.get("flash_method") == "flash.py":
            reset_port = board.get("reset_port", "")
            cmd = (
                f'cd {remote_dir} &&'
                f' copy {REMOTE_SCRIPTS_DIR}\\avrdude.conf . >nul 2>&1 &'
                f' python {REMOTE_BASE_DIR}\\flash.py'
                f' --reset_port {reset_port}'
                f' --flash_port {ecu_port}'
                f' --hex {hex_name}'
                f' --delay 0.4'
            )
        else:
            # Copy avrdude.conf from base dir to user folder, then flash
            cmd = (
                f'cd {remote_dir} &&'
                f' copy {REMOTE_SCRIPTS_DIR}\\avrdude.conf . >nul 2>&1 &'
                f' avrdude.exe -C avrdude.conf -v'
                f' -p {AVRDUDE_DEFAULTS["mcu"]}'
                f' -c {AVRDUDE_DEFAULTS["programmer"]}'
                f' -b {AVRDUDE_DEFAULTS["baudrate"]}'
                f' -P {ecu_port}'
                f' -U flash:w:{hex_name}:i'
            )

        self.log.append_log(f"[Flash] Executing: {cmd}")
        worker = SSHWorker(pc["host"], pc["user"], pc["password"], cmd)
        worker.output.connect(self.log.append_log)
        worker.finished_signal.connect(
            lambda s: self.log.append_log(
                f"[Flash] {'SUCCESS' if s == '0' else 'FAILED'} (exit={s})"
            )
        )
        self._workers.append(worker)
        worker.start()

    def _do_all(self):
        """Upload, reset, then flash — sequentially."""
        pc = self._get_pc_cfg()
        board = self._get_board_cfg()
        local = self.hex_path.text().strip()
        if not local or not os.path.isfile(local):
            self.log.append_log("[All] Please select a valid .hex file.")
            return

        remote = self.remote_folder.text().strip().replace("\\", "/")
        self.log.append_log("=== Starting full flash sequence ===")

        # Step 1: Upload
        upload_worker = SCPWorker(
            pc["host"], pc["user"], pc["password"], local, remote
        )
        upload_worker.output.connect(self.log.append_log)
        upload_worker.finished_signal.connect(self._after_upload)
        self._workers.append(upload_worker)
        upload_worker.start()

    def _after_upload(self, ok):
        if not ok:
            self.log.append_log("[All] Upload failed — aborting.")
            return
        pc = self._get_pc_cfg()
        board = self._get_board_cfg()

        # For flash.py PCs, flash includes reset
        if pc.get("flash_method") == "flash.py":
            self._flash_firmware()
            return

        reset_script = board.get("reset_script")
        if reset_script:
            cmd = f'cd {_get_remote_user_dir()} && copy {REMOTE_SCRIPTS_DIR}\\{reset_script} . >nul 2>&1 & powershell -ExecutionPolicy Bypass -File {reset_script}'
            self.log.append_log("[All] Resetting board...")
            worker = SSHWorker(pc["host"], pc["user"], pc["password"], cmd)
            worker.output.connect(self.log.append_log)
            worker.finished_signal.connect(self._after_reset)
            self._workers.append(worker)
            worker.start()
        else:
            self._after_reset("0")

    def _after_reset(self, _status):
        self.log.append_log("[All] Flashing firmware...")
        self._flash_firmware()


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Serial Tab
# ---------------------------------------------------------------------------

class SerialTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        layout = QVBoxLayout(self)

        ctrl = QGroupBox("Remote Serial Terminal")
        g = QGridLayout(ctrl)

        g.addWidget(QLabel("Computer:"), 0, 0)
        self.pc_combo = QComboBox()
        self.pc_combo.addItems(COMPUTERS.keys())
        self.pc_combo.currentTextChanged.connect(self._on_pc_changed)
        g.addWidget(self.pc_combo, 0, 1)

        g.addWidget(QLabel("Board:"), 1, 0)
        self.board_combo = QComboBox()
        self.board_combo.currentTextChanged.connect(self._on_board_changed)
        g.addWidget(self.board_combo, 1, 1)

        g.addWidget(QLabel("COM Port:"), 2, 0)
        self.port_combo = QComboBox()
        g.addWidget(self.port_combo, 2, 1)

        g.addWidget(QLabel("Baudrate:"), 3, 0)
        self.baudrate = QComboBox()
        self.baudrate.setEditable(True)
        self.baudrate.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baudrate.setCurrentText(SERIAL_DEFAULTS["baudrate"])
        g.addWidget(self.baudrate, 3, 1)

        g.addWidget(QLabel("Remote Folder:"), 4, 0)
        self.remote_dir = QLineEdit(_get_remote_user_dir())
        self.remote_dir.setPlaceholderText("Your folder on the remote PC")
        g.addWidget(self.remote_dir, 4, 1)

        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("Open Serial")
        self.connect_btn.clicked.connect(self._toggle_serial)
        btn_row.addWidget(self.connect_btn)
        self.upload_btn = QPushButton("Upload serialterm.py")
        self.upload_btn.setToolTip("Upload a bundled serialterm.py to the remote folder")
        self.upload_btn.clicked.connect(self._upload_serialterm)
        btn_row.addWidget(self.upload_btn)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(lambda: self.log.clear())
        btn_row.addWidget(self.clear_btn)
        g.addLayout(btn_row, 5, 0, 1, 2)

        layout.addWidget(ctrl)

        self.log = LogWidget()
        layout.addWidget(self.log)

        self.serial_worker = None
        self._on_pc_changed(self.pc_combo.currentText())

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
        self.port_combo.clear()
        self.port_combo.addItems(board.get("ecu_ports", []))

    def _toggle_serial(self):
        if self.serial_worker is not None:
            self._stop_serial()
        else:
            self._start_serial()

    def _start_serial(self):
        pc = self._get_pc_cfg()
        port = self.port_combo.currentText()
        baud = self.baudrate.currentText()
        remote_dir = self.remote_dir.text().strip()
        if not port:
            return
        self.connect_btn.setText("Close Serial")
        self.serial_worker = SerialWorker(
            pc["host"], pc["user"], pc["password"], port, baud, remote_dir
        )
        self.serial_worker.output.connect(self.log.append_log)
        self.serial_worker.finished_signal.connect(self._on_serial_done)
        self._workers.append(self.serial_worker)
        self.serial_worker.start()

    def _upload_serialterm(self):
        """Upload the bundled serialterm.py to the remote PC."""
        pc = self._get_pc_cfg()
        remote_dir = self.remote_dir.text().strip().replace("\\", "/")
        local_path = os.path.join(os.path.dirname(__file__), "serialterm.py")
        if not os.path.isfile(local_path):
            self.log.append_log("[Upload] serialterm.py not found next to main.py!")
            return
        worker = SCPWorker(
            pc["host"], pc["user"], pc["password"], local_path, remote_dir
        )
        worker.output.connect(self.log.append_log)
        worker.finished_signal.connect(
            lambda ok: self.log.append_log(
                "[Upload] serialterm.py uploaded!" if ok else "[Upload] FAILED"
            )
        )
        self._workers.append(worker)
        worker.start()

    def _stop_serial(self):
        if self.serial_worker:
            self.serial_worker.stop()
            self.serial_worker.wait(3000)
            self.serial_worker = None
        self.connect_btn.setText("Open Serial")

    def _on_serial_done(self):
        self.serial_worker = None
        self.connect_btn.setText("Open Serial")
        self.log.append_log("[Serial] Connection closed.")


# ---------------------------------------------------------------------------
# SSH Terminal Tab
# ---------------------------------------------------------------------------

class SSHTerminalTab(QWidget):
    """Direct SSH command execution."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        layout = QVBoxLayout(self)

        ctrl = QGroupBox("SSH Command Execution")
        g = QGridLayout(ctrl)

        g.addWidget(QLabel("Computer:"), 0, 0)
        self.pc_combo = QComboBox()
        self.pc_combo.addItems(COMPUTERS.keys())
        g.addWidget(self.pc_combo, 0, 1)

        g.addWidget(QLabel("Command:"), 1, 0)
        cmd_row = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("e.g. dir c:\\dev")
        self.cmd_input.returnPressed.connect(self._run_command)
        cmd_row.addWidget(self.cmd_input)
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self._run_command)
        cmd_row.addWidget(self.run_btn)
        g.addLayout(cmd_row, 1, 1)

        layout.addWidget(ctrl)

        self.log = LogWidget()
        layout.addWidget(self.log)

    def _run_command(self):
        pc = COMPUTERS.get(self.pc_combo.currentText(), {})
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
        worker = SSHWorker(pc["host"], pc["user"], pc["password"], cmd)
        worker.output.connect(self.log.append_log)
        worker.finished_signal.connect(
            lambda s: self.log.append_log(f"--- exit status: {s} ---")
        )
        self._workers.append(worker)
        worker.start()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class CameraPanel(QWidget):
    """Persistent camera side-panel that stays visible across tabs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel("Camera Feed")
        header.setStyleSheet("color: #fff; font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        ctrl_row = QHBoxLayout()
        self.url_combo = QComboBox()
        self.url_combo.setEditable(True)
        self.url_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for _name, cfg in COMPUTERS.items():
            self.url_combo.addItem(cfg["camera_url"])
        ctrl_row.addWidget(self.url_combo)

        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self._toggle_camera)
        ctrl_row.addWidget(self.start_btn)
        layout.addLayout(ctrl_row)

        self.image_label = QLabel("Click Start to view camera")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(320, 240)
        self.image_label.setStyleSheet(
            "background-color: #000; color: #888; border: 1px solid #444;"
        )
        layout.addWidget(self.image_label, stretch=1)

        self.cam_worker = None

    def _toggle_camera(self):
        if self.cam_worker is not None:
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        url = self.url_combo.currentText().strip()
        if not url:
            return
        self.start_btn.setText("Stop")
        self.cam_worker = CameraWorker(url)
        self.cam_worker.frame_ready.connect(self._update_frame)
        self.cam_worker.error.connect(self._on_cam_error)
        self._workers.append(self.cam_worker)
        self.cam_worker.start()

    def _stop_camera(self):
        if self.cam_worker:
            self.cam_worker.stop()
            self.cam_worker.wait(2000)
            self.cam_worker = None
        self.start_btn.setText("Start")
        self.image_label.setText("Camera stopped")

    def _update_frame(self, img: QImage):
        scaled = img.scaled(
            self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.image_label.setPixmap(QPixmap.fromImage(scaled))

    def _on_cam_error(self, msg):
        self.image_label.setText(f"Camera error: {msg}")
        self._stop_camera()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Remote Firmware Flasher — UFPE Lab")
        self.setMinimumSize(1100, 700)

        # Set window icon
        icon_path = os.path.join(getattr(sys, '_MEIPASS', _APP_DIR), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # --- Tabs (left side) ---
        self.tabs = QTabWidget()
        self.vpn_tab = VPNTab()
        self.flash_tab = FlashTab()
        self.serial_tab = SerialTab()
        self.ssh_tab = SSHTerminalTab()

        self.tabs.addTab(self.vpn_tab, "VPN")
        self.tabs.addTab(self.flash_tab, "Flash")
        self.tabs.addTab(self.serial_tab, "Serial")
        self.tabs.addTab(self.ssh_tab, "SSH Terminal")

        # --- Camera panel (right side) ---
        self.camera_panel = CameraPanel()
        self._camera_visible = True  # user preference

        # --- Splitter: tabs | camera ---
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tabs)
        splitter.addWidget(self.camera_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([600, 400])

        self.setCentralWidget(splitter)

        # Toggle camera button on the tab bar corner
        self.toggle_cam_btn = QPushButton("Hide Camera")
        self.toggle_cam_btn.setCheckable(True)
        self.toggle_cam_btn.setChecked(False)
        self.toggle_cam_btn.setStyleSheet(
            "padding: 4px 12px; font-size: 11px; border-radius: 3px;"
        )
        self.toggle_cam_btn.toggled.connect(self._on_toggle_camera)
        self.tabs.setCornerWidget(self.toggle_cam_btn, Qt.TopRightCorner)

        # Update visibility when tab changes
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._on_tab_changed(self.tabs.currentIndex())

        # Status bar
        self.statusBar().showMessage("Ready — connect VPN first, then use Flash/Camera/Serial tabs")

        self._apply_style()

    def _on_toggle_camera(self, hidden):
        """User explicitly toggles the camera panel."""
        self._camera_visible = not hidden
        self.toggle_cam_btn.setText("Show Camera" if hidden else "Hide Camera")
        self._update_camera_visibility()

    def _on_tab_changed(self, index):
        """Update camera visibility based on tab and user preference."""
        self._update_camera_visibility()

    def _update_camera_visibility(self):
        is_vpn = (self.tabs.currentWidget() is self.vpn_tab)
        self.camera_panel.setVisible(not is_vpn and self._camera_visible)
        # Hide the toggle button on VPN tab since camera is always hidden there
        self.toggle_cam_btn.setVisible(not is_vpn)

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; }
            QTabWidget::pane { border: 1px solid #444; background: #2b2b2b; }
            QTabBar::tab {
                background: #353535; color: #ccc; padding: 8px 16px;
                border: 1px solid #444; border-bottom: none;
                margin-right: 2px;
            }
            QTabBar::tab:selected { background: #2b2b2b; color: #fff; }
            QTabBar::tab:hover { background: #404040; }
            QGroupBox {
                color: #ddd; border: 1px solid #555; border-radius: 4px;
                margin-top: 8px; padding-top: 16px; font-weight: bold;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QLabel { color: #ccc; }
            QLineEdit, QComboBox, QSpinBox {
                background: #3c3c3c; color: #ddd; border: 1px solid #555;
                padding: 4px; border-radius: 3px;
            }
            QPushButton {
                background: #0d47a1; color: white; border: none;
                padding: 6px 16px; border-radius: 3px; font-weight: bold;
            }
            QPushButton:hover { background: #1565c0; }
            QPushButton:pressed { background: #0a3a7e; }
            QStatusBar { color: #aaa; background: #252525; }
        """)


def _show_first_run_dialog() -> bool:
    """Show a setup dialog on first run so the user can set their remote folder.
    Returns True if the user completed setup, False if they cancelled."""
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout
    settings = _load_settings()

    dlg = QDialog()
    dlg.setWindowTitle("First Run Setup")
    dlg.setMinimumWidth(420)
    layout = QVBoxLayout(dlg)

    info = QLabel(
        "Welcome! Please enter your name.\n"
        f"Your remote folder will be created at {REMOTE_BASE_DIR}\\<your_name>."
    )
    info.setWordWrap(True)
    layout.addWidget(info)

    form = QFormLayout()
    name_edit = QLineEdit(settings.get("user_name", ""))
    name_edit.setPlaceholderText("e.g. renato")
    form.addRow("Your name:", name_edit)

    folder_edit = QLineEdit(settings.get("remote_user_dir", ""))
    folder_edit.setPlaceholderText(f"e.g. {REMOTE_BASE_DIR}\\renato")
    form.addRow("Remote folder:", folder_edit)

    # Auto-fill folder when name changes
    def _update_folder():
        name = name_edit.text().strip()
        if name and not folder_edit.isModified():
            folder_edit.setText(f"{REMOTE_BASE_DIR}\\{name}")
    name_edit.textChanged.connect(_update_folder)

    layout.addLayout(form)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)

    if dlg.exec() != QDialog.Accepted:
        return False

    name = name_edit.text().strip()
    folder = folder_edit.text().strip()
    if not name or not folder:
        return False

    _save_settings(user_name=name, remote_user_dir=folder)
    return True


def main():
    # Windows taskbar icon fix — must be set before QApplication
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ufpe.remote_flasher")

    app = QApplication(sys.argv)
    app.setApplicationName("Remote Firmware Flasher")

    # Set app-wide icon (shows in taskbar)
    icon_path = os.path.join(getattr(sys, '_MEIPASS', _APP_DIR), "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Show first-run setup if no remote folder is configured
    settings = _load_settings()
    if not settings.get("remote_user_dir"):
        if not _show_first_run_dialog():
            sys.exit(0)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""VPN connection tab."""
import subprocess
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QLineEdit, QCheckBox, QMessageBox,
)

from settings import load_credentials, save_credentials, clear_credentials, clear_all_settings
from widgets import LogWidget, StatusIndicator, make_log_with_clear


class VPNTab(QWidget):
    vpn_status_changed = Signal(bool)
    _log_signal = Signal(str)
    _status_signal = Signal(str, str, bool)

    DEFAULT_VPN_NAME = "VPN_CIN"
    DEFAULT_VPN_ADDRESS = "vpn.cin.ufpe.br"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        layout = QVBoxLayout(self)

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
        self.remember_cb.setToolTip("Save credentials locally (not shared with source code)")
        self.remember_cb.toggled.connect(self._on_remember_toggled)
        g.addWidget(self.remember_cb, 4, 1)

        saved = load_credentials()
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
        self.setup_btn.setToolTip("Create the Windows SSTP VPN profile automatically (only needed once)")
        self.setup_btn.clicked.connect(self._setup_vpn_profile)
        btn_row.addWidget(self.setup_btn)

        g.addLayout(btn_row, 5, 0, 1, 3)
        layout.addWidget(grp)

        hint = QGroupBox("Info")
        hl = QVBoxLayout(hint)
        hl.addWidget(QLabel(
            "Click 'Setup VPN Profile' once to create the Windows SSTP VPN connection.\n"
            "After that, enter your CIN credentials and click 'Connect VPN'.\n\n"
            "If you're already connected, click 'Test Connection' to verify."
        ))
        layout.addWidget(hint)

        self.log = make_log_with_clear(layout)

        clear_row = QHBoxLayout()
        clear_row.addStretch()
        self.clear_settings_btn = QPushButton("Clear All Settings")
        self.clear_settings_btn.setFlat(True)
        self.clear_settings_btn.setStyleSheet("color: #888; font-size: 10px; text-decoration: underline; padding: 2px;")
        self.clear_settings_btn.setCursor(Qt.PointingHandCursor)
        self.clear_settings_btn.setToolTip("Remove all saved settings and restart first-run setup")
        self.clear_settings_btn.clicked.connect(self._on_clear_settings)
        clear_row.addWidget(self.clear_settings_btn)
        layout.addLayout(clear_row)

        self._log_signal.connect(self.log.append_log)
        self._status_signal.connect(self._apply_status)

        # Check if VPN is already connected on startup
        threading.Thread(target=self._check_vpn_on_startup, daemon=True).start()

    def _check_vpn_on_startup(self):
        """Check if the VPN is already connected by listing active rasdial connections."""
        try:
            result = subprocess.run(
                ["rasdial"],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output = result.stdout.decode("cp850", errors="replace")
            vpn_name = self.vpn_name.text().strip()
            if vpn_name and vpn_name.lower() in output.lower():
                self._status_signal.emit("connected", "Connected", True)
                self._log_signal.emit(f"[VPN] Already connected to '{vpn_name}'")
        except Exception:
            pass  # silently ignore — not critical

    def _on_remember_toggled(self, checked):
        if checked:
            user = self.vpn_user.text().strip()
            passwd = self.vpn_pass.text().strip()
            if user and passwd:
                save_credentials(user, passwd)
        else:
            clear_credentials()

    def _on_clear_settings(self):
        reply = QMessageBox.question(
            self, "Clear All Settings",
            "This will remove all saved settings (VPN credentials, remote folder).\n"
            "The app will close and show the first-run setup on next launch.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            clear_all_settings()
            self.vpn_user.clear()
            self.vpn_pass.clear()
            self.remember_cb.setChecked(False)
            QMessageBox.information(self, "Settings Cleared",
                                    "All settings have been removed.\nThe app will now close.")
            QApplication.instance().quit()

    def _apply_status(self, indicator: str, label: str, connected: bool):
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
        name = self.vpn_name.text().strip()
        address = self.vpn_address.text().strip()
        if not name or not address:
            self.log.append_log("[VPN Setup] Name and address are required.")
            return
        self.log.append_log(f"[VPN Setup] Creating SSTP profile '{name}' -> {address}...")
        threading.Thread(target=self._do_setup_vpn, args=(name, address), daemon=True).start()

    def _do_setup_vpn(self, name, address):
        check_cmd = f'Get-VpnConnection -Name "{name}" -ErrorAction SilentlyContinue'
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", check_cmd],
                capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if name.encode() in result.stdout:
                self._log_signal.emit(f"[VPN Setup] Profile '{name}' already exists. Removing to recreate...")
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", f'Remove-VpnConnection -Name "{name}" -Force'],
                    capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW,
                )
        except Exception:
            pass
        create_cmd = (
            f'Add-VpnConnection -Name "{name}" -ServerAddress "{address}"'
            f' -TunnelType Sstp -AuthenticationMethod MSChapv2'
            f' -EncryptionLevel Required -RememberCredential -Force'
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", create_cmd],
                capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            stdout = result.stdout.decode("cp850", errors="replace").strip() if isinstance(result.stdout, bytes) else result.stdout.strip()
            stderr = result.stderr.decode("cp850", errors="replace").strip() if isinstance(result.stderr, bytes) else result.stderr.strip()
            if result.returncode == 0:
                self._log_signal.emit(f"[VPN Setup] Profile '{name}' created successfully!")
                self._log_signal.emit("[VPN Setup] You can now enter your credentials and click 'Connect VPN'.")
            else:
                self._log_signal.emit(f"[VPN Setup] Failed (exit={result.returncode})")
                if stdout: self._log_signal.emit(stdout)
                if stderr: self._log_signal.emit(stderr)
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
        if self.remember_cb.isChecked():
            save_credentials(user, passwd)
        self.status_indicator.set_status("connecting")
        self.status_label.setText("Connecting...")
        self.log.append_log(f"[VPN] Connecting to '{name}' as '{user}'...")
        threading.Thread(target=self._rasdial_connect, args=(name, user, passwd), daemon=True).start()

    def _profile_exists(self, name):
        """Check if a VPN profile exists using rasdial (list) or rasphone."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f'Get-VpnConnection -Name "{name}" -ErrorAction SilentlyContinue'],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return name.encode() in result.stdout
        except Exception:
            return True  # assume exists if check fails

    def _rasdial_connect(self, name, user, passwd):
        # Check if profile exists, auto-create if not
        if not self._profile_exists(name):
            self._log_signal.emit(f"[VPN] Profile '{name}' not found. Creating it...")
            address = self.vpn_address.text().strip() or self.DEFAULT_VPN_ADDRESS
            create_cmd = (
                f'Add-VpnConnection -Name "{name}" -ServerAddress "{address}"'
                f' -TunnelType Sstp -AuthenticationMethod MSChapv2'
                f' -EncryptionLevel Required -RememberCredential -Force'
            )
            try:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", create_cmd],
                    capture_output=True, timeout=20,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if result.returncode == 0:
                    self._log_signal.emit(f"[VPN] Profile '{name}' created.")
                else:
                    stderr = result.stderr.decode("cp850", errors="replace").strip()
                    self._log_signal.emit(f"[VPN] Could not create profile: {stderr}")
                    self._status_signal.emit("disconnected", "No profile", False)
                    return
            except Exception as e:
                self._log_signal.emit(f"[VPN] Profile creation error: {e}")
                self._status_signal.emit("disconnected", "Error", False)
                return

        try:
            result = subprocess.run(
                ["rasdial", name, user, passwd],
                capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            stdout = result.stdout.decode("cp850", errors="replace").strip()
            stderr = result.stderr.decode("cp850", errors="replace").strip()
            if result.returncode == 0:
                self._log_signal.emit("[VPN] Connected successfully!")
                self._log_signal.emit(stdout)
                self._status_signal.emit("connected", "Connected", True)
            else:
                self._log_signal.emit(f"[VPN] Connection failed (exit={result.returncode})")
                self._log_signal.emit(stdout)
                if stderr: self._log_signal.emit(stderr)
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
                capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.log.append_log(result.stdout.decode("cp850", errors="replace").strip())
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
                capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            stdout = result.stdout.decode("cp850", errors="replace").strip()
            if result.returncode == 0:
                self._log_signal.emit("[VPN] SUCCESS — 172.20.36.217 is reachable!")
                self._status_signal.emit("connected", "Reachable", True)
            else:
                self._log_signal.emit("[VPN] FAILED — host not reachable. Is the VPN connected?")
                self._log_signal.emit(stdout)
                self._status_signal.emit("disconnected", "Not reachable", False)
        except Exception as e:
            self._log_signal.emit(f"[VPN] Test error: {e}")

"""VPN connection tab."""
import subprocess
import threading

import paramiko
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QLineEdit, QCheckBox, QMessageBox,
)

from lab_config import COMPUTERS, REMOTE_BASE_DIR
from settings import load_credentials, save_credentials, clear_credentials, clear_all_settings
from widgets import LogWidget, StatusIndicator, make_log_with_clear


class VPNTab(QWidget):
    vpn_status_changed = Signal(bool)
    _log_signal = Signal(str)
    _status_signal = Signal(str, str, bool)
    _health_result = Signal(str, str, str)  # pc_name, board_name, status ("ok"/"fail"/"error")
    _health_done = Signal()

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

        # ── Lab Health Check ───────────────────────────────────────
        hc_grp = QGroupBox("Lab Health Check")
        hc_layout = QVBoxLayout(hc_grp)

        hc_btn_row = QHBoxLayout()
        self.health_btn = QPushButton("Run Health Check")
        self.health_btn.setToolTip(
            "SSH into each lab PC and check if all board controllers respond.\n"
            "Red = controller frozen (needs manual cable reset)."
        )
        self.health_btn.clicked.connect(self._run_health_check)
        hc_btn_row.addWidget(self.health_btn)
        hc_btn_row.addStretch()
        hc_layout.addLayout(hc_btn_row)

        # Grid: rows = PCs, columns = boards 1-4
        self._hc_grid = QGridLayout()
        self._hc_grid.setSpacing(6)
        self._hc_indicators = {}  # (pc_label, board_name) -> (StatusIndicator, QLabel)

        # Header row
        self._hc_grid.addWidget(QLabel(""), 0, 0)
        for col, bname in enumerate(["Placa 01", "Placa 02", "Placa 03", "Placa 04"], start=1):
            lbl = QLabel(bname)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-weight: bold; font-size: 11px;")
            self._hc_grid.addWidget(lbl, 0, col)
        cam_hdr = QLabel("Camera")
        cam_hdr.setAlignment(Qt.AlignCenter)
        cam_hdr.setStyleSheet("font-weight: bold; font-size: 11px;")
        self._hc_grid.addWidget(cam_hdr, 0, 5)

        row = 1
        for pc_label, pc_info in COMPUTERS.items():
            # Short name like "PC 217"
            short = pc_label.split("(")[0].strip()
            pc_lbl = QLabel(short)
            pc_lbl.setStyleSheet("font-weight: bold;")
            self._hc_grid.addWidget(pc_lbl, row, 0)

            for col, bname in enumerate(sorted(pc_info["boards"].keys()), start=1):
                cell = QHBoxLayout()
                ind = StatusIndicator()
                ind.set_status("idle")
                cell.addStretch()
                cell.addWidget(ind)
                status_lbl = QLabel("--")
                status_lbl.setStyleSheet("font-size: 10px; color: #888;")
                cell.addWidget(status_lbl)
                cell.addStretch()
                self._hc_grid.addLayout(cell, row, col)
                self._hc_indicators[(short, bname)] = (ind, status_lbl)

            # Camera column — only PCs with a camera_url get an indicator
            cam_cell = QHBoxLayout()
            cam_ind = StatusIndicator()
            cam_lbl = QLabel("--")
            cam_lbl.setStyleSheet("font-size: 10px; color: #888;")
            cam_cell.addStretch()
            if pc_info.get("camera_url"):
                cam_ind.set_status("idle")
                cam_cell.addWidget(cam_ind)
                cam_cell.addWidget(cam_lbl)
                self._hc_indicators[(short, "camera")] = (cam_ind, cam_lbl)
            else:
                cam_lbl.setText("")
                cam_cell.addWidget(cam_lbl)
            cam_cell.addStretch()
            self._hc_grid.addLayout(cam_cell, row, 5)

            row += 1

        hc_layout.addLayout(self._hc_grid)
        layout.addWidget(hc_grp)

        self._health_result.connect(self._apply_health_result)
        self._health_done.connect(lambda: self.health_btn.setEnabled(True))

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
        # Capture widget value in main thread — Qt widgets must not be read from bg threads.
        vpn_name = self.vpn_name.text().strip()
        threading.Thread(target=self._check_vpn_on_startup, args=(vpn_name,), daemon=True).start()

    def _check_vpn_on_startup(self, vpn_name):
        """Check if the VPN is already connected by listing active rasdial connections."""
        try:
            result = subprocess.run(
                ["rasdial"],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output = result.stdout.decode("cp850", errors="replace")
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
        address = self.vpn_address.text().strip() or self.DEFAULT_VPN_ADDRESS
        self.log.append_log(f"[VPN] Connecting to '{name}' as '{user}'...")
        threading.Thread(target=self._rasdial_connect, args=(name, user, passwd, address), daemon=True).start()

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

    def _rasdial_connect(self, name, user, passwd, address):
        # Check if profile exists, auto-create if not
        if not self._profile_exists(name):
            self._log_signal.emit(f"[VPN] Profile '{name}' not found. Creating it...")
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

    # ── Lab Health Check ──────────────────────────────────────────

    def _apply_health_result(self, pc_name, board_name, status):
        key = (pc_name, board_name)
        if key not in self._hc_indicators:
            return
        ind, lbl = self._hc_indicators[key]
        if status == "ok":
            ind.set_status("connected")
            lbl.setText("OK")
            lbl.setStyleSheet("font-size: 10px; color: #44ff44;")
        elif status == "fail":
            ind.set_status("disconnected")
            lbl.setText("FROZEN")
            lbl.setStyleSheet("font-size: 10px; color: #ff4444; font-weight: bold;")
        elif status == "no_ssh":
            ind.set_status("disconnected")
            lbl.setText("SSH fail")
            lbl.setStyleSheet("font-size: 10px; color: #ff8800;")
        else:
            ind.set_status("idle")
            lbl.setText("--")
            lbl.setStyleSheet("font-size: 10px; color: #888;")

    def _run_health_check(self):
        # Reset all indicators
        for (pc, board), (ind, lbl) in self._hc_indicators.items():
            ind.set_status("connecting")
            lbl.setText("...")
            lbl.setStyleSheet("font-size: 10px; color: #ffaa00;")

        self.health_btn.setEnabled(False)
        self._log_signal.emit("[Health] Starting health check on all PCs...")
        threading.Thread(target=self._do_health_check, daemon=True).start()

    def _do_health_check(self):
        """SSH into each PC, run test_ttl.ps1, parse which boards respond."""
        for pc_label, pc_info in COMPUTERS.items():
            short = pc_label.split("(")[0].strip()
            host = pc_info["host"]
            user = pc_info["user"]
            password = pc_info["password"]
            boards = sorted(pc_info["boards"].keys())

            self._log_signal.emit(f"[Health] Checking {short} ({host})...")

            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(host, username=user, password=password, timeout=10)

                # Run the TTL test script
                cmd = f'powershell -ExecutionPolicy Bypass -File "{REMOTE_BASE_DIR}\\test_ttl.ps1"'
                _, stdout_ch, stderr_ch = client.exec_command(cmd, timeout=20)
                output = stdout_ch.read().decode("utf-8", errors="replace")
                stderr_out = stderr_ch.read().decode("utf-8", errors="replace")
                client.close()

                self._log_signal.emit(f"[Health] {short} TTL output:\n{output.strip()}")
                if stderr_out.strip():
                    self._log_signal.emit(f"[Health] {short} stderr: {stderr_out.strip()}")

                # Parse output: look for each board's response.
                # The script typically outputs lines per port. If a port doesn't
                # respond, it's missing or shows an error/timeout.
                # Strategy: for each board, check if its reset_port (TTL controller)
                # appears in the output with a successful response.
                output_lower = output.lower()
                for board_name in boards:
                    board_info = pc_info["boards"][board_name]
                    reset_port = board_info.get("reset_port") or board_info.get("can_selector_port")

                    if not reset_port:
                        # No TTL controller configured — can't check
                        self._health_result.emit(short, board_name, "ok")
                        continue

                    # Check if the port appears in output with a response
                    port_lower = reset_port.lower()
                    if port_lower in output_lower:
                        # Port found in output — check if it got a response
                        # Lines with the port that DON'T contain error/timeout = OK
                        port_lines = [l for l in output.splitlines()
                                      if port_lower in l.lower()]
                        has_error = any("erro" in l.lower() or "timeout" in l.lower()
                                        or "falha" in l.lower() or "fail" in l.lower()
                                        or "não" in l.lower()
                                        for l in port_lines)
                        if has_error:
                            self._health_result.emit(short, board_name, "fail")
                            self._log_signal.emit(
                                f"[Health] !! {short} {board_name} ({reset_port}): FROZEN / not responding")
                        else:
                            self._health_result.emit(short, board_name, "ok")
                    else:
                        # Port not mentioned at all — likely not responding
                        self._health_result.emit(short, board_name, "fail")
                        self._log_signal.emit(
                            f"[Health] !! {short} {board_name} ({reset_port}): not found in output")

            except Exception as e:
                self._log_signal.emit(f"[Health] {short}: SSH failed — {e}")
                for board_name in boards:
                    self._health_result.emit(short, board_name, "no_ssh")
                if pc_info.get("camera_url"):
                    self._health_result.emit(short, "camera", "no_ssh")
                continue

            # Check camera process if this PC has one
            if pc_info.get("camera_url"):
                try:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    client.connect(host, username=user, password=password, timeout=10)
                    _, stdout_ch, _ = client.exec_command(
                        'tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH', timeout=10)
                    proc_output = stdout_ch.read().decode("utf-8", errors="replace")
                    client.close()

                    if "camera" in proc_output.lower() or proc_output.strip().count("python.exe") > 0:
                        # python.exe is running — likely the camera (best we can check without PID)
                        self._health_result.emit(short, "camera", "ok")
                        self._log_signal.emit(f"[Health] {short}: camera process running")
                    else:
                        self._health_result.emit(short, "camera", "fail")
                        self._log_signal.emit(f"[Health] !! {short}: camera process NOT running")
                except Exception as e:
                    self._log_signal.emit(f"[Health] {short}: camera check failed — {e}")
                    self._health_result.emit(short, "camera", "no_ssh")

        self._log_signal.emit("[Health] Health check complete.")
        self._health_done.emit()

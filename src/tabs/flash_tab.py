"""Firmware flash tab."""
import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QLineEdit, QFileDialog,
    QMessageBox,
)

from lab_config import COMPUTERS, AVRDUDE_DEFAULTS, REMOTE_BASE_DIR, REMOTE_SCRIPTS_DIR
from settings import get_remote_user_dir
from widgets import LogWidget, make_log_with_clear
from workers import SSHWorker, SCPWorker, PortsFetchWorker, LockAcquireWorker, LockReleaseWorker
from ports_sync import apply_overrides, save_cache, REMOTE_PORTS_PATH


class FlashTab(QWidget):
    # Emitted after ports.json is successfully fetched and COMPUTERS is
    # updated in place. MainWindow relays this to the other tabs so their
    # board/port combos refresh without a PC-selector round-trip.
    ports_synced = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        # Monotonic counter — each user-initiated action (click) gets a fresh
        # id so LogWidget can color its lines distinctly from other actions
        # running concurrently.
        self._next_op_id = 0
        # In-process COM-port reservation. Prevents a Reset click from firing
        # while a Flash is mid-write on the same board (the resulting mid-flash
        # reboot floods avrdude with stk500_cmd() out-of-sync errors).
        # Keyed by (pc_key, com_port); released when the owning op finishes.
        self._busy_ports: set[tuple[str, str]] = set()
        layout = QVBoxLayout(self)

        ctrl = QGroupBox("Firmware Flash")
        g = QGridLayout(ctrl)

        g.addWidget(QLabel("Computer:"), 0, 0)
        pc_row = QHBoxLayout()
        self.pc_combo = QComboBox()
        self.pc_combo.addItems(COMPUTERS.keys())
        self.pc_combo.setToolTip("Which lab PC hosts the board you want to flash.")
        self.pc_combo.currentTextChanged.connect(self._on_pc_changed)
        pc_row.addWidget(self.pc_combo, stretch=1)

        self.sync_ports_btn = QPushButton("Sync Ports from PC 217")
        self.sync_ports_btn.setToolTip(
            f"Download {REMOTE_PORTS_PATH} from PC 217 and apply to all 4 PCs"
        )
        self.sync_ports_btn.clicked.connect(self._sync_ports)
        pc_row.addWidget(self.sync_ports_btn)
        g.addLayout(pc_row, 0, 1)

        g.addWidget(QLabel("Board:"), 1, 0)
        self.board_combo = QComboBox()
        self.board_combo.setToolTip("Which physical board on the selected PC.")
        g.addWidget(self.board_combo, 1, 1)
        self.board_combo.currentTextChanged.connect(self._on_board_changed)

        g.addWidget(QLabel("ECU COM Port:"), 2, 0)
        self.ecu_combo = QComboBox()
        self.ecu_combo.setToolTip(
            "COM port where avrdude will talk to the AVR bootloader.\n"
            "Must be free — close any Serial panel using this port first."
        )
        g.addWidget(self.ecu_combo, 2, 1)

        g.addWidget(QLabel("HEX File:"), 3, 0)
        hex_row = QHBoxLayout()
        self.hex_path = QLineEdit()
        self.hex_path.setPlaceholderText("Select .hex firmware file...")
        self.hex_path.setToolTip("Local path to the compiled .hex firmware to flash.")
        hex_row.addWidget(self.hex_path)
        browse = QPushButton("Browse")
        browse.setToolTip("Pick a .hex file from disk.")
        browse.clicked.connect(self._browse_hex)
        hex_row.addWidget(browse)
        g.addLayout(hex_row, 3, 1)

        g.addWidget(QLabel("Remote Folder:"), 4, 0)
        self.remote_folder = QLineEdit(get_remote_user_dir())
        self.remote_folder.setPlaceholderText("Your folder on the remote PC")
        self.remote_folder.setToolTip(
            "Folder on the remote PC where the .hex is uploaded before flashing.\n"
            "Typically C:\\2026\\<your-username>."
        )
        g.addWidget(self.remote_folder, 4, 1)

        btn_row = QHBoxLayout()
        self.upload_btn = QPushButton("1. Upload HEX")
        self.upload_btn.setToolTip("SCP-copy the .hex to the remote folder.")
        self.upload_btn.clicked.connect(self._upload_hex)
        btn_row.addWidget(self.upload_btn)

        self.reset_btn = QPushButton("2. Reset Board")
        self.reset_btn.setToolTip("Send the CAN reset pulse to reboot the ECU into its bootloader.")
        self.reset_btn.clicked.connect(self._reset_board)
        btn_row.addWidget(self.reset_btn)

        self.flash_btn = QPushButton("3. Flash Firmware")
        self.flash_btn.setToolTip("Run avrdude on the remote PC to program the already-uploaded .hex.")
        self.flash_btn.clicked.connect(self._flash_firmware)
        btn_row.addWidget(self.flash_btn)

        self.flash_all_btn = QPushButton("Upload + Reset + Flash")
        self.flash_all_btn.setStyleSheet("background-color: #2d5a27; color: white; font-weight: bold;")
        self.flash_all_btn.setToolTip(
            "Run the full sequence: upload → reset the ECU → flash.\n"
            "Runs as one atomic operation with a shared port lock."
        )
        self.flash_all_btn.clicked.connect(self._do_all)
        btn_row.addWidget(self.flash_all_btn)

        g.addLayout(btn_row, 5, 0, 1, 2)
        layout.addWidget(ctrl)

        self.log = make_log_with_clear(layout)

        self._on_pc_changed(self.pc_combo.currentText())

    def _mint_op(self) -> int:
        op = self._next_op_id
        self._next_op_id += 1
        return op

    def _log(self, op_id: int, msg: str):
        self.log.append_op(op_id, msg)

    def _acquire_local_ports(self, op_id: int, label: str, pc_key: str, ports) -> bool:
        """Reserve COM ports for this in-process op. Returns False (and warns)
        if any requested port is already held by another flash/reset op.
        """
        ports = [p for p in ports if p]
        busy = [p for p in ports if (pc_key, p) in self._busy_ports]
        if busy:
            QMessageBox.warning(
                self, "Operation in Progress",
                f"Can't start {label.lower()} — the following port(s) are already "
                f"being used by another flash/reset on {pc_key}:\n\n"
                f"  {', '.join(busy)}\n\n"
                "Wait for the running operation to finish.",
                QMessageBox.Ok,
            )
            self._log(op_id, f"[{label}] Aborted — {', '.join(busy)} busy on {pc_key}.")
            return False
        for p in ports:
            self._busy_ports.add((pc_key, p))
        return True

    def _release_local_ports(self, pc_key: str, ports):
        for p in ports:
            self._busy_ports.discard((pc_key, p))

    def _acquire_remote_locks(self, op_id, label, pc_key, pc_info, ports, on_success):
        """Acquire cross-user SFTP locks on the remote PC, async.

        Local locks are assumed already held. On success, invokes on_success()
        on the Qt thread. On conflict, releases the local locks (since the op
        can't proceed) and shows the user who holds the remote locks.
        """
        ports = [p for p in ports if p]
        if not ports:
            on_success()
            return
        self._log(op_id, f"[{label}] Acquiring remote lock for {', '.join(ports)}...")
        worker = LockAcquireWorker(pc_info, ports)
        worker.finished_signal.connect(
            lambda ok, conflicts, op=op_id, lbl=label, pk=pc_key, ps=ports:
                self._on_remote_locks_acquired(ok, conflicts, op, lbl, pk, ps, on_success)
        )
        self._workers.append(worker)
        worker.start()

    def _on_remote_locks_acquired(self, ok, conflicts, op_id, label, pc_key, ports, on_success):
        if ok:
            on_success()
            return
        # Conflict — back out the local reservation so the user can try again.
        self._release_local_ports(pc_key, ports)
        owners = "\n".join(f"  {p}: {o}" for p, o in conflicts)
        QMessageBox.warning(
            self, "Port In Use (Another User)",
            f"Can't start {label.lower()} on {pc_key} — in use by:\n\n{owners}\n\n"
            "Wait for them to finish or coordinate on who goes next.",
            QMessageBox.Ok,
        )
        conflict_list = ", ".join(f"{p} ({o})" for p, o in conflicts)
        self._log(op_id, f"[{label}] Aborted — remote port held by: {conflict_list}.")

    def _release_all_ports(self, pc_key: str, ports):
        """Release both in-process and cross-user locks. Remote release is async."""
        ports = [p for p in ports if p]
        self._release_local_ports(pc_key, ports)
        if not ports:
            return
        pc_info = COMPUTERS.get(pc_key)
        if not pc_info:
            return
        worker = LockReleaseWorker(pc_info, ports)
        worker.finished_signal.connect(worker.deleteLater)
        self._workers.append(worker)
        worker.start()

    def _get_pc_cfg(self):
        return COMPUTERS.get(self.pc_combo.currentText(), {})

    def _get_board_cfg(self):
        pc = self._get_pc_cfg()
        return pc.get("boards", {}).get(self.board_combo.currentText(), {})

    def _on_pc_changed(self, _text):
        pc = self._get_pc_cfg()
        self.board_combo.clear()
        self.board_combo.addItems(pc.get("boards", {}).keys())

    def _on_board_changed(self, _text):
        board = self._get_board_cfg()
        self.ecu_combo.clear()
        self.ecu_combo.addItems(board.get("ecu_ports", []))

    def _sync_ports(self):
        """Fetch ports.json from PC 217 and apply overrides to COMPUTERS."""
        op = self._mint_op()
        pc217_key = next(
            (k for k in COMPUTERS if k.startswith("PC 217")), None
        )
        if not pc217_key:
            self._log(op, "[Ports] PC 217 not configured in lab_config.")
            return
        pc = COMPUTERS[pc217_key]
        self.sync_ports_btn.setEnabled(False)
        self._log(op, f"[Ports] Syncing {REMOTE_PORTS_PATH} from {pc['host']}...")
        worker = PortsFetchWorker(
            pc["host"], pc["user"], pc["password"], REMOTE_PORTS_PATH
        )
        worker.output.connect(lambda m, op=op: self._log(op, m))
        worker.finished_signal.connect(
            lambda ok, data, op=op: self._on_ports_fetched(ok, data, op)
        )
        self._workers.append(worker)
        worker.start()

    def _on_ports_fetched(self, ok, data, op_id):
        self.sync_ports_btn.setEnabled(True)
        if not ok:
            self._log(op_id, "[Ports] Sync failed — keeping previous mapping.")
            return
        changes = apply_overrides(COMPUTERS, data)
        try:
            save_cache(data)
            self._log(op_id, "[Ports] Cached locally for next startup.")
        except Exception as e:
            self._log(op_id, f"[Ports] WARNING: could not write cache: {e}")
        if changes:
            self._log(op_id, f"[Ports] Applied {len(changes)} change(s):")
            for c in changes:
                self._log(op_id, f"  - {c}")
        else:
            self._log(op_id, "[Ports] No changes — already in sync.")
        # Refresh this tab's combos immediately with the new values.
        self._on_pc_changed(self.pc_combo.currentText())
        # Notify other tabs.
        self.ports_synced.emit()

    def _browse_hex(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select HEX file", "", "HEX Files (*.hex);;All (*)")
        if path:
            self.hex_path.setText(path)

    def _upload_hex(self):
        op = self._mint_op()
        if not self._preflight(op, "Upload"):
            return
        pc = self._get_pc_cfg()
        local = self.hex_path.text().strip()
        if not local or not os.path.isfile(local):
            self._log(op, "[Upload] Please select a valid .hex file.")
            return
        remote = self.remote_folder.text().strip().replace("\\", "/")
        worker = SCPWorker(pc["host"], pc["user"], pc["password"], local, remote)
        worker.output.connect(lambda m, op=op: self._log(op, m))
        worker.finished_signal.connect(lambda ok, op=op: self._log(
            op, "[Upload] Done!" if ok else "[Upload] FAILED"
        ))
        self._workers.append(worker)
        worker.start()

    def _reset_board(self):
        op = self._mint_op()
        pc_key = self.pc_combo.currentText()
        board = self._get_board_cfg()
        reset_port = board.get("reset_port")
        if not self._preflight(op, "Reset", ports_to_check=[reset_port] if reset_port else []):
            return
        pc = self._get_pc_cfg()
        reset_script = board.get("reset_script")
        if reset_script:
            if not reset_port:
                self._log(op, "[Reset] reset_port not configured for this board.")
                return
            cmd = (f'mkdir {get_remote_user_dir()} >nul 2>&1 & cd {get_remote_user_dir()}'
                   f' && copy {REMOTE_SCRIPTS_DIR}\\{reset_script} . >nul 2>&1'
                   f' & powershell -ExecutionPolicy Bypass -File {reset_script} -Port {reset_port}')
        elif reset_port and pc.get("flash_method") == "flash.py":
            self._log(op, "[Reset] This PC uses flash.py — reset is integrated into flash.")
            return
        else:
            self._log(op, "[Reset] No reset method configured for this board.")
            return
        if not self._acquire_local_ports(op, "Reset", pc_key, [reset_port]):
            return
        self._acquire_remote_locks(
            op, "Reset", pc_key, pc, [reset_port],
            lambda: self._run_reset_cmd(op, pc, cmd, pc_key, reset_port),
        )

    def _run_reset_cmd(self, op, pc, cmd, pc_key, reset_port):
        self._log(op, "[Reset] Sending reset signal...")
        worker = SSHWorker(pc["host"], pc["user"], pc["password"], cmd)
        worker.output.connect(lambda m, op=op: self._log(op, m))
        worker.finished_signal.connect(
            lambda s, op=op, pk=pc_key, rp=reset_port: self._on_reset_done(s, op, pk, rp)
        )
        self._workers.append(worker)
        worker.start()

    def _on_reset_done(self, status, op_id, pc_key, reset_port):
        self._log(op_id, f"[Reset] Exit status: {status}")
        self._release_all_ports(pc_key, [reset_port])

    def _check_port_in_use(self, port):
        """Check if a COM port is being used by an active serial panel."""
        if not port:
            return False
        main_window = self.window()
        serial_tab = getattr(main_window, 'serial_tab', None)
        if serial_tab is None:
            return False
        for panel in getattr(serial_tab, 'panels', []):
            if panel.serial_worker and panel.serial_worker.isRunning():
                panel_port = getattr(panel, 'port_combo', None)
                if panel_port and panel_port.currentText() == port:
                    return True
        return False

    def _preflight(self, op_id, label, ports_to_check=()):
        """Pre-flight checks: VPN connection + COM port availability.

        Returns True if OK to proceed; False if the user cancelled or a port
        is held by a running serial panel.
        """
        # 1) VPN check — non-blocking (user can proceed if they know better)
        main_window = self.window()
        vpn_tab = getattr(main_window, 'vpn_tab', None)
        if vpn_tab is not None and not getattr(vpn_tab, '_connected', False):
            reply = QMessageBox.question(
                self, "VPN Not Connected",
                "The VPN appears to be disconnected.\n\n"
                "If the remote PC isn't reachable without the VPN, "
                f"{label.lower()} will fail.\n\nProceed anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self._log(op_id, f"[{label}] Aborted — VPN not connected.")
                return False

        # 2) Port-in-use check — blocking (can't share a COM port)
        for port in ports_to_check:
            if self._check_port_in_use(port):
                QMessageBox.warning(
                    self, "Port In Use",
                    f"COM port {port} is currently open in a serial panel.\n\n"
                    f"Close the serial connection before {label.lower()}.",
                    QMessageBox.Ok,
                )
                self._log(op_id, f"[{label}] Aborted — {port} is in use by a serial panel.")
                return False
        return True

    def _flash_firmware(self, _internal=False, op_id=None, release_ports=None):
        """Flash the hex file to the board.

        release_ports: when chained from _do_all, a (pc_key, [ports]) tuple
        that _on_flash_done releases when the flash finishes. When called
        directly from the button, _flash_firmware acquires (and arranges to
        release) the ports itself.
        """
        ecu_port = self.ecu_combo.currentText()
        # Reuse the caller's op_id when chained from _after_reset (keeps the
        # whole sequence in one color); mint a fresh one for direct button clicks.
        if op_id is None:
            op_id = self._mint_op()
        pc_key = self.pc_combo.currentText()
        pc = self._get_pc_cfg()
        board = self._get_board_cfg()
        # _internal=True when chained from _after_upload / _after_reset — the
        # preflight, local acquire, and remote acquire already ran at the top
        # of the sequence.
        if not _internal:
            if not self._preflight(op_id, "Flash", ports_to_check=[ecu_port]):
                return
            ports_to_hold = [ecu_port]
            # flash.py integrates reset — it also touches reset_port, so lock it too.
            if pc.get("flash_method") == "flash.py":
                rp = board.get("reset_port")
                if rp:
                    ports_to_hold.append(rp)
            if not self._acquire_local_ports(op_id, "Flash", pc_key, ports_to_hold):
                return
            release_ports = (pc_key, ports_to_hold)
            self._acquire_remote_locks(
                op_id, "Flash", pc_key, pc, ports_to_hold,
                lambda: self._run_flash_cmd(op_id, release_ports),
            )
            return
        # _internal path: locks already held, go straight to the flash command.
        self._run_flash_cmd(op_id, release_ports)

    def _run_flash_cmd(self, op_id, release_ports):
        pc = self._get_pc_cfg()
        board = self._get_board_cfg()
        ecu_port = self.ecu_combo.currentText()
        hex_name = os.path.basename(self.hex_path.text().strip())
        remote_dir = self.remote_folder.text().strip()
        if not hex_name:
            self._log(op_id, "[Flash] No hex file specified.")
            if release_ports is not None:
                self._release_all_ports(*release_ports)
            return

        if pc.get("flash_method") == "flash.py":
            reset_port = board.get("reset_port", "")
            # -u = unbuffered so flash.py's prints stream in real time
            cmd = (f'cd {remote_dir} && copy {REMOTE_SCRIPTS_DIR}\\avrdude.conf . >nul 2>&1'
                   f' & python -u {REMOTE_BASE_DIR}\\flash.py --reset_port {reset_port}'
                   f' --flash_port {ecu_port} --hex {hex_name} --delay 0.4')
        else:
            cmd = (f'cd {remote_dir} && copy {REMOTE_SCRIPTS_DIR}\\avrdude.conf . >nul 2>&1'
                   f' & avrdude.exe -C avrdude.conf -v'
                   f' -p {AVRDUDE_DEFAULTS["mcu"]} -c {AVRDUDE_DEFAULTS["programmer"]}'
                   f' -b {AVRDUDE_DEFAULTS["baudrate"]} -P {ecu_port}'
                   f' -U flash:w:{hex_name}:i')
        self._log(op_id, f"[Flash] Executing: {cmd}")
        # use_pty=True makes avrdude/python detect a TTY and flush each line
        # immediately instead of dumping everything at the end.
        worker = SSHWorker(pc["host"], pc["user"], pc["password"], cmd, timeout=30, use_pty=True)
        worker.output.connect(lambda m, op=op_id: self._log(op, m))
        worker.finished_signal.connect(
            lambda s, op=op_id, rp=release_ports: self._on_flash_done(s, op, rp)
        )
        self._workers.append(worker)
        worker.start()

    def _on_flash_done(self, status, op_id, release_ports):
        if status == "0":
            self._log(op_id, "[Flash] SUCCESS")
        elif status == "-1":
            self._log(op_id, "[Flash] FAILED — connection error or timeout (30s).")
            self._log(op_id, "[Flash] Check that the COM port is not in use and the board is connected.")
        else:
            self._log(op_id, f"[Flash] FAILED (exit={status})")
        if release_ports is not None:
            self._release_all_ports(*release_ports)

    def _do_all(self):
        op = self._mint_op()
        pc_key = self.pc_combo.currentText()
        board = self._get_board_cfg()
        ecu_port = self.ecu_combo.currentText()
        reset_port = board.get("reset_port")
        ports_to_check = [ecu_port] + ([reset_port] if reset_port else [])
        if not self._preflight(op, "All", ports_to_check=ports_to_check):
            return
        # Hold both ports for the entire upload→reset→flash sequence.
        if not self._acquire_local_ports(op, "All", pc_key, ports_to_check):
            return
        pc = self._get_pc_cfg()
        local = self.hex_path.text().strip()
        if not local or not os.path.isfile(local):
            self._log(op, "[All] Please select a valid .hex file.")
            self._release_local_ports(pc_key, ports_to_check)
            return
        self._acquire_remote_locks(
            op, "All", pc_key, pc, ports_to_check,
            lambda: self._start_upload(op, pc_key, pc, local, ports_to_check),
        )

    def _start_upload(self, op, pc_key, pc, local, ports_to_check):
        remote = self.remote_folder.text().strip().replace("\\", "/")
        self._log(op, "=== Starting full flash sequence ===")
        held = (pc_key, ports_to_check)
        upload_worker = SCPWorker(pc["host"], pc["user"], pc["password"], local, remote)
        upload_worker.output.connect(lambda m, op=op: self._log(op, m))
        upload_worker.finished_signal.connect(
            lambda ok, op=op, h=held: self._after_upload(ok, op, h)
        )
        self._workers.append(upload_worker)
        upload_worker.start()

    def _after_upload(self, ok, op_id, held):
        if not ok:
            self._log(op_id, "[All] Upload failed — aborting.")
            self._release_all_ports(*held)
            return
        pc = self._get_pc_cfg()
        board = self._get_board_cfg()
        if pc.get("flash_method") == "flash.py":
            self._flash_firmware(_internal=True, op_id=op_id, release_ports=held)
            return
        reset_script = board.get("reset_script")
        reset_port = board.get("reset_port")
        if reset_script and reset_port:
            cmd = (f'mkdir {get_remote_user_dir()} >nul 2>&1 & cd {get_remote_user_dir()}'
                   f' && copy {REMOTE_SCRIPTS_DIR}\\{reset_script} . >nul 2>&1'
                   f' & powershell -ExecutionPolicy Bypass -File {reset_script} -Port {reset_port}')
            self._log(op_id, "[All] Resetting board...")
            worker = SSHWorker(pc["host"], pc["user"], pc["password"], cmd)
            worker.output.connect(lambda m, op=op_id: self._log(op, m))
            worker.finished_signal.connect(
                lambda s, op=op_id, h=held: self._after_reset(s, op, h)
            )
            self._workers.append(worker)
            worker.start()
        else:
            self._after_reset("0", op_id, held)

    def _after_reset(self, _status, op_id, held):
        self._log(op_id, "[All] Flashing firmware...")
        self._flash_firmware(_internal=True, op_id=op_id, release_ports=held)

"""Firmware flash tab."""
import os
import shutil
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QLineEdit, QFileDialog,
    QMessageBox,
)

from lab_config import COMPUTERS, AVRDUDE_DEFAULTS, REMOTE_BASE_DIR, REMOTE_SCRIPTS_DIR
from settings import get_remote_user_dir
from widgets import LogWidget, make_log_with_clear
from workers import SSHWorker, SCPWorker, PortsFetchWorker, LocalCommandWorker
from ports_sync import apply_overrides, save_cache, REMOTE_PORTS_PATH


# -------------------------------------------------------------------------
# Local-mode helpers (used when flash_method == 'local', e.g. aneb-sim
# simulator).  Find avrdude.exe and its config in standard install
# locations so the local path doesn't need a remote_dir / remote scripts.
# -------------------------------------------------------------------------

_AVRDUDE_SEARCH = (
    r"C:\Program Files (x86)\Arduino\hardware\tools\avr\bin\avrdude.exe",
    r"C:\Program Files\Arduino\hardware\tools\avr\bin\avrdude.exe",
    r"C:\msys64\mingw64\bin\avrdude.exe",
    r"C:\msys64\usr\bin\avrdude.exe",
)


def _find_avrdude():
    found = shutil.which("avrdude") or shutil.which("avrdude.exe")
    if found:
        return found
    for p in _AVRDUDE_SEARCH:
        if os.path.isfile(p):
            return p
    return None


def _find_avrdude_conf(avrdude_exe):
    """Find avrdude.conf relative to a given avrdude binary.  Arduino's
    bundled build expects bin/../etc/avrdude.conf and won't find it via
    the empty default when launched from a non-Arduino working dir."""
    exe = Path(avrdude_exe)
    for c in (exe.parent.parent / "etc" / "avrdude.conf",
              exe.parent / "avrdude.conf"):
        if c.is_file():
            return str(c)
    return None


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

        # Dark background — the tab itself has no explicit background in the
        # global stylesheet, which leaves a white strip between child widgets.
        self.setStyleSheet("FlashTab { background: #2b2b2b; }")

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

        # Cancel — only enabled during the avrdude phase. Reset is a brief
        # CAN pulse; interrupting it mid-pulse could leave the ECU in a bad
        # state, so we don't expose Cancel for reset.
        self.cancel_btn = QPushButton("Cancel Flash")
        self.cancel_btn.setStyleSheet(
            "QPushButton { background-color: #8b0000; color: white; font-weight: bold; }"
            "QPushButton:disabled { background-color: #3a1a1a; color: #777; }"
        )
        self.cancel_btn.setToolTip(
            "Abort the running avrdude process (kills only the avrdude bound to\n"
            "this ECU port, leaves other students' work untouched).\n"
            "Only available while avrdude is actually running."
        )
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_flash)
        btn_row.addWidget(self.cancel_btn)
        self._flash_worker = None  # current avrdude SSHWorker (None when idle)
        self._flash_cancelled = False  # set by _cancel_flash; read in _on_flash_done

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
        """Historical cross-user SFTP lock step — now a pass-through.

        The SFTP lock layer was removed (it caused more problems than it
        solved — stale locks, SSH/SFTP churn that tripped the camera's
        capture watchdog). Local `_busy_ports` still guards against
        same-app Flash-vs-Reset racing on the same port. This wrapper is
        kept so callers don't all have to be rewritten at once; it just
        invokes on_success() synchronously.
        """
        on_success()

    def _release_all_ports(self, pc_key: str, ports):
        """Release the in-process port reservation (no remote lock to free)."""
        ports = [p for p in ports if p]
        self._release_local_ports(pc_key, ports)

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
        # Local mode: .hex is already on disk — nothing to upload.
        if pc.get("flash_method") == "local":
            self._log(op, f"[Upload] Local target — using {local} in place (no copy).")
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
        # Local mode: aneb-sim's TCP UART server kicks any prior client
        # and resets the chip whenever a NEW client connects.  We trigger
        # that by opening and immediately closing a TCP socket to the
        # selected ECU's UART port.  This kicks off the aneb-sim UI's
        # bridge — the user will need to restart it from the UI.
        if pc.get("flash_method") == "local":
            self._local_reset(op, board)
            return
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
        # Reset is just a short CAN AT-command pulse — safe to cancel. Track
        # it as the cancellable worker; no write-phase monitoring needed here.
        self._flash_worker = worker
        self._flash_pc = pc
        self._flash_port = reset_port
        self.cancel_btn.setEnabled(True)
        worker.start()

    def _on_reset_done(self, status, op_id, pc_key, reset_port):
        self._flash_worker = None
        # Leave Cancel disabled until the next op starts (avoid flicker when
        # reset → flash chains).
        self.cancel_btn.setEnabled(False)
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
        # Local-mode targets (aneb-sim) don't need the VPN — everything runs
        # on 127.0.0.1.  Skip the VPN gate for those PCs.
        is_local = self._get_pc_cfg().get("flash_method") == "local"
        # 1) VPN check — non-blocking (user can proceed if they know better)
        main_window = self.window()
        vpn_tab = getattr(main_window, 'vpn_tab', None)
        if (not is_local) and vpn_tab is not None and not getattr(vpn_tab, '_connected', False):
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

        self._launch_flash_worker(op_id, pc, ecu_port, remote_dir, hex_name,
                                  board, release_ports)

    def _launch_flash_worker(self, op_id, pc, ecu_port, remote_dir, hex_name,
                             board, release_ports):
        # ---- Local mode (aneb-sim simulator) ---------------------------
        # No SCP, no SSH, no flash.py.  We have the .hex on disk already
        # and the simulator does its own DTR-pulse reset on TCP/COM
        # connect — so just shell out to a local avrdude.
        if pc.get("flash_method") == "local":
            self._launch_local_flash_worker(op_id, pc, ecu_port, hex_name,
                                            board, release_ports)
            return

        # For PCs using the flash.py method, keep the remote copy of
        # flash.py in sync with our local bundle — size-compared so an
        # unchanged file is a cheap stat+skip. Without this the remote
        # can run a stale flash.py (e.g. without the avrdude kill-timeout)
        # and hang forever on a bad sync.
        if pc.get("flash_method") == "flash.py":
            try:
                self._sftp_upload_flash_py(pc)
            except Exception as e:
                self._log(op_id, f"[Flash] Could not refresh flash.py ({e}); using existing copy.")
        if pc.get("flash_method") == "flash.py":
            reset_port = board.get("reset_port", "")
            # -u = unbuffered so flash.py's prints stream in real time
            cmd = (f'cd {remote_dir} && copy {REMOTE_SCRIPTS_DIR}\\avrdude.conf . >nul 2>&1'
                   f' & python -u {REMOTE_BASE_DIR}\\flash.py --reset_port {reset_port}'
                   f' --flash_port {ecu_port} --hex {hex_name} --delay 0.4')
        else:
            # Critical: combine pre-kill + reset + avrdude into ONE SSH exec.
            # The Uno bootloader only listens for ~1-2 s after reset, and a
            # separate SSH session between reset and avrdude burns 2-3 s on
            # connect/auth — by the time avrdude talks to the board, the
            # bootloader has already handed off to user code and sync fails.
            # Chaining with cmd.exe's `&` keeps the gap under 100 ms.
            reset_port = board.get("reset_port", "")
            reset_script = board.get("reset_script", "")
            # Use PowerShell + Stop-Process instead of `wmic ... delete`.
            # wmic's Terminate() can fail silently on avrdude instances
            # stuck in a kernel I/O wait on the FTDI driver (the exact
            # state that leaves ports held after a failed flash). The -Force
            # on Stop-Process delivers the same signal but surfaces errors
            # and handles more cases. Still port-scoped — only matches
            # avrdudes/serialterms for THIS ECU port.
            pre_kill = (
                f'powershell -NoProfile -Command '
                f'"Get-CimInstance Win32_Process | Where-Object {{'
                f'$_.CommandLine -match \'-P\\s+{ecu_port}\\s+-U\' -or '
                f'$_.CommandLine -match \'serialterm.*--port\\s+{ecu_port}\\b\''
                f'}} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"'
            )
            setup = f'cd {remote_dir} && copy {REMOTE_SCRIPTS_DIR}\\avrdude.conf . >nul 2>&1'
            reset_inline = ''
            if reset_script and reset_port:
                reset_inline = (
                    f' & copy {REMOTE_SCRIPTS_DIR}\\{reset_script} . >nul 2>&1'
                    f' & powershell -ExecutionPolicy Bypass -File {reset_script} -Port {reset_port}'
                )
            avrdude = (
                f' & avrdude.exe -C avrdude.conf -v'
                f' -p {AVRDUDE_DEFAULTS["mcu"]} -c {AVRDUDE_DEFAULTS["programmer"]}'
                f' -b {AVRDUDE_DEFAULTS["baudrate"]} -P {ecu_port}'
                f' -U flash:w:{hex_name}:i'
            )
            cmd = f'{pre_kill} & {setup}{reset_inline}{avrdude}'
        self._log(op_id, f"[Flash] Executing: {cmd}")
        # use_pty=True makes avrdude/python detect a TTY and flush each line
        # immediately instead of dumping everything at the end.
        # flash.py tries 57600 first (lab boards' working default), then
        # 115200 as fallback. Each attempt is capped at ~12s; 35s gives
        # the full fallback chain room to complete before the SSH cap
        # kicks in; sentinel short-circuit bails earlier on clean
        # completion.
        worker = SSHWorker(pc["host"], pc["user"], pc["password"], cmd, timeout=35, use_pty=True)
        worker.output.connect(lambda m, op=op_id: self._on_flash_output(op, m))
        worker.finished_signal.connect(
            lambda s, op=op_id, rp=release_ports, p=pc, port=ecu_port:
                self._on_flash_done(s, op, rp, p, port)
        )
        self._workers.append(worker)
        self._flash_worker = worker
        self._flash_port = ecu_port
        self._flash_pc = pc
        self._flash_is_writing = False
        self._flash_cancelled = False
        self.cancel_btn.setEnabled(True)
        worker.start()

    def _ecu_tcp_port(self, board, ecu_port):
        """Map an ECU COM port to the simulator's matching TCP UART port.
        Returns None if the board/port pair has no TCP mapping (which means
        the entry came from somewhere other than _localhost_simulator)."""
        ecu_ports = board.get("ecu_ports") or []
        tcp_ports = board.get("ecu_tcp_ports") or []
        if ecu_port in ecu_ports and len(tcp_ports) == len(ecu_ports):
            return tcp_ports[ecu_ports.index(ecu_port)]
        return None

    def _local_reset(self, op_id, board):
        """Trigger reset-on-connect on the aneb-sim TCP UART server by
        opening + immediately closing a fresh socket to the selected ECU.
        Cheap (≈ a few ms) and synchronous — no worker needed."""
        import socket
        ecu_port = self.ecu_combo.currentText()
        tcp = self._ecu_tcp_port(board, ecu_port)
        if tcp is None:
            self._log(op_id, "[Reset] No TCP mapping for this ECU — skipped.")
            return
        try:
            s = socket.create_connection(("127.0.0.1", tcp), timeout=1.0)
            s.close()
        except Exception as e:
            self._log(op_id,
                      f"[Reset] Could not connect to 127.0.0.1:{tcp}: {e}. "
                      "Is aneb-sim running?")
            return
        self._log(op_id,
                  f"[Reset] Triggered reset on {ecu_port} via TCP:{tcp}. "
                  "(Note: this kicks the aneb-sim UI bridge — restart it from "
                  "the UI when you're done.)")

    def _launch_local_flash_worker(self, op_id, pc, ecu_port, hex_name,
                                   board, release_ports):
        """Flash a local target (aneb-sim simulator) directly via avrdude.

        We use avrdude's net:host:port transport to talk straight to the
        simulator's TCP UART server, bypassing com0com entirely.  Opening
        the TCP socket triggers reset-on-connect on the sim (which kicks
        any prior client and pulses DTR), so reset and flash happen in a
        single atomic avrdude session — no separate reset step needed.

        Side effect: the aneb-sim UI's bridge gets disconnected when
        avrdude grabs the TCP socket.  The user must restart bridges
        from the aneb-sim UI after a flash if they want to keep using
        Serial / Dashboard panels.
        """
        # The .hex file is local — no SCP needed.  Resolve absolute path
        # so avrdude doesn't get confused by the cwd.
        hex_path = self.hex_path.text().strip()
        if not os.path.isabs(hex_path):
            hex_path = os.path.abspath(hex_path)
        if not os.path.isfile(hex_path):
            self._log(op_id, f"[Flash] Hex file not found: {hex_path}")
            self._on_flash_done("-1", op_id, release_ports, pc, ecu_port)
            return

        avrdude = _find_avrdude()
        if not avrdude:
            self._log(op_id,
                      "[Flash] avrdude.exe not found.  Install Arduino IDE "
                      "or add avrdude to PATH.")
            self._on_flash_done("-1", op_id, release_ports, pc, ecu_port)
            return
        avrdude_conf = _find_avrdude_conf(avrdude)

        # Prefer net: transport so opening the socket triggers the sim's
        # reset-on-connect.  Fall back to the COM port if no TCP mapping
        # is configured (defensive — _localhost_simulator always sets one).
        tcp = self._ecu_tcp_port(board, ecu_port)
        if tcp is not None:
            avr_port_arg = f"net:127.0.0.1:{tcp}"
        else:
            avr_port_arg = ecu_port

        cmd_parts = [f'"{avrdude}"']
        if avrdude_conf:
            cmd_parts += ["-C", f'"{avrdude_conf}"']
        cmd_parts += [
            "-v",
            "-p", AVRDUDE_DEFAULTS["mcu"],
            "-c", AVRDUDE_DEFAULTS["programmer"],
            "-b", AVRDUDE_DEFAULTS["baudrate"],
            "-P", avr_port_arg,
            "-U", f'flash:w:"{hex_path}":i',
        ]
        cmd = " ".join(cmd_parts)
        self._log(op_id, f"[Flash] Executing locally: {cmd}")

        worker = LocalCommandWorker(
            pc["host"], pc["user"], pc["password"], cmd, timeout=60,
        )
        worker.output.connect(lambda m, op=op_id: self._on_flash_output(op, m))
        worker.finished_signal.connect(
            lambda s, op=op_id, rp=release_ports, p=pc, port=ecu_port:
                self._on_flash_done(s, op, rp, p, port)
        )
        self._workers.append(worker)
        self._flash_worker = worker
        self._flash_port = ecu_port
        self._flash_pc = pc
        self._flash_is_writing = False
        self._flash_cancelled = False
        self.cancel_btn.setEnabled(True)
        worker.start()

    def _sftp_upload_flash_py(self, pc):
        """Push local remote_scripts/220/flash.py to c:\\2026\\flash.py on the
        remote, only if sizes differ. Keeps the helper in sync so a stale
        copy can't hang the flash flow. Called inline before launching the
        flash SSHWorker — short & synchronous; any network hitch throws."""
        import paramiko
        local_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "remote_scripts", "220", "flash.py"
        )
        local_path = os.path.normpath(local_path)
        if not os.path.isfile(local_path):
            return  # nothing to upload — fall back to whatever's there
        remote_path = f"{REMOTE_BASE_DIR}\\flash.py"
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(pc["host"], username=pc["user"],
                       password=pc["password"], timeout=10)
        try:
            sftp = client.open_sftp()
            try:
                try:
                    rstat = sftp.stat(remote_path)
                    if rstat.st_size == os.path.getsize(local_path):
                        return  # already up-to-date
                except FileNotFoundError:
                    pass
                sftp.put(local_path, remote_path)
            finally:
                sftp.close()
        finally:
            client.close()

    def _on_flash_output(self, op_id, text):
        """Log every line AND sniff for the write phase. Once avrdude starts
        programming (prints 'Writing |'), disable Cancel to prevent leaving
        the ECU in an indeterminate half-written state."""
        self._log(op_id, text)
        if (not self._flash_is_writing) and ("Writing |" in text or "writing flash" in text.lower()):
            self._flash_is_writing = True
            self.cancel_btn.setEnabled(False)
            self.log.append_log(
                "[Flash] Write phase — Cancel disabled until avrdude finishes."
            )

    def _on_flash_done(self, status, op_id, release_ports, pc=None, ecu_port=None):
        # Drop Cancel / flash-worker tracking first so a late-arriving signal
        # can't leave the button falsely enabled.
        cancelled = self._flash_cancelled
        self._flash_cancelled = False
        self._flash_worker = None
        self.cancel_btn.setEnabled(False)

        # A user cancel overrides whatever the worker reported — paramiko can
        # return a clean "0" exit status when we close a channel mid-op, which
        # would otherwise make a cancel look like SUCCESS.
        if cancelled or status == "-2":
            self._log(op_id, "[Flash] CANCELLED by user")
        elif status == "0":
            self._log(op_id, "[Flash] SUCCESS")
        elif status == "-1":
            self._log(op_id, "[Flash] FAILED — connection error or timeout.")
            self._log(op_id, "[Flash] Check that the COM port is not in use and the board is connected.")
        else:
            self._log(op_id, f"[Flash] FAILED (exit={status})")
        if release_ports is not None:
            self._release_all_ports(*release_ports)

    def _cancel_flash(self):
        """Abort the running op (reset or avrdude). Disabled automatically
        once avrdude enters the write phase — see _on_flash_output."""
        worker = self._flash_worker
        if worker is None:
            return
        self._flash_cancelled = True  # read by _on_flash_done to force CANCELLED status
        pc = getattr(self, "_flash_pc", None)
        port = getattr(self, "_flash_port", None)
        self.cancel_btn.setEnabled(False)
        self.log.append_log(f"[Flash] Cancel requested — killing remote ops on {port}...")

        # Port-scoped remote kill via SSHWorker (keeps all paramiko calls on
        # worker threads Qt knows about; never touches widgets off-thread).
        # Matches avrdude (-P COMxx -U), reset scripts (reset.ps1 -Port COMxx),
        # and orphan serialterms (--port COMxx) — all scoped to THIS port,
        # so other students' work on different boards isn't affected.
        if pc is not None and port:
            kill_cmd = (
                f"wmic process where \"commandline like '%-P {port} -U%'\" delete"
                f" & wmic process where \"commandline like '%reset.ps1 -Port {port}%'\" delete"
                f" & wmic process where \"commandline like '%serialterm%--port {port}%'\" delete"
                f" & wmic process where \"commandline like '%flash.py%--flash_port {port}%'\" delete"
            )
            kw = SSHWorker(pc["host"], pc["user"], pc["password"],
                           kill_cmd, timeout=10)
            self._workers.append(kw)
            kw.start()

        # Stop reading output on our side so the running worker unblocks.
        # Its finished_signal → _on_flash_done / _on_reset_done releases ports.
        try:
            worker.stop()
        except Exception:
            pass

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
        self._log(op, "=== Starting full flash sequence ===")
        held = (pc_key, ports_to_check)
        # Local mode (aneb-sim): the .hex is already on disk and avrdude
        # runs locally, so there is nothing to upload.  Skip SCP and go
        # straight to the flash phase.
        if pc.get("flash_method") == "local":
            self._log(op, "[All] Local target — skipping upload.")
            self._after_upload(True, op, held)
            return
        remote = self.remote_folder.text().strip().replace("\\", "/")
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
        # Reset is now chained inline inside _launch_flash_worker for the
        # avrdude path (and flash.py already bundles its own reset), so the
        # full sequence goes through a single SSH exec — no bootloader-window
        # race from SSH session setup between reset and sync.
        self._log(op_id, "[All] Resetting + flashing...")
        self._flash_firmware(_internal=True, op_id=op_id, release_ports=held)

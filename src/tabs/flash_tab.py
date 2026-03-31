"""Firmware flash tab."""
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QLineEdit, QFileDialog,
)

from lab_config import COMPUTERS, AVRDUDE_DEFAULTS, REMOTE_BASE_DIR, REMOTE_SCRIPTS_DIR
from settings import get_remote_user_dir
from widgets import LogWidget
from workers import SSHWorker, SCPWorker


class FlashTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        layout = QVBoxLayout(self)

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
        self.remote_folder = QLineEdit(get_remote_user_dir())
        self.remote_folder.setPlaceholderText("Your folder on the remote PC")
        g.addWidget(self.remote_folder, 4, 1)

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

        self._on_pc_changed(self.pc_combo.currentText())

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

    def _browse_hex(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select HEX file", "", "HEX Files (*.hex);;All (*)")
        if path:
            self.hex_path.setText(path)

    def _upload_hex(self):
        pc = self._get_pc_cfg()
        local = self.hex_path.text().strip()
        if not local or not os.path.isfile(local):
            self.log.append_log("[Upload] Please select a valid .hex file.")
            return
        remote = self.remote_folder.text().strip().replace("\\", "/")
        worker = SCPWorker(pc["host"], pc["user"], pc["password"], local, remote)
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
            cmd = (f'mkdir {get_remote_user_dir()} >nul 2>&1 & cd {get_remote_user_dir()}'
                   f' && copy {REMOTE_SCRIPTS_DIR}\\{reset_script} . >nul 2>&1'
                   f' & powershell -ExecutionPolicy Bypass -File {reset_script}')
        elif reset_port and pc.get("flash_method") == "flash.py":
            self.log.append_log("[Reset] This PC uses flash.py — reset is integrated into flash.")
            return
        else:
            self.log.append_log("[Reset] No reset method configured for this board.")
            return
        self.log.append_log("[Reset] Sending reset signal...")
        worker = SSHWorker(pc["host"], pc["user"], pc["password"], cmd)
        worker.output.connect(self.log.append_log)
        worker.finished_signal.connect(lambda s: self.log.append_log(f"[Reset] Exit status: {s}"))
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
            cmd = (f'cd {remote_dir} && copy {REMOTE_SCRIPTS_DIR}\\avrdude.conf . >nul 2>&1'
                   f' & python {REMOTE_BASE_DIR}\\flash.py --reset_port {reset_port}'
                   f' --flash_port {ecu_port} --hex {hex_name} --delay 0.4')
        else:
            cmd = (f'cd {remote_dir} && copy {REMOTE_SCRIPTS_DIR}\\avrdude.conf . >nul 2>&1'
                   f' & avrdude.exe -C avrdude.conf -v'
                   f' -p {AVRDUDE_DEFAULTS["mcu"]} -c {AVRDUDE_DEFAULTS["programmer"]}'
                   f' -b {AVRDUDE_DEFAULTS["baudrate"]} -P {ecu_port}'
                   f' -U flash:w:{hex_name}:i')
        self.log.append_log(f"[Flash] Executing: {cmd}")
        worker = SSHWorker(pc["host"], pc["user"], pc["password"], cmd)
        worker.output.connect(self.log.append_log)
        worker.finished_signal.connect(
            lambda s: self.log.append_log(f"[Flash] {'SUCCESS' if s == '0' else 'FAILED'} (exit={s})")
        )
        self._workers.append(worker)
        worker.start()

    def _do_all(self):
        pc = self._get_pc_cfg()
        local = self.hex_path.text().strip()
        if not local or not os.path.isfile(local):
            self.log.append_log("[All] Please select a valid .hex file.")
            return
        remote = self.remote_folder.text().strip().replace("\\", "/")
        self.log.append_log("=== Starting full flash sequence ===")
        upload_worker = SCPWorker(pc["host"], pc["user"], pc["password"], local, remote)
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
        if pc.get("flash_method") == "flash.py":
            self._flash_firmware()
            return
        reset_script = board.get("reset_script")
        if reset_script:
            cmd = (f'mkdir {get_remote_user_dir()} >nul 2>&1 & cd {get_remote_user_dir()}'
                   f' && copy {REMOTE_SCRIPTS_DIR}\\{reset_script} . >nul 2>&1'
                   f' & powershell -ExecutionPolicy Bypass -File {reset_script}')
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

"""Serial terminal tab — up to 4 independent connections with spatial layout."""
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QFrame, QSplitter, QCheckBox,
)

from lab_config import COMPUTERS, SERIAL_DEFAULTS
from settings import get_remote_user_dir
from widgets import LogWidget
from workers import SerialWorker, SCPWorker


class SerialPanel(QFrame):
    """Compact serial connection panel — config in grid, log takes the space."""
    port_usage_changed = Signal()
    close_requested = Signal(object)

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
        self.pc_combo.currentTextChanged.connect(self._on_pc_changed)
        g.addWidget(self.pc_combo, 0, 1)

        g.addWidget(QLabel("Remote Folder:"), 0, 2)
        self.remote_dir = QLineEdit(get_remote_user_dir())
        self.remote_dir.setPlaceholderText("Your folder on the remote PC")
        g.addWidget(self.remote_dir, 0, 3, 1, 3)

        g.addWidget(QLabel("Board:"), 1, 0)
        self.board_combo = QComboBox()
        self.board_combo.currentTextChanged.connect(self._on_board_changed)
        g.addWidget(self.board_combo, 1, 1)

        g.addWidget(QLabel("COM Port:"), 1, 2)
        self.port_combo = QComboBox()
        g.addWidget(self.port_combo, 1, 3)

        g.addWidget(QLabel("Baudrate:"), 1, 4)
        self.baudrate = QComboBox()
        self.baudrate.setEditable(True)
        self.baudrate.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baudrate.setCurrentText(SERIAL_DEFAULTS["baudrate"])
        g.addWidget(self.baudrate, 1, 5)

        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("Open Serial")
        self.connect_btn.clicked.connect(self._toggle_serial)
        btn_row.addWidget(self.connect_btn)

        self.upload_btn = QPushButton("Upload serialterm.py")
        self.upload_btn.setToolTip("Upload serialterm.py to remote folder")
        self.upload_btn.clicked.connect(self._upload_serialterm)
        btn_row.addWidget(self.upload_btn)

        self.clear_btn = QPushButton("Clear Log")
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
        self.send_input = QLineEdit()
        self.send_input.setPlaceholderText("Type command to send over serial...")
        self.send_input.returnPressed.connect(self._send_command)
        self.send_input.setEnabled(False)
        send_row.addWidget(self.send_input)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send_command)
        self.send_btn.setEnabled(False)
        send_row.addWidget(self.send_btn)
        layout.addLayout(send_row)

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
        available = [p for p in all_ports if (pc_name, p) not in used]
        self.port_combo.clear()
        self.port_combo.addItems(available)

    def refresh_ports(self):
        self._on_board_changed(None)

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
        self._connected_port_key = (self.pc_combo.currentText(), port)
        self.connect_btn.setText("Close Serial")
        self.send_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.pc_combo.setEnabled(False)
        self.board_combo.setEnabled(False)
        self.port_combo.setEnabled(False)
        self.baudrate.setEnabled(False)
        self.remote_dir.setEnabled(False)
        self.serial_worker = SerialWorker(
            pc["host"], pc["user"], pc["password"], port, baud, remote_dir
        )
        self.serial_worker.output.connect(self.log.append_log)
        self.serial_worker.finished_signal.connect(self._on_serial_done)
        self._workers.append(self.serial_worker)
        self.serial_worker.start()
        self.port_usage_changed.emit()

    def _send_command(self):
        if not self.serial_worker:
            return
        text = self.send_input.text()
        if not text:
            return
        self.log.append_log(f"> {text}")
        self.serial_worker.send_data(text)
        self.send_input.clear()

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
        self.pc_combo.setEnabled(True)
        self.board_combo.setEnabled(True)
        self.port_combo.setEnabled(True)
        self.baudrate.setEnabled(True)
        self.remote_dir.setEnabled(True)

    def _stop_serial(self):
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
        self.panels.append(panel)
        self._rebuild_layout()
        self._update_add_btn()

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

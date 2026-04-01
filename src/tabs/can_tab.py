"""CAN network configuration tab — visual bus topology with per-board selectors."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QRadioButton,
    QButtonGroup, QFrame, QSizePolicy,
)

from lab_config import COMPUTERS
from widgets import LogWidget
from workers import SSHWorker


# CAN selector port mapping — same ports as reset
_CAN_SELECTOR_PORTS = {
    "Placa 01": "reset_port",
    "Placa 02": "reset_port",
    "Placa 03": "reset_port",
    "Placa 04": "reset_port",
}


class BusTopologyWidget(QWidget):
    """Visual representation of two CAN buses with boards connected to them."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Board states: {board_name: 1 or 2}
        self._board_states = {}
        self._board_colors = {
            "Placa 01": QColor("#c0392b"),
            "Placa 02": QColor("#2980b9"),
            "Placa 03": QColor("#f39c12"),
            "Placa 04": QColor("#27ae60"),
        }

    def set_board_states(self, states: dict):
        self._board_states = dict(states)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 40
        bus_x_start = margin + 80
        bus_x_end = w - margin
        bus_y1 = h * 0.30  # CAN1 bus line
        bus_y2 = h * 0.70  # CAN2 bus line

        # Background
        p.fillRect(self.rect(), QColor("#1e1e1e"))

        # Bus labels
        label_font = QFont("Consolas", 11, QFont.Bold)
        p.setFont(label_font)

        p.setPen(QColor("#4CAF50"))
        p.drawText(10, int(bus_y1 + 5), "CAN 1")

        p.setPen(QColor("#FF9800"))
        p.drawText(10, int(bus_y2 + 5), "CAN 2")

        # Bus lines
        bus_pen = QPen(QColor("#4CAF50"), 3)
        p.setPen(bus_pen)
        p.drawLine(int(bus_x_start), int(bus_y1), int(bus_x_end), int(bus_y1))

        bus_pen.setColor(QColor("#FF9800"))
        p.setPen(bus_pen)
        p.drawLine(int(bus_x_start), int(bus_y2), int(bus_x_end), int(bus_y2))

        # Termination resistors (small zigzag at ends)
        for bus_y, color in [(bus_y1, QColor("#4CAF50")), (bus_y2, QColor("#FF9800"))]:
            p.setPen(QPen(color, 2))
            rx = bus_x_end + 5
            for end_x in [int(bus_x_start - 5), int(rx)]:
                p.drawLine(end_x, int(bus_y - 6), end_x, int(bus_y + 6))

        # Draw boards
        boards = list(self._board_colors.keys())
        n = len(boards)
        if n == 0:
            return

        spacing = (bus_x_end - bus_x_start) / (n + 1)
        board_font = QFont("Consolas", 9, QFont.Bold)
        p.setFont(board_font)

        for i, board_name in enumerate(boards):
            bx = int(bus_x_start + spacing * (i + 1))
            bus_num = self._board_states.get(board_name, 1)
            bus_y = bus_y1 if bus_num == 1 else bus_y2
            color = self._board_colors.get(board_name, QColor("#888"))

            # Board box
            box_w, box_h = 70, 30
            box_x = bx - box_w // 2

            # Position box above or below the bus line
            if bus_num == 1:
                box_y = int(bus_y - box_h - 12)
            else:
                box_y = int(bus_y + 12)

            # Connection line from box to bus
            conn_pen = QPen(color, 2)
            p.setPen(conn_pen)
            if bus_num == 1:
                p.drawLine(bx, box_y + box_h, bx, int(bus_y))
            else:
                p.drawLine(bx, box_y, bx, int(bus_y))

            # Draw node dot on bus
            p.setBrush(QBrush(color))
            p.setPen(Qt.NoPen)
            p.drawEllipse(bx - 4, int(bus_y) - 4, 8, 8)

            # Draw board box
            p.setPen(QPen(color, 2))
            p.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 60)))
            p.drawRoundedRect(box_x, box_y, box_w, box_h, 5, 5)

            # Board label
            p.setPen(color)
            ecu_label = board_name.replace("Placa ", "P")
            p.drawText(box_x, box_y, box_w, box_h, Qt.AlignCenter, ecu_label)

        p.end()


class CANTab(QWidget):
    """CAN network configuration — visual topology + per-board selectors."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        self._board_states = {}  # {board_name: 1 or 2}

        layout = QVBoxLayout(self)

        # PC selector
        pc_row = QHBoxLayout()
        pc_row.addWidget(QLabel("Computer:"))
        self.pc_combo = QComboBox()
        self.pc_combo.addItems(COMPUTERS.keys())
        self.pc_combo.currentTextChanged.connect(self._on_pc_changed)
        pc_row.addWidget(self.pc_combo, stretch=1)
        pc_row.addStretch(2)
        layout.addLayout(pc_row)

        # Visual topology
        topo_grp = QGroupBox("CAN Bus Topology")
        topo_layout = QVBoxLayout(topo_grp)
        self.topology = BusTopologyWidget()
        topo_layout.addWidget(self.topology)
        layout.addWidget(topo_grp, stretch=1)

        # Board selectors
        sel_grp = QGroupBox("Board Configuration")
        sel_layout = QGridLayout(sel_grp)

        sel_layout.addWidget(QLabel("Board"), 0, 0)
        sel_layout.addWidget(QLabel("CAN 1"), 0, 1)
        sel_layout.addWidget(QLabel("CAN 2"), 0, 2)
        sel_layout.addWidget(QLabel("Port"), 0, 3)
        sel_layout.addWidget(QLabel(""), 0, 4)

        self._radio_groups = {}
        self._apply_buttons = {}
        self._port_labels = {}

        for i, board_name in enumerate(["Placa 01", "Placa 02", "Placa 03", "Placa 04"]):
            row = i + 1
            colors = ["#c0392b", "#2980b9", "#f39c12", "#27ae60"]

            name_label = QLabel(board_name)
            name_label.setStyleSheet(f"color: {colors[i]}; font-weight: bold;")
            sel_layout.addWidget(name_label, row, 0)

            rb1 = QRadioButton()
            rb2 = QRadioButton()
            rb1.setChecked(True)

            group = QButtonGroup(self)
            group.addButton(rb1, 1)
            group.addButton(rb2, 2)
            group.buttonClicked.connect(
                lambda btn, bn=board_name: self._on_radio_changed(bn)
            )
            self._radio_groups[board_name] = group

            sel_layout.addWidget(rb1, row, 1, alignment=Qt.AlignCenter)
            sel_layout.addWidget(rb2, row, 2, alignment=Qt.AlignCenter)

            port_label = QLabel("—")
            port_label.setStyleSheet("color: #888;")
            self._port_labels[board_name] = port_label
            sel_layout.addWidget(port_label, row, 3)

            apply_btn = QPushButton("Apply")
            apply_btn.setFixedWidth(70)
            apply_btn.clicked.connect(
                lambda checked, bn=board_name: self._apply_single(bn)
            )
            self._apply_buttons[board_name] = apply_btn
            sel_layout.addWidget(apply_btn, row, 4)

            self._board_states[board_name] = 1

        layout.addWidget(sel_grp)

        # Presets
        preset_grp = QGroupBox("Quick Presets")
        preset_layout = QHBoxLayout(preset_grp)

        presets = [
            ("All CAN 1", {1: 1, 2: 1, 3: 1, 4: 1}),
            ("All CAN 2", {1: 2, 2: 2, 3: 2, 4: 2}),
            ("P1+P2 CAN1, P3+P4 CAN2", {1: 1, 2: 1, 3: 2, 4: 2}),
            ("P1+P3 CAN1, P2+P4 CAN2", {1: 1, 2: 2, 3: 1, 4: 2}),
        ]
        for label, config in presets:
            btn = QPushButton(label)
            btn.clicked.connect(
                lambda checked, c=config: self._apply_preset(c)
            )
            preset_layout.addWidget(btn)

        layout.addWidget(preset_grp)

        # Log
        self.log = LogWidget()
        self.log.setMaximumHeight(120)
        layout.addWidget(self.log)

        # Initialize
        self._on_pc_changed(self.pc_combo.currentText())

    def _get_pc_cfg(self):
        return COMPUTERS.get(self.pc_combo.currentText(), {})

    def _on_pc_changed(self, _text):
        pc = self._get_pc_cfg()
        boards = pc.get("boards", {})
        for board_name, port_label in self._port_labels.items():
            board_cfg = boards.get(board_name, {})
            port = board_cfg.get("reset_port")
            port_label.setText(port if port else "N/A")
            # Disable controls if no port
            has_port = port is not None
            self._apply_buttons[board_name].setEnabled(has_port)
            for btn in self._radio_groups[board_name].buttons():
                btn.setEnabled(has_port)
        self._update_topology()

    def _on_radio_changed(self, board_name):
        group = self._radio_groups[board_name]
        self._board_states[board_name] = group.checkedId()
        self._update_topology()

    def _update_topology(self):
        self.topology.set_board_states(self._board_states)

    def _apply_single(self, board_name):
        bus = self._board_states.get(board_name, 1)
        pc = self._get_pc_cfg()
        boards = pc.get("boards", {})
        board_cfg = boards.get(board_name, {})
        port = board_cfg.get("reset_port")

        if not port:
            self.log.append_log(f"[CAN] {board_name}: no selector port configured.")
            return

        cmd = (
            f'powershell -Command "'
            f"$s = New-Object System.IO.Ports.SerialPort {port},19200,None,8,One; "
            f"$s.ReadTimeout = 2000; $s.Open(); "
            f"$s.WriteLine('AT C{bus}'); "
            f"Start-Sleep -Milliseconds 500; "
            f"$r = ''; if($s.BytesToRead -gt 0){{$r = $s.ReadExisting()}}; "
            f"$s.Close(); "
            f"Write-Host $r.Trim()"
            f'"'
        )

        self.log.append_log(f"[CAN] {board_name} -> CAN {bus} ({port})...")
        worker = SSHWorker(
            pc["host"], pc["user"], pc["password"], cmd
        )
        worker.output.connect(self.log.append_log)
        worker.finished_signal.connect(
            lambda s, bn=board_name, b=bus: self._on_apply_done(bn, b, s)
        )
        self._workers.append(worker)
        worker.start()

    def _on_apply_done(self, board_name, bus, status):
        if status == "0":
            self.log.append_log(f"[CAN] {board_name} set to CAN {bus} OK")
        else:
            self.log.append_log(f"[CAN] {board_name} failed (exit={status})")

    def _apply_preset(self, config):
        """Apply a preset configuration. config = {1: bus, 2: bus, 3: bus, 4: bus}"""
        boards = ["Placa 01", "Placa 02", "Placa 03", "Placa 04"]
        for idx, board_name in enumerate(boards, 1):
            bus = config.get(idx, 1)
            self._board_states[board_name] = bus
            group = self._radio_groups[board_name]
            for btn in group.buttons():
                if group.id(btn) == bus:
                    btn.setChecked(True)
        self._update_topology()
        # Apply all
        for board_name in boards:
            self._apply_single(board_name)

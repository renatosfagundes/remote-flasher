"""CAN network configuration tab — visual bus topology with per-board selectors."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QRadioButton,
    QButtonGroup, QFrame, QSizePolicy,
)

from lab_config import COMPUTERS
from widgets import LogWidget, make_log_with_clear
from workers import SSHWorker




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

    def set_board_states(self, states: dict, available: dict = None):
        """Update board positions. available = {board_name: bool} for which boards have selectors."""
        self._board_states = dict(states)
        self._available = available or {k: True for k in states}
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
            has_selector = self._available.get(board_name, True)
            color = self._board_colors.get(board_name, QColor("#888"))

            box_w, box_h = 70, 30
            box_x = bx - box_w // 2

            if not has_selector:
                # No CAN selector — show greyed out between the two buses
                mid_y = (bus_y1 + bus_y2) / 2
                box_y = int(mid_y - box_h / 2)
                grey = QColor("#444")

                # Dashed line to indicate unknown connection
                dash_pen = QPen(grey, 1, Qt.DashLine)
                p.setPen(dash_pen)
                p.drawLine(bx, int(bus_y1), bx, box_y)
                p.drawLine(bx, box_y + box_h, bx, int(bus_y2))

                # Grey box with "?"
                p.setPen(QPen(grey, 2))
                p.setBrush(QBrush(QColor(60, 60, 60, 100)))
                p.drawRoundedRect(box_x, box_y, box_w, box_h, 5, 5)

                p.setPen(QColor("#666"))
                ecu_label = board_name.replace("Placa ", "P") + " ?"
                p.drawText(box_x, box_y, box_w, box_h, Qt.AlignCenter, ecu_label)
            else:
                # Normal board with CAN selector
                bus_num = self._board_states.get(board_name, 1)
                bus_y = bus_y1 if bus_num == 1 else bus_y2

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

                # Node dot on bus
                p.setBrush(QBrush(color))
                p.setPen(Qt.NoPen)
                p.drawEllipse(bx - 4, int(bus_y) - 4, 8, 8)

                # Board box
                p.setPen(QPen(color, 2))
                p.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 60)))
                p.drawRoundedRect(box_x, box_y, box_w, box_h, 5, 5)

                # Label
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
        self._per_pc_states = {}  # {pc_name: {board_name: 1 or 2}}
        self._board_statuses = {}  # {board_name: "ok"|"warn"|"error"|"unknown"}
        self._per_pc_statuses = {}  # {pc_name: {board_name: status}}
        self._pending_output = {}  # {board_name: accumulated output}
        self._apply_queue = []  # sequential queue for apply commands

        layout = QVBoxLayout(self)

        # PC selector
        pc_row = QHBoxLayout()
        pc_row.addWidget(QLabel("Computer:"))
        self.pc_combo = QComboBox()
        self.pc_combo.addItems(COMPUTERS.keys())
        self.pc_combo.setToolTip("Lab PC whose boards you want to configure.")
        self.pc_combo.currentTextChanged.connect(self._on_pc_changed)
        pc_row.addWidget(self.pc_combo, stretch=1)
        pc_row.addStretch(2)
        layout.addLayout(pc_row)

        # Visual topology
        topo_grp = QGroupBox("CAN Bus Topology")
        topo_layout = QVBoxLayout(topo_grp)
        self.topology = BusTopologyWidget()
        self.topology.setToolTip(
            "Live diagram: each Placa shown on the bus it's connected to.\n"
            "Greyed-out boards have no CAN selector (can't be switched remotely)."
        )
        topo_layout.addWidget(self.topology)
        layout.addWidget(topo_grp, stretch=1)

        # Board selectors
        sel_grp = QGroupBox("Board Configuration")
        sel_layout = QGridLayout(sel_grp)

        sel_layout.addWidget(QLabel("Board"), 0, 0)
        sel_layout.addWidget(QLabel("CAN 1"), 0, 1)
        sel_layout.addWidget(QLabel("CAN 2"), 0, 2)
        sel_layout.addWidget(QLabel("Port"), 0, 3)
        sel_layout.addWidget(QLabel("Status"), 0, 4)
        sel_layout.addWidget(QLabel(""), 0, 5)

        self._radio_groups = {}
        self._radio_buttons = {}  # {board_name: (rb1, rb2)}
        self._na_labels = {}      # {board_name: QLabel} shown when no port
        self._apply_buttons = {}
        self._port_labels = {}
        self._status_labels = {}

        for i, board_name in enumerate(["Placa 01", "Placa 02", "Placa 03", "Placa 04"]):
            row = i + 1
            colors = ["#c0392b", "#2980b9", "#f39c12", "#27ae60"]

            name_label = QLabel(board_name)
            name_label.setStyleSheet(f"color: {colors[i]}; font-weight: bold;")
            sel_layout.addWidget(name_label, row, 0)

            rb1 = QRadioButton()
            rb1.setToolTip(f"Put {board_name} on CAN bus 1 (green).")
            rb2 = QRadioButton()
            rb2.setToolTip(f"Put {board_name} on CAN bus 2 (orange).")
            rb1.setChecked(True)

            group = QButtonGroup(self)
            group.addButton(rb1, 1)
            group.addButton(rb2, 2)
            group.buttonClicked.connect(
                lambda btn, bn=board_name: self._on_radio_changed(bn)
            )
            self._radio_groups[board_name] = group
            self._radio_buttons[board_name] = (rb1, rb2)

            sel_layout.addWidget(rb1, row, 1, alignment=Qt.AlignCenter)
            sel_layout.addWidget(rb2, row, 2, alignment=Qt.AlignCenter)

            # "No selector" label — spans CAN1+CAN2 columns, hidden by default
            na_label = QLabel("No CAN selector")
            na_label.setStyleSheet("color: #666; font-style: italic;")
            na_label.setAlignment(Qt.AlignCenter)
            na_label.setVisible(False)
            na_label.setToolTip(
                "This board has no remote-controllable CAN selector — its bus\n"
                "must be set by physically moving a jumper on the hardware."
            )
            sel_layout.addWidget(na_label, row, 1, 1, 2, alignment=Qt.AlignCenter)
            self._na_labels[board_name] = na_label

            port_label = QLabel("—")
            port_label.setStyleSheet("color: #888;")
            port_label.setToolTip("COM port used to drive this board's CAN selector.")
            self._port_labels[board_name] = port_label
            sel_layout.addWidget(port_label, row, 3)

            status_label = QLabel("?")
            status_label.setStyleSheet("color: #666; font-weight: bold; font-size: 14px;")
            status_label.setFixedWidth(24)
            status_label.setAlignment(Qt.AlignCenter)
            status_label.setToolTip(
                "Last apply/detect result: ✓ OK, ! no response, ✗ error, ? unknown."
            )
            self._status_labels[board_name] = status_label
            sel_layout.addWidget(status_label, row, 4, alignment=Qt.AlignCenter)

            apply_btn = QPushButton("Apply")
            apply_btn.setFixedWidth(70)
            apply_btn.setToolTip(
                f"Send the 'AT C<n>' command to switch {board_name} to the selected CAN bus."
            )
            apply_btn.clicked.connect(
                lambda checked, bn=board_name: self._apply_single(bn)
            )
            self._apply_buttons[board_name] = apply_btn
            sel_layout.addWidget(apply_btn, row, 5)

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
            btn.setToolTip(f"Apply preset to all boards at once: {label}.")
            btn.clicked.connect(
                lambda checked, c=config: self._apply_preset(c)
            )
            preset_layout.addWidget(btn)

        preset_layout.addSpacing(20)
        detect_btn = QPushButton("Detect Boards")
        detect_btn.setStyleSheet("font-weight: bold;")
        detect_btn.setToolTip(
            "Query every board's CAN selector (AT BI / FV / BV) to see\n"
            "which bus it's on and whether the controller is alive."
        )
        detect_btn.clicked.connect(self._query_all)
        preset_layout.addWidget(detect_btn)

        layout.addWidget(preset_grp)

        # Log
        self.log = make_log_with_clear(layout, max_height=120)

        # Initialize
        self._on_pc_changed(self.pc_combo.currentText())

    def _get_pc_cfg(self):
        return COMPUTERS.get(self.pc_combo.currentText(), {})

    def _on_pc_changed(self, _text):
        pc_name = self.pc_combo.currentText()

        # Save current state for the previous PC
        if hasattr(self, '_current_pc') and self._current_pc:
            self._per_pc_states[self._current_pc] = dict(self._board_states)
            self._per_pc_statuses[self._current_pc] = dict(self._board_statuses)
        self._current_pc = pc_name

        pc = self._get_pc_cfg()
        boards = pc.get("boards", {})
        saved = self._per_pc_states.get(pc_name, {})
        saved_statuses = self._per_pc_statuses.get(pc_name, {})

        for board_name in ["Placa 01", "Placa 02", "Placa 03", "Placa 04"]:
            board_cfg = boards.get(board_name, {})
            port = board_cfg.get("can_selector_port")
            has_port = port is not None
            rb1, rb2 = self._radio_buttons[board_name]
            group = self._radio_groups[board_name]

            # Restore saved bus state (or default CAN1)
            bus = saved.get(board_name, 1)
            self._board_states[board_name] = bus
            for btn in group.buttons():
                if group.id(btn) == bus:
                    btn.setChecked(True)

            # Show radio buttons or "No selector" label
            rb1.setVisible(has_port)
            rb2.setVisible(has_port)
            self._na_labels[board_name].setVisible(not has_port)

            # Update port label, apply button, and restore status indicator
            self._port_labels[board_name].setText(port if port else "—")
            self._apply_buttons[board_name].setVisible(has_port)
            status = saved_statuses.get(board_name, "unknown")
            self._set_status(board_name, status)

        self._update_topology()

    def _on_radio_changed(self, board_name):
        group = self._radio_groups[board_name]
        self._board_states[board_name] = group.checkedId()
        # Save immediately for current PC
        pc_name = self.pc_combo.currentText()
        self._per_pc_states[pc_name] = dict(self._board_states)
        self._update_topology()

    def _update_topology(self):
        pc = self._get_pc_cfg()
        boards_cfg = pc.get("boards", {})
        available = {}
        for board_name in ["Placa 01", "Placa 02", "Placa 03", "Placa 04"]:
            port = boards_cfg.get(board_name, {}).get("can_selector_port")
            available[board_name] = port is not None
        self.topology.set_board_states(self._board_states, available)

    def _apply_single(self, board_name):
        """Queue a board for sequential CAN bus apply."""
        bus = self._board_states.get(board_name, 1)
        pc = self._get_pc_cfg()
        boards = pc.get("boards", {})
        board_cfg = boards.get(board_name, {})
        port = board_cfg.get("can_selector_port")

        if not port:
            self.log.append_log(f"[CAN] {board_name}: no selector port configured.")
            return

        self._apply_queue.append((board_name, bus, port, pc))
        # Start processing if this is the only item (not already running)
        if len(self._apply_queue) == 1:
            self._process_next_apply()

    def _process_next_apply(self):
        """Process the next board in the sequential apply queue."""
        if not self._apply_queue:
            return
        board_name, bus, port, pc = self._apply_queue[0]

        # Local PCs (aneb-sim simulator) only have one logical CAN bus
        # today and there's no AT-command selector to switch -- the
        # simulator just routes every chip's MCP2515 to the same bus.
        # Treat the apply as immediately successful so the UI shows
        # CAN <bus> as the active selection.  When future aneb-sim
        # builds support multiple buses this branch can dispatch over
        # the existing JSON-Lines protocol instead.
        if pc.get("flash_method") == "local":
            self.log.append_log(
                f"[CAN] {board_name} -> CAN {bus} (aneb-sim, single-bus model)")
            # Match the success status string the SSH path emits ("0").
            self._on_apply_done(board_name, bus, "0")
            return

        cmd = (
            f'powershell -Command "'
            f"$s = New-Object System.IO.Ports.SerialPort {port},19200,None,8,One; "
            f"$s.ReadTimeout = 2000; $s.Open(); "
            f"Start-Sleep -Milliseconds 200; "
            f"if($s.BytesToRead -gt 0){{$s.ReadExisting() | Out-Null}}; "
            f"$s.WriteLine('AT C{bus}'); "
            f"Start-Sleep -Milliseconds 500; "
            f"$r = ''; if($s.BytesToRead -gt 0){{$r = $s.ReadExisting()}}; "
            f"$s.Close(); "
            f"Write-Host $r.Trim()"
            f'"'
        )

        self.log.append_log(f"[CAN] {board_name} -> CAN {bus} ({port})...")
        self._pending_output[board_name] = ""
        worker = SSHWorker(
            pc["host"], pc["user"], pc["password"], cmd
        )
        worker.output.connect(
            lambda line, bn=board_name: self._collect_output(bn, line)
        )
        worker.finished_signal.connect(
            lambda s, bn=board_name, b=bus: self._on_apply_done(bn, b, s)
        )
        self._workers.append(worker)
        worker.start()

    def _collect_output(self, board_name, line):
        self._pending_output[board_name] = (
            self._pending_output.get(board_name, "") + line + "\n"
        )

    def _on_apply_done(self, board_name, bus, status):
        output = self._pending_output.pop(board_name, "")

        if status != "0":
            self.log.append_log(f"[CAN] {board_name} FAILED (exit={status})")
            self._set_status(board_name, "error")
        elif "OK" in output:
            self.log.append_log(f"[CAN] {board_name} set to CAN {bus} — OK")
            self._set_status(board_name, "ok")
        else:
            self.log.append_log(f"[CAN] {board_name} set to CAN {bus} — no response")
            self._set_status(board_name, "warn")

        # Process next board in queue
        if self._apply_queue:
            self._apply_queue.pop(0)
        if self._apply_queue:
            self._process_next_apply()

    def _set_status(self, board_name, state):
        """Update the status indicator for a board. state: 'ok', 'warn', 'error', 'unknown'."""
        self._board_statuses[board_name] = state
        colors = {"ok": "#27ae60", "warn": "#f39c12", "error": "#c0392b", "unknown": "#666"}
        icons = {"ok": "\u2713", "warn": "!", "error": "\u2717", "unknown": "?"}
        label = self._status_labels.get(board_name)
        if label:
            label.setText(icons.get(state, "?"))
            label.setStyleSheet(
                f"color: {colors.get(state, '#666')}; font-weight: bold; font-size: 14px;"
            )

    def _query_all(self):
        """Query current CAN bus state for all boards on the selected PC."""
        pc = self._get_pc_cfg()
        boards = pc.get("boards", {})
        any_queried = False
        # Iterate over the PC's actual boards rather than a hard-coded
        # list — that way variants like 'Placa 01 (aneb-sim)' (the
        # local simulator board) are queried alongside 'Placa 01'..04
        # on real lab PCs.
        for board_name, board_cfg in boards.items():
            port = board_cfg.get("can_selector_port") if board_cfg else None
            if port:
                self._query_board(board_name, port, pc)
                any_queried = True
        if not any_queried:
            self.log.append_log("[CAN] No boards with CAN selectors on this PC.")

    def _query_board(self, board_name, port, pc):
        """Send AT BI + AT FV + AT BV to a board to identify it."""
        # Local PCs (aneb-sim simulator) don't expose an AT-command
        # interface -- the board id / firmware version / board version
        # are static for the simulator.  Synthesize a response in the
        # same `BI:<id>|FV:<ver>|BV:<rev>` format the real boards return
        # so the rest of the query/display flow doesn't need to know
        # whether the board was real or simulated.
        if pc.get("flash_method") == "local":
            self.log.append_log(f"[CAN] Querying {board_name} (aneb-sim)...")
            self._pending_output[board_name] = "BI:aneb-sim|FV:1.0|BV:ANEB v1.1"
            self._on_query_done(board_name, "0")
            return

        # Helper: send cmd, wait, read all available bytes in a loop
        # Using a PS function to avoid response bleed between commands
        cmd = (
            f'powershell -Command "'
            f"function Read-AT($s, $cmd) {{ "
            f"$s.DiscardInBuffer(); "
            f"$s.WriteLine($cmd); "
            f"$r = ''; "
            f"for($i=0; $i -lt 3; $i++) {{ "
            f"Start-Sleep -Milliseconds 300; "
            f"if($s.BytesToRead -gt 0){{$r += $s.ReadExisting()}} "
            f"}}; "
            f"return $r.Trim() "
            f"}}; "
            f"$s = New-Object System.IO.Ports.SerialPort {port},19200,None,8,One; "
            f"$s.ReadTimeout = 2000; $s.Open(); "
            f"Start-Sleep -Milliseconds 200; "
            f"if($s.BytesToRead -gt 0){{$s.ReadExisting() | Out-Null}}; "
            f"$bi = Read-AT $s 'AT BI'; "
            f"$fv = Read-AT $s 'AT FV'; "
            f"$bv = Read-AT $s 'AT BV'; "
            f"$s.Close(); "
            f"Write-Host ('BI:' + $bi + '|FV:' + $fv + '|BV:' + $bv)"
            f'"'
        )
        self.log.append_log(f"[CAN] Querying {board_name} ({port})...")
        self._pending_output[board_name] = ""
        worker = SSHWorker(pc["host"], pc["user"], pc["password"], cmd)
        worker.output.connect(
            lambda line, bn=board_name: self._collect_output(bn, line)
        )
        worker.finished_signal.connect(
            lambda s, bn=board_name: self._on_query_done(bn, s)
        )
        self._workers.append(worker)
        worker.start()

    def _on_query_done(self, board_name, status):
        output = self._pending_output.pop(board_name, "")
        if status != "0":
            self.log.append_log(f"[CAN] {board_name} query failed (exit={status})")
            self._set_status(board_name, "error")
            return

        # Parse BI:|FV:|BV: response
        parts = {}
        for segment in output.strip().split("|"):
            if ":" in segment:
                key, val = segment.split(":", 1)
                parts[key.strip()] = val.strip()

        bi = parts.get("BI", "?")
        fv = parts.get("FV", "?")
        bv = parts.get("BV", "?")
        self.log.append_log(f"[CAN] {board_name}: {bi} | {fv} | {bv}")
        self._set_status(board_name, "ok" if "OK" in bi else "warn")

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

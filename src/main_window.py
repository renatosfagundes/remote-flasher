"""Main window — CameraPanel + MainWindow with tab management."""
import sys
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QComboBox, QSplitter, QSizePolicy,
    QMessageBox,
)

from _version import __version__
from lab_config import COMPUTERS
from settings import APP_DIR
from workers import CameraWorker
from dashboard_backend import DashboardBackend
from port_lock import PortLockManager
from tabs import (
    VPNTab, FlashTab, CANTab, SerialTab, SSHTerminalTab, SetupTab,
    GaugesTab, HMIDashboardTab, PlotterTab,
)


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
            url = cfg.get("camera_url", "").strip()
            if url:
                self.url_combo.addItem(url)
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
        self.setWindowTitle(f"Remote Firmware Flasher v{__version__} — UFPE Lab")
        self.setMinimumSize(1100, 700)

        icon_path = os.path.join(getattr(sys, '_MEIPASS', APP_DIR), "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.tabs = QTabWidget()
        self.vpn_tab = VPNTab()
        self.flash_tab = FlashTab()
        self.can_tab = CANTab()
        self.serial_tab = SerialTab()
        self.ssh_tab = SSHTerminalTab()
        self.setup_tab = SetupTab()

        # Dashboard backend (shared by HMI Dashboard + Plots tabs)
        self.dashboard_backend = DashboardBackend()
        self.gauges_tab = HMIDashboardTab(self.dashboard_backend)
        self.plotter_tab = PlotterTab()
        self._dashboard_source_panel = None
        self._plotter_source_panel = None

        self.tabs.addTab(self.vpn_tab, "VPN")
        self.tabs.addTab(self.flash_tab, "Flash")
        self.tabs.addTab(self.can_tab, "CAN")
        self.tabs.addTab(self.serial_tab, "Serial")
        self.tabs.addTab(self.gauges_tab, "Dashboard")
        self.tabs.addTab(self.plotter_tab, "Plotter")
        self.tabs.addTab(self.ssh_tab, "SSH Terminal")
        self.tabs.addTab(self.setup_tab, "Setup")

        self.camera_panel = CameraPanel()
        self._camera_visible = True

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.addWidget(self.camera_panel)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([600, 400])

        self.setCentralWidget(self.main_splitter)

        # Port lock manager — polls lock files on lab PCs, enabled only when VPN is up
        self.lock_manager = PortLockManager(self)
        self.serial_tab.lock_manager = self.lock_manager
        self.lock_manager.locks_changed.connect(self._on_locks_changed)
        self.vpn_tab.vpn_status_changed.connect(self.lock_manager.set_enabled)

        self.serial_tab.panel_count_changed.connect(self._on_serial_panel_count)
        self.flash_tab.ports_synced.connect(self._on_ports_synced)

        # Plotter backend gets the dashboard bridge for auto-routing named signals
        self.plotter_tab.backend.set_dashboard_bridge(
            self.gauges_tab._bridge if hasattr(self.gauges_tab, '_bridge') else None
        )
        self._feed_panel = None  # the serial panel currently feeding dashboard/plotter
        self.serial_tab.feed_toggled.connect(self._on_feed_toggled)

        self.toggle_cam_btn = QPushButton("Hide Camera")
        self.toggle_cam_btn.setCheckable(True)
        self.toggle_cam_btn.setChecked(False)
        self.toggle_cam_btn.setStyleSheet(
            "padding: 4px 12px; font-size: 11px; border-radius: 3px;"
        )
        self.toggle_cam_btn.toggled.connect(self._on_toggle_camera)
        self.tabs.setCornerWidget(self.toggle_cam_btn, Qt.TopRightCorner)

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._on_tab_changed(self.tabs.currentIndex())


        self.statusBar().showMessage(f"v{__version__} — Ready — connect VPN first, then use Flash/Camera/Serial tabs")

        self._apply_style()

    def _on_toggle_camera(self, hidden):
        self._camera_visible = not hidden
        self.toggle_cam_btn.setText("Show Camera" if hidden else "Hide Camera")
        self._update_camera_visibility()

    def _on_tab_changed(self, index):
        self._update_camera_visibility()

    def _on_ports_synced(self):
        """Refresh board/port combos in every tab after ports.json sync.
        SSHTab reads COMPUTERS live when acting, so no refresh is needed there.
        """
        # CAN tab has a single pc_combo.
        handler = getattr(self.can_tab, "_on_pc_changed", None)
        if callable(handler):
            handler(self.can_tab.pc_combo.currentText())
        # Serial tab owns multiple panels, each with its own pc_combo.
        for panel in getattr(self.serial_tab, "panels", []):
            panel_handler = getattr(panel, "_on_pc_changed", None)
            if callable(panel_handler):
                panel_handler(panel.pc_combo.currentText())

    def _on_locks_changed(self):
        """Refresh port dropdowns when remote lock state changes."""
        for panel in getattr(self.serial_tab, "panels", []):
            if panel.serial_worker is None:  # only refresh idle panels
                panel._on_board_changed(None)

    def _on_serial_panel_count(self, count):
        if self.tabs.currentWidget() is not self.serial_tab:
            return
        if not self._camera_visible:
            return
        total = self.main_splitter.width() or 1000
        if count <= 1:
            self.main_splitter.setSizes([int(total * 0.6), int(total * 0.4)])
        else:
            self.main_splitter.setSizes([int(total * 0.75), int(total * 0.25)])

    def _update_camera_visibility(self):
        hide_camera = self.tabs.currentWidget() in (
            self.vpn_tab, self.setup_tab, self.gauges_tab, self.plotter_tab,
        )
        self.camera_panel.setVisible(not hide_camera and self._camera_visible)
        self.toggle_cam_btn.setVisible(not hide_camera)

    # ------------------------------------------------------------------
    # Dashboard source management
    # ------------------------------------------------------------------

    def _on_feed_toggled(self, panel, checked):
        """Connect/disconnect a serial panel's output to plotter + dashboard."""
        backend = self.plotter_tab.backend

        # Disconnect previous feed panel
        if self._feed_panel is not None:
            worker = getattr(self._feed_panel, "serial_worker", None)
            if worker is not None:
                try:
                    worker.output.disconnect(backend.onSerialLine)
                except RuntimeError:
                    pass
            self._feed_panel = None

        if not checked:
            return

        # Connect new feed panel
        worker = getattr(panel, "serial_worker", None)
        if worker is not None:
            worker.output.connect(backend.onSerialLine)
            self._feed_panel = panel

    def closeEvent(self, event):
        # Stop all active serial connections before closing
        for panel in self.serial_tab.panels:
            panel.cleanup()
        self.dashboard_backend.stopLogging()
        if self.vpn_tab._connected:
            msg = QMessageBox(self)
            msg.setWindowTitle("VPN Connected")
            msg.setText("The VPN is still connected. What would you like to do?")
            disconnect_btn = msg.addButton("Disconnect && Close", QMessageBox.AcceptRole)
            keep_btn = msg.addButton("Keep VPN && Close", QMessageBox.RejectRole)
            cancel_btn = msg.addButton("Cancel", QMessageBox.DestructiveRole)
            msg.setDefaultButton(cancel_btn)
            msg.exec()

            clicked = msg.clickedButton()
            if clicked == disconnect_btn:
                self.vpn_tab._disconnect_vpn()
                event.accept()
            elif clicked == keep_btn:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

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

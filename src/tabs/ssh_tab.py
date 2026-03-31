"""SSH terminal tab — command execution + SFTP file/folder upload."""
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QLineEdit, QFileDialog,
    QProgressBar,
)

from lab_config import COMPUTERS
from settings import get_remote_user_dir
from widgets import LogWidget
from workers import SSHWorker, SFTPUploadWorker


class SSHTerminalTab(QWidget):
    """Direct SSH command execution + SFTP file/folder upload."""
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

        upload_grp = QGroupBox("SFTP File/Folder Upload")
        ug = QGridLayout(upload_grp)

        ug.addWidget(QLabel("Local Path:"), 0, 0)
        local_row = QHBoxLayout()
        self.local_path_input = QLineEdit()
        self.local_path_input.setPlaceholderText("Select a file or folder to upload...")
        local_row.addWidget(self.local_path_input)
        self.browse_file_btn = QPushButton("File...")
        self.browse_file_btn.clicked.connect(self._browse_file)
        local_row.addWidget(self.browse_file_btn)
        self.browse_folder_btn = QPushButton("Folder...")
        self.browse_folder_btn.clicked.connect(self._browse_folder)
        local_row.addWidget(self.browse_folder_btn)
        ug.addLayout(local_row, 0, 1)

        ug.addWidget(QLabel("Remote Path:"), 1, 0)
        self.remote_path_input = QLineEdit(get_remote_user_dir())
        self.remote_path_input.setPlaceholderText("Remote destination folder")
        ug.addWidget(self.remote_path_input, 1, 1)

        upload_row = QHBoxLayout()
        self.upload_btn = QPushButton("Upload")
        self.upload_btn.setStyleSheet("background-color: #2d5a27; color: white; font-weight: bold;")
        self.upload_btn.clicked.connect(self._start_upload)
        upload_row.addWidget(self.upload_btn)
        self.progress_label = QLabel("")
        upload_row.addWidget(self.progress_label)
        upload_row.addStretch()
        ug.addLayout(upload_row, 2, 0, 1, 2)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #555; border-radius: 3px; text-align: center; "
            "background: #3c3c3c; color: #ddd; } "
            "QProgressBar::chunk { background: #2d5a27; }"
        )
        ug.addWidget(self.progress_bar, 3, 0, 1, 2)

        layout.addWidget(upload_grp)

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

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload", "", "All Files (*)")
        if path:
            self.local_path_input.setText(path)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder to Upload")
        if path:
            self.local_path_input.setText(path)

    def _start_upload(self):
        pc = COMPUTERS.get(self.pc_combo.currentText(), {})
        local = self.local_path_input.text().strip()
        remote = self.remote_path_input.text().strip()
        if not local or not os.path.exists(local):
            self.log.append_log("[SFTP] Please select a valid file or folder.")
            return
        if not remote:
            self.log.append_log("[SFTP] Please enter a remote destination path.")
            return
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Uploading...")
        self.upload_btn.setEnabled(False)
        worker = SFTPUploadWorker(pc["host"], pc["user"], pc["password"], local, remote)
        worker.output.connect(self.log.append_log)
        worker.progress.connect(self._on_upload_progress)
        worker.finished_signal.connect(self._on_upload_done)
        self._workers.append(worker)
        worker.start()

    def _on_upload_progress(self, transferred, total):
        if total > 0:
            pct = int(transferred * 100 / total)
            self.progress_bar.setValue(pct)
            self.progress_label.setText(f"{transferred // 1024} KB / {total // 1024} KB")

    def _on_upload_done(self, ok):
        self.progress_bar.setValue(100 if ok else 0)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Upload complete!" if ok else "Upload failed!")
        self.upload_btn.setEnabled(True)

"""
Remote Firmware Flasher — PySide6 desktop application.
Connect via VPN + SSH to flash Arduino boards in the lab and watch cameras.

Entry point — run this file to launch the application.
"""
import sys
import os

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QVBoxLayout, QLabel, QLineEdit, QDialog, QDialogButtonBox,
    QFormLayout,
)

from lab_config import REMOTE_BASE_DIR
from settings import APP_DIR, load_settings, save_settings
from main_window import MainWindow


def _show_first_run_dialog() -> bool:
    """Show a setup dialog on first run so the user can set their remote folder.
    Returns True if the user completed setup, False if they cancelled."""
    settings = load_settings()

    dlg = QDialog()
    dlg.setWindowTitle("First Run Setup")
    dlg.setMinimumWidth(420)
    layout = QVBoxLayout(dlg)

    info = QLabel(
        "Welcome! Please enter your name.\n"
        f"Your remote folder will be created at {REMOTE_BASE_DIR}\\<your_name>."
    )
    info.setWordWrap(True)
    layout.addWidget(info)

    form = QFormLayout()
    name_edit = QLineEdit(settings.get("user_name", ""))
    name_edit.setPlaceholderText("e.g. renato")
    form.addRow("Your name:", name_edit)

    folder_edit = QLineEdit(settings.get("remote_user_dir", ""))
    folder_edit.setPlaceholderText(f"e.g. {REMOTE_BASE_DIR}\\renato")
    form.addRow("Remote folder:", folder_edit)

    def _update_folder():
        name = name_edit.text().strip()
        if name and not folder_edit.isModified():
            folder_edit.setText(f"{REMOTE_BASE_DIR}\\{name}")
    name_edit.textChanged.connect(_update_folder)

    layout.addLayout(form)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)

    if dlg.exec() != QDialog.Accepted:
        return False

    name = name_edit.text().strip()
    folder = folder_edit.text().strip()
    if not name or not folder:
        return False

    save_settings(user_name=name, remote_user_dir=folder)
    return True


def main():
    # Windows taskbar icon fix — must be set before QApplication
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ufpe.remote_flasher")

    app = QApplication(sys.argv)
    app.setApplicationName("Remote Firmware Flasher")

    icon_path = os.path.join(getattr(sys, '_MEIPASS', APP_DIR), "assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Show first-run setup if no remote folder is configured
    settings = load_settings()
    if not settings.get("remote_user_dir"):
        if not _show_first_run_dialog():
            sys.exit(0)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

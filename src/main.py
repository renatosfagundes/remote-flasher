"""
Remote Firmware Flasher — PySide6 desktop application.
Connect via VPN + SSH to flash Arduino boards in the lab and watch cameras.

Entry point — run this file to launch the application.
"""
from _version import __version__

import sys
import os
import logging
import traceback
import faulthandler

# Enable Python fault handler — dumps a traceback on native crashes
# (segfaults, aborts) to stderr instead of vanishing silently.
# Guard against --windowed builds where stderr is None.
if sys.stderr is not None:
    faulthandler.enable()


def _excepthook(exc_type, exc_value, exc_tb):
    """Log any uncaught Python exception instead of letting it close the
    app silently. Keeps the original message visible in the console."""
    print("\n" + "=" * 60, file=sys.stderr)
    print("UNCAUGHT EXCEPTION — app may have misbehaved:", file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_tb, file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)


def _thread_excepthook(args):
    """QThread/paramiko/threading exceptions don't hit sys.excepthook —
    they go here. Log them so threading bugs don't silently kill the app."""
    print("\n" + "=" * 60, file=sys.stderr)
    print(f"THREAD EXCEPTION in {args.thread.name!r}:", file=sys.stderr)
    traceback.print_exception(
        args.exc_type, args.exc_value, args.exc_traceback, file=sys.stderr
    )
    print("=" * 60 + "\n", file=sys.stderr)


sys.excepthook = _excepthook
import threading
threading.excepthook = _thread_excepthook

# Suppress noisy socket/urllib3 warnings on console
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("requests").setLevel(logging.CRITICAL)

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

    # Minimal app-wide styling: force readable text in the two spots where
    # Qt's default palette mis-contrasts against our widgets.
    #   - QCheckBox labels sit on dark panels and need light text.
    #   - QMessageBox body text on a white background was rendering as a
    #     dim goldenrod (system palette quirk), too washed-out to read.
    app.setStyleSheet("""
        QCheckBox { color: #ddd; }
        QMessageBox { color: #202020; }
        QMessageBox QLabel { color: #202020; }
    """)

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

"""Environment setup tab — status checks, install, and IDE integration guides."""
import sys
import os
import re
import shutil
import subprocess

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QTabWidget, QSplitter, QTextBrowser,
)

from settings import APP_DIR
from widgets import LogWidget, make_log_with_clear

# Paths matching setup_environment.py
_ESA_DIR = r"C:\ESA"
_ARDUINO_CLI_DIR = os.path.join(_ESA_DIR, "arduino_cli", "bin")
_AVR_TOOLS_DIR = os.path.join(_ESA_DIR, "avr_tools")
_AVR_TOOLCHAIN_DIR = os.path.join(_AVR_TOOLS_DIR, "avr8-gnu-toolchain-win32_x86")
_AVR_BIN_DIR = os.path.join(_AVR_TOOLCHAIN_DIR, "bin")
_TRAMPOLINE_DIR = os.path.join(_ESA_DIR, "trampoline")


def _dir_in_user_path(directory):
    """Check if a directory is in the user's Windows PATH (reads registry)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ)
        current_path, _ = winreg.QueryValueEx(key, "Path")
        winreg.CloseKey(key)
        entries = [e.strip().lower() for e in current_path.split(";") if e.strip()]
        return directory.lower() in entries
    except Exception:
        return False


def _check_component(name):
    """Return True/False for a named environment component."""
    checks = {
        "Git": lambda: shutil.which("git") is not None,
        "Arduino CLI": lambda: os.path.isfile(os.path.join(_ARDUINO_CLI_DIR, "arduino-cli.exe")),
        "Arduino CLI in PATH": lambda: _dir_in_user_path(_ARDUINO_CLI_DIR),
        "AVR Toolchain": lambda: os.path.isfile(os.path.join(_AVR_BIN_DIR, "avr-gcc.exe")),
        "AVR tools in PATH": lambda: _dir_in_user_path(_AVR_BIN_DIR),
        "goil compiler": lambda: os.path.isfile(os.path.join(_AVR_BIN_DIR, "goil.exe")),
        "Trampoline RTOS": lambda: os.path.isdir(os.path.join(_TRAMPOLINE_DIR, ".git")),
        "Arduino submodule": lambda: os.path.isdir(
            os.path.join(_TRAMPOLINE_DIR, "machines", "avr", "arduino", "cores")
        ),
        "Nano template": lambda: os.path.isdir(
            os.path.join(_TRAMPOLINE_DIR, "goil", "templates", "config", "avr", "arduino", "nano")
        ),
        "MCP_CAN (Trampoline)": lambda: os.path.isdir(
            os.path.join(_TRAMPOLINE_DIR, "machines", "avr", "arduino", "libraries", "mcp_can", "src")
        ),
        "Nano examples": lambda: os.path.isdir(
            os.path.join(_TRAMPOLINE_DIR, "examples", "avr", "arduinoNano")
        ),
    }
    try:
        return checks.get(name, lambda: False)()
    except Exception:
        return False


COMPONENTS = [
    "Git", "Arduino CLI", "Arduino CLI in PATH",
    "AVR Toolchain", "AVR tools in PATH", "goil compiler",
    "Trampoline RTOS", "Arduino submodule",
    "Nano template", "MCP_CAN (Trampoline)", "Nano examples",
]


class SetupCheckWorker(QThread):
    """Run environment checks in background."""
    result = Signal(str, bool)
    finished_signal = Signal()

    def run(self):
        for name in COMPONENTS:
            ok = _check_component(name)
            self.result.emit(name, ok)
        self.finished_signal.emit()


class SetupInstallWorker(QThread):
    """Run setup_environment.py in a subprocess."""
    output = Signal(str)
    finished_signal = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

    def _find_script(self):
        """Locate setup_environment.py — works both from source and from frozen exe."""
        candidates = [
            # Running from source: src/tabs/ -> src/ -> remote_flasher/ -> RTOS/
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "..", "setup_environment.py"),
            # Bundled inside PyInstaller exe
            os.path.join(getattr(sys, '_MEIPASS', ''), "setup_environment.py"),
            # Next to the exe
            os.path.join(os.path.dirname(sys.executable), "setup_environment.py"),
            # Two levels up from exe (dist/ -> remote_flasher/ -> RTOS/)
            os.path.join(os.path.dirname(sys.executable), "..", "..", "setup_environment.py"),
        ]
        for path in candidates:
            path = os.path.normpath(path)
            if os.path.isfile(path):
                return path
        return None

    def run(self):
        script = self._find_script()
        if not script:
            self.output.emit("[ERROR] setup_environment.py not found!")
            self.output.emit("  Searched in multiple locations relative to the executable and source.")
            self.finished_signal.emit(1)
            return
        try:
            # In a frozen exe, sys.executable is the exe itself — need a real Python
            if getattr(sys, 'frozen', False):
                import shutil as _shutil
                import glob as _glob
                python = _shutil.which("python") or _shutil.which("python3") or _shutil.which("py")
                if not python:
                    # Search common install locations
                    for pattern in [
                        r"C:\Users\*\AppData\Local\Programs\Python\Python3*\python.exe",
                        r"C:\Python3*\python.exe",
                        r"C:\Program Files\Python3*\python.exe",
                    ]:
                        found = sorted(_glob.glob(pattern), reverse=True)
                        if found:
                            python = found[0]
                            break
                if not python:
                    self.output.emit("[ERROR] Python not found on this computer!")
                    self.output.emit("")
                    self.output.emit("The environment setup requires Python 3 to be installed.")
                    self.output.emit("Please download and install it from:")
                    self.output.emit("")
                    self.output.emit("  https://www.python.org/downloads/")
                    self.output.emit("")
                    self.output.emit("IMPORTANT: During installation, check the box:")
                    self.output.emit('  [x] "Add Python to PATH"')
                    self.output.emit("")
                    self.output.emit("After installing Python, restart Remote Flasher and try again.")
                    self.finished_signal.emit(1)
                    return
            else:
                python = sys.executable
            proc = subprocess.Popen(
                [python, "-u", script],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            for line in proc.stdout:
                cleaned = re.sub(r'\x1b\[[0-9;]*m', '', line.rstrip())
                if cleaned:
                    self.output.emit(cleaned)
            proc.wait()
            self.finished_signal.emit(proc.returncode)
        except Exception as e:
            self.output.emit(f"[ERROR] {e}")
            self.finished_signal.emit(1)


# ---------------------------------------------------------------------------
# IDE Guide HTML content
# ---------------------------------------------------------------------------

_NOTEPADPP_GUIDE = """\
<h3>Notepad++ Integration</h3>

<h4>1. Install Plugins</h4>
<p>Open Notepad++ and install via <b>Plugins &rarr; Plugins Admin</b>:</p>
<ul>
  <li><b>NppExec</b> &mdash; run commands from within Notepad++</li>
  <li><b>SourceCookifier</b> &mdash; code navigation</li>
</ul>
<p>Also install <b>NppConsole</b> manually from
<a href="https://sourceforge.net/projects/nppconsole/">sourceforge.net/projects/nppconsole</a>.
Extract <code>NppConsole.dll</code> into
<code>Plugins\\NppConsole\\</code> inside your Notepad++ install folder.</p>

<h4>2. Configure NppExec Highlight Filters</h4>
<p><b>Plugins &rarr; NppExec &rarr; Console Output Filters &rarr; Highlights tab</b></p>
<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
<tr><th>#</th><th>Mask</th><th>Color</th><th>Style</th></tr>
<tr><td>1</td><td><code>%FILE%:%LINE%:*: error:*</code></td><td>Red</td><td>Bold</td></tr>
<tr><td>2</td><td><code>%FILE%:%LINE%:*: warning:*</code></td><td>&mdash;</td><td>Italic</td></tr>
<tr><td>3</td><td><code>%FILE%(%LINE%,*):*: error*</code></td><td>&mdash;</td><td>Bold</td></tr>
<tr><td>4</td><td><code>%FILE%(%LINE%): warning*</code></td><td>&mdash;</td><td>Italic</td></tr>
<tr><td>5</td><td><code>%FILE%:%LINE%:*: note:*</code></td><td>Blue</td><td>Underline</td></tr>
<tr><td>6</td><td><code>*at%FILE%:%LINE%</code></td><td>&mdash;</td><td>Italic</td></tr>
<tr><td>7</td><td><code>%FILE%:%LINE%: error:*</code></td><td>&mdash;</td><td>Italic</td></tr>
</table>

<h4>3. Create NppExec Scripts</h4>
<p>Save these files in <code>C:\\Program Files (x86)\\Notepad++\\plugins\\NppExec\\scripts\\</code>:</p>

<p><b>arduino_boards.scp</b></p>
<pre>
cd $(CURRENT_DIRECTORY)
cls
arduino-cli board list
</pre>

<p><b>arduino_compile.scp</b></p>
<pre>
NPP_SAVEALL
cd $(CURRENT_DIRECTORY)
INPUTBOX "Select the board:":"Board": "$(board)"
set board = $(INPUT)
if "$(board)" == "nano_old" then
  set FQBN = arduino:avr:nano:cpu=atmega328old
else if "$(board)" == "nano" then
  set FQBN = arduino:avr:nano
else if "$(board)" == "uno" then
  set FQBN = arduino:avr:uno
endif
arduino-cli compile -b $(FQBN) -v -e $(FILE_NAME)
</pre>

<p><b>arduino_upload.scp</b></p>
<pre>
cd $(CURRENT_DIRECTORY)
INPUTBOX "Select serial port:":"CommPort": "COM3"
set local commport = $(INPUT)
arduino-cli upload -b $(FQBN) -p $(commport) -v \\
  -i build/$(BUILD_DIR)/$(FILE_NAME).hex -t
</pre>

<p><b>Trampoline scripts</b> &mdash; trampoline_goil.scp, trampoline_make.scp,
trampoline_make_clean.scp, trampoline_upload.scp (see apostila.pdf Section 4.5)</p>

<h4>4. Create Macro Menu Items</h4>
<p><b>Plugins &rarr; NppExec &rarr; Advanced Options</b></p>
<p>Associate each script with a menu item name. Then access them from
<b>Macro</b> menu.</p>
"""

_VSCODE_GUIDE = """\
<h3>VSCode Integration</h3>

<h4>1. Install Extensions</h4>
<ul>
  <li><b>C/C++</b> (Microsoft) &mdash; IntelliSense, debugging</li>
  <li><b>Arduino</b> (Microsoft) &mdash; board manager, compile, upload</li>
</ul>

<h4>2. Configure IntelliSense for AVR</h4>
<p>Create <code>.vscode/c_cpp_properties.json</code> in your project:</p>
<pre>
{
  "configurations": [{
    "name": "AVR",
    "includePath": [
      "${workspaceFolder}/**",
      "C:/ESA/avr_tools/avr8-gnu-toolchain-win32_x86/avr/include",
      "C:/ESA/trampoline/os",
      "C:/ESA/trampoline/machines/avr/arduino/cores/arduino",
      "C:/ESA/trampoline/machines/avr/arduino/libraries/mcp_can/src"
    ],
    "defines": [
      "F_CPU=16000000",
      "__AVR_ATmega328P__",
      "ARDUINO=10813"
    ],
    "compilerPath": "C:/ESA/avr_tools/avr8-gnu-toolchain-win32_x86/bin/avr-gcc.exe",
    "cStandard": "c11",
    "cppStandard": "c++14",
    "intelliSenseMode": "gcc-x86"
  }],
  "version": 4
}
</pre>

<h4>3. Build Tasks (tasks.json)</h4>
<p>Create <code>.vscode/tasks.json</code> for compile, upload, and Trampoline workflows:</p>
<pre>
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Arduino: Compile (Uno)",
      "type": "shell",
      "command": "arduino-cli compile -b arduino:avr:uno -v -e .",
      "group": "build",
      "problemMatcher": ["$gcc"]
    },
    {
      "label": "Arduino: Compile (Nano)",
      "type": "shell",
      "command": "arduino-cli compile -b arduino:avr:nano -v -e .",
      "group": "build",
      "problemMatcher": ["$gcc"]
    },
    {
      "label": "Arduino: Upload",
      "type": "shell",
      "command": "arduino-cli upload -b arduino:avr:uno -p ${input:comPort} -v -t",
      "problemMatcher": []
    },
    {
      "label": "Arduino: List Boards",
      "type": "shell",
      "command": "arduino-cli board list",
      "problemMatcher": []
    },
    {
      "label": "Trampoline: Run goil (Nano)",
      "type": "shell",
      "command": "goil --target=avr/arduino/nano --templates=${input:trampolineBase}/goil/templates/ ${fileBasename}",
      "options": { "cwd": "${fileDirname}" },
      "problemMatcher": []
    },
    {
      "label": "Trampoline: make.py",
      "type": "shell",
      "command": "python make.py",
      "options": { "cwd": "${fileDirname}" },
      "group": "build",
      "problemMatcher": ["$gcc"]
    },
    {
      "label": "Trampoline: make clean",
      "type": "shell",
      "command": "python make.py clean",
      "options": { "cwd": "${fileDirname}" },
      "problemMatcher": []
    },
    {
      "label": "Trampoline: Upload hex",
      "type": "shell",
      "command": "arduino-cli upload -b arduino:avr:nano -p ${input:comPort} -v -i image.hex -t",
      "options": { "cwd": "${fileDirname}" },
      "problemMatcher": []
    }
  ],
  "inputs": [
    {
      "id": "comPort",
      "description": "Serial COM port (e.g. COM3)",
      "default": "COM3",
      "type": "promptString"
    },
    {
      "id": "trampolineBase",
      "description": "Trampoline base path (relative)",
      "default": "../../../..",
      "type": "promptString"
    }
  ]
}
</pre>

<h4>4. Recommended Settings (settings.json)</h4>
<pre>
{
  "files.associations": {
    "*.oil": "c",
    "*.ino": "cpp"
  },
  "C_Cpp.errorSquiggles": "enabled",
  "terminal.integrated.defaultProfile.windows": "Git Bash"
}
</pre>

<h4>5. Workflow</h4>
<ol>
  <li>Open the project folder in VSCode</li>
  <li><b>Ctrl+Shift+B</b> to run build tasks</li>
  <li><b>Ctrl+Shift+P</b> &rarr; "Tasks: Run Task" for upload, goil, etc.</li>
  <li>Use the integrated terminal for arduino-cli commands</li>
</ol>
"""


class SetupTab(QWidget):
    """Environment setup: status checks, install, and IDE integration guides."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers = []
        layout = QVBoxLayout(self)

        status_grp = QGroupBox("Environment Status")
        status_layout = QVBoxLayout(status_grp)

        self._status_grid = QGridLayout()
        self._status_grid.setSpacing(4)

        self._status_labels = {}
        for i, name in enumerate(COMPONENTS):
            row, col_offset = divmod(i, 3)
            indicator = QLabel()
            indicator.setFixedSize(14, 14)
            indicator.setStyleSheet(
                "background-color: #888; border-radius: 7px; border: 1px solid #555;"
            )
            label = QLabel(name)
            self._status_grid.addWidget(indicator, row, col_offset * 3)
            self._status_grid.addWidget(label, row, col_offset * 3 + 1)
            if col_offset < 2:
                spacer = QLabel("  ")
                self._status_grid.addWidget(spacer, row, col_offset * 3 + 2)
            self._status_labels[name] = indicator

        status_layout.addLayout(self._status_grid)

        btn_row = QHBoxLayout()
        self.check_btn = QPushButton("Check Environment")
        self.check_btn.clicked.connect(self._run_check)
        btn_row.addWidget(self.check_btn)

        self.install_btn = QPushButton("Run Full Setup")
        self.install_btn.setStyleSheet("background-color: #2d5a27; color: white; font-weight: bold;")
        self.install_btn.setToolTip("Run setup_environment.py to install all missing components")
        self.install_btn.clicked.connect(self._run_install)
        btn_row.addWidget(self.install_btn)
        btn_row.addStretch()
        status_layout.addLayout(btn_row)

        layout.addWidget(status_grp)

        splitter = QSplitter(Qt.Horizontal)

        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_label = QLabel("Setup Log")
        log_label.setStyleSheet("font-weight: bold;")
        log_layout.addWidget(log_label)
        self.log = make_log_with_clear(log_layout)
        splitter.addWidget(log_widget)

        guide_widget = QWidget()
        guide_layout = QVBoxLayout(guide_widget)
        guide_layout.setContentsMargins(0, 0, 0, 0)
        guide_label = QLabel("IDE Integration Guides")
        guide_label.setStyleSheet("font-weight: bold;")
        guide_layout.addWidget(guide_label)

        self.guide_tabs = QTabWidget()
        npp_browser = QTextBrowser()
        npp_browser.setOpenExternalLinks(True)
        npp_browser.setHtml(_NOTEPADPP_GUIDE)
        npp_browser.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #3c3c3c;"
        )
        self.guide_tabs.addTab(npp_browser, "Notepad++")

        vscode_browser = QTextBrowser()
        vscode_browser.setOpenExternalLinks(True)
        vscode_browser.setHtml(_VSCODE_GUIDE)
        vscode_browser.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #3c3c3c;"
        )
        self.guide_tabs.addTab(vscode_browser, "VSCode")

        guide_layout.addWidget(self.guide_tabs)
        splitter.addWidget(guide_widget)

        splitter.setSizes([400, 600])
        layout.addWidget(splitter, stretch=1)

        QTimer.singleShot(500, self._run_check)

    def _set_indicator(self, name, ok):
        indicator = self._status_labels.get(name)
        if indicator:
            color = "#44ff44" if ok else "#ff4444"
            indicator.setStyleSheet(
                f"background-color: {color}; border-radius: 7px; border: 1px solid #555;"
            )

    def _reset_indicators(self):
        for name in COMPONENTS:
            indicator = self._status_labels.get(name)
            if indicator:
                indicator.setStyleSheet(
                    "background-color: #888; border-radius: 7px; border: 1px solid #555;"
                )

    def _run_check(self):
        self._reset_indicators()
        self.check_btn.setEnabled(False)
        worker = SetupCheckWorker()
        worker.result.connect(self._set_indicator)
        worker.finished_signal.connect(lambda: self.check_btn.setEnabled(True))
        self._workers.append(worker)
        worker.start()

    def _run_install(self):
        self.install_btn.setEnabled(False)
        self.log.clear()
        self.log.append_log("Starting environment setup...")
        worker = SetupInstallWorker()
        worker.output.connect(self.log.append_log)
        worker.finished_signal.connect(self._on_install_done)
        self._workers.append(worker)
        worker.start()

    def _on_install_done(self, exit_code):
        self.install_btn.setEnabled(True)
        if exit_code == 0:
            self.log.append_log("[DONE] Setup completed successfully!")
        else:
            self.log.append_log(f"[DONE] Setup finished with exit code {exit_code}")
        self._run_check()

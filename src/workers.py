"""
Background worker threads — SSH, SCP, SFTP, Camera, Serial.
"""
import sys
import os
import re
import time

import paramiko
import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from lab_config import REMOTE_BASE_DIR


class SSHWorker(QThread):
    """Run a command over SSH in a background thread."""
    output = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, host, user, password, command, parent=None):
        super().__init__(parent)
        self.host = host
        self.user = user
        self.password = password
        self.command = command
        self._stop = False

    def run(self):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.output.emit(f"[SSH] Connecting to {self.host}...")
            client.connect(
                self.host, username=self.user, password=self.password, timeout=15
            )
            self.output.emit(f"[SSH] Running: {self.command}")
            stdin, stdout, stderr = client.exec_command(self.command, timeout=120)
            raw_out = stdout.read()
            raw_err = stderr.read()
            for raw in (raw_out, raw_err):
                is_err = raw is raw_err
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw.decode("cp850", errors="replace")
                for line in text.splitlines():
                    if self._stop:
                        break
                    self.output.emit(f"[STDERR] {line}" if is_err else line)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status > 0x7FFFFFFF:
                exit_status = exit_status - 0x100000000
            client.close()
            self.finished_signal.emit(str(exit_status))
        except Exception as e:
            self.output.emit(f"[ERROR] {e}")
            self.finished_signal.emit("-1")

    def stop(self):
        self._stop = True


class SCPWorker(QThread):
    """Upload a file via SFTP (SCP) in a background thread."""
    output = Signal(str)
    finished_signal = Signal(bool)

    def __init__(self, host, user, password, local_path, remote_path, parent=None):
        super().__init__(parent)
        self.host = host
        self.user = user
        self.password = password
        self.local_path = local_path
        self.remote_path = remote_path

    def run(self):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.output.emit(f"[SCP] Connecting to {self.host}...")
            client.connect(
                self.host, username=self.user, password=self.password, timeout=15
            )
            sftp = client.open_sftp()
            try:
                sftp.stat(self.remote_path)
            except FileNotFoundError:
                self.output.emit(f"[SCP] Creating remote folder: {self.remote_path}")
                sftp.mkdir(self.remote_path)
            filename = os.path.basename(self.local_path)
            remote_file = f"{self.remote_path}/{filename}"
            self.output.emit(f"[SCP] Uploading {filename} -> {remote_file}")
            sftp.put(self.local_path, remote_file)
            sftp.close()
            client.close()
            self.output.emit(f"[SCP] Upload complete: {remote_file}")
            self.finished_signal.emit(True)
        except Exception as e:
            self.output.emit(f"[SCP ERROR] {e}")
            self.finished_signal.emit(False)


class SFTPUploadWorker(QThread):
    """Upload files or entire folders via SFTP with progress reporting."""
    output = Signal(str)
    progress = Signal(int, int)
    finished_signal = Signal(bool)

    def __init__(self, host, user, password, local_path, remote_path, parent=None):
        super().__init__(parent)
        self.host = host
        self.user = user
        self.password = password
        self.local_path = local_path
        self.remote_path = remote_path
        self._total_bytes = 0
        self._transferred = 0

    def _get_total_size(self, path):
        if os.path.isfile(path):
            return os.path.getsize(path)
        total = 0
        for dirpath, _dirnames, filenames in os.walk(path):
            for f in filenames:
                total += os.path.getsize(os.path.join(dirpath, f))
        return total

    def _sftp_mkdir_p(self, sftp, remote_dir):
        remote_dir = remote_dir.replace("\\", "/")
        dirs_to_create = []
        current = remote_dir
        while current and current not in ("/", ""):
            try:
                sftp.stat(current)
                break
            except FileNotFoundError:
                dirs_to_create.append(current)
                parent = current.rsplit("/", 1)[0] if "/" in current else ""
                if parent == current:
                    break
                current = parent
        for d in reversed(dirs_to_create):
            try:
                sftp.mkdir(d)
            except IOError:
                pass

    def _progress_cb(self, transferred, total):
        self._transferred += transferred - getattr(self, '_last_file_transferred', 0)
        self._last_file_transferred = transferred
        self.progress.emit(self._transferred, self._total_bytes)

    def _upload_dir(self, sftp, local_dir, remote_dir):
        remote_dir = remote_dir.replace("\\", "/")
        self._sftp_mkdir_p(sftp, remote_dir)
        for entry in os.scandir(local_dir):
            local_path = entry.path
            remote_path = remote_dir + "/" + entry.name
            if entry.is_dir():
                self._upload_dir(sftp, local_path, remote_path)
            else:
                self.output.emit(f"[SFTP] Uploading: {entry.name}")
                self._last_file_transferred = 0
                sftp.put(local_path, remote_path, callback=self._progress_cb)

    def run(self):
        try:
            self._total_bytes = self._get_total_size(self.local_path)
            self._transferred = 0
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.output.emit(f"[SFTP] Connecting to {self.host}...")
            client.connect(
                self.host, username=self.user, password=self.password, timeout=15
            )
            sftp = client.open_sftp()
            remote = self.remote_path.replace("\\", "/")
            if os.path.isfile(self.local_path):
                self._sftp_mkdir_p(sftp, remote)
                filename = os.path.basename(self.local_path)
                remote_file = remote + "/" + filename
                self.output.emit(f"[SFTP] Uploading: {filename}")
                self._last_file_transferred = 0
                sftp.put(self.local_path, remote_file, callback=self._progress_cb)
            elif os.path.isdir(self.local_path):
                dir_name = os.path.basename(self.local_path)
                remote_target = remote + "/" + dir_name
                self.output.emit(f"[SFTP] Uploading folder: {self.local_path} -> {remote_target}")
                self._upload_dir(sftp, self.local_path, remote_target)
            sftp.close()
            client.close()
            self.output.emit("[SFTP] Upload complete!")
            self.finished_signal.emit(True)
        except Exception as e:
            self.output.emit(f"[SFTP ERROR] {e}")
            self.finished_signal.emit(False)


class CameraWorker(QThread):
    """Fetch MJPEG frames from a camera URL."""
    frame_ready = Signal(QImage)
    error = Signal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self._running = True

    def run(self):
        try:
            resp = requests.get(self.url, stream=True, timeout=10)
            buf = b""
            for chunk in resp.iter_content(chunk_size=4096):
                if not self._running:
                    break
                buf += chunk
                start = buf.find(b"\xff\xd8")
                end = buf.find(b"\xff\xd9")
                if start != -1 and end != -1 and end > start:
                    jpg = buf[start : end + 2]
                    buf = buf[end + 2 :]
                    img = QImage()
                    img.loadFromData(jpg)
                    if not img.isNull():
                        self.frame_ready.emit(img)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._running = False


class SerialWorker(QThread):
    """Open a remote serial terminal via SSH and stream output."""
    output = Signal(str)
    finished_signal = Signal()

    def __init__(self, host, user, password, com_port, baudrate, remote_dir, parent=None):
        super().__init__(parent)
        self.host = host
        self.user = user
        self.password = password
        self.com_port = com_port
        self.baudrate = baudrate
        self.remote_dir = remote_dir
        self._running = True
        self._client = None
        self._channel = None

    _ANSI_RE = re.compile(
        r'\x1b\[[0-9;]*[A-Za-z]'
        r'|\x1b\][^\x07]*\x07'
        r'|\x1b\][\x20-\x7e]*'
        r'|\x1b[()][0-9A-Za-z]'
        r'|\x1b\[\?[0-9;]*[A-Za-z]'
    )

    def _clean(self, text: str) -> str:
        return self._ANSI_RE.sub("", text)

    def run(self):
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.output.emit(f"[Serial] Connecting to {self.host}...")
            self._client.connect(
                self.host,
                username=self.user,
                password=self.password,
                timeout=15,
            )
            # Use full path to run serialterm.py — avoids cd issues over SSH.
            # The "if not exist" must be wrapped in cmd /c to prevent it from
            # swallowing subsequent commands when the file already exists.
            remote_script = f"{self.remote_dir}\\serialterm.py"
            cmd = (
                f"cmd /c \"if not exist {remote_script}"
                f" (mkdir {self.remote_dir} >nul 2>&1"
                f" ^& copy {REMOTE_BASE_DIR}\\serialterm.py {remote_script} >nul 2>&1)\""
                f" & python -u {remote_script} --port {self.com_port} --baudrate {self.baudrate}"
            )
            self.output.emit(f"[Serial] Running: {cmd}")
            self._channel = self._client.get_transport().open_session()
            # No PTY — use python -u for unbuffered output instead.
            # PTY echoes back stdin which corrupts VirtualIO commands.
            self._channel.exec_command(cmd)
            while self._running:
                if self._channel.recv_ready():
                    data = self._channel.recv(4096).decode("utf-8", errors="replace")
                    cleaned = self._clean(data)
                    for line in cleaned.splitlines():
                        line = line.strip()
                        if line:
                            self.output.emit(line)
                elif self._channel.recv_stderr_ready():
                    data = self._channel.recv_stderr(4096).decode("utf-8", errors="replace")
                    cleaned = self._clean(data)
                    for line in cleaned.splitlines():
                        line = line.strip()
                        if line:
                            self.output.emit(f"[STDERR] {line}")
                elif self._channel.exit_status_ready():
                    while self._channel.recv_ready():
                        data = self._channel.recv(4096).decode("utf-8", errors="replace")
                        cleaned = self._clean(data)
                        for line in cleaned.splitlines():
                            line = line.strip()
                            if line:
                                self.output.emit(line)
                    exit_code = self._channel.recv_exit_status()
                    self.output.emit(f"[Serial] Process exited with code {exit_code}")
                    break
                else:
                    time.sleep(0.05)
            self._client.close()
        except Exception as e:
            self.output.emit(f"[Serial ERROR] {e}")
        self.finished_signal.emit()

    def send_data(self, text: str):
        """Send text to the remote serial terminal's stdin."""
        if self._channel and not self._channel.closed:
            try:
                self._channel.sendall((text + "\n").encode("utf-8"))
            except Exception:
                pass

    def stop(self):
        self._running = False
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass

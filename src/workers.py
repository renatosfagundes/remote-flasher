"""
Background worker threads — SSH, SCP, SFTP, Camera, Serial.
"""
import sys
import os
import re
import time
import json
import io

import paramiko
import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from lab_config import REMOTE_BASE_DIR


_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[a-zA-Z@`~]"       # CSI sequences (cursor, color, erase)
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC sequences (title, icon)
    r"|\x1b[()#][0-9A-Za-z]"            # charset designators
    r"|\x1b[=>78]"                       # keypad mode, save/restore cursor
    r"|\x07"                              # stray BEL
)

_EXIT_SENTINEL = "__RF_EXIT__="


class SSHWorker(QThread):
    """Run a command over SSH in a background thread."""
    output = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, host, user, password, command, parent=None, timeout=120, use_pty=False):
        super().__init__(parent)
        self.host = host
        self.user = user
        self.password = password
        self.timeout = timeout
        # Request a PTY so child processes (avrdude, python) detect a TTY and
        # use line-buffered stdout instead of fully-buffered. Without this,
        # long-running commands appear to hang and dump all output at the end.
        self.use_pty = use_pty
        if use_pty:
            # Windows OpenSSH doesn't reliably propagate child exit codes
            # through a PTY, so wrap the command in `cmd /v:on /c` (delayed
            # expansion) and echo a sentinel with !ERRORLEVEL! so we can
            # parse the real exit status from stdout. `call echo %%X%%`
            # alone doesn't work here — cmd expands %ERRORLEVEL% to %0% in
            # that context; delayed expansion with !ERRORLEVEL! does.
            self.command = (
                f'cmd /v:on /c "{command} & echo {_EXIT_SENTINEL}!ERRORLEVEL!"'
            )
        else:
            self.command = command
        self._captured_exit = None
        self._sentinel_seen = False
        self._stop = False

    def _decode(self, raw):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("cp850", errors="replace")

    def _emit_lines(self, buf, prefix=""):
        """Emit complete lines from buffer, return leftover (incomplete line).

        Splits on both \\n and \\r so progress bars that overwrite via carriage
        return (avrdude's Writing/Reading bars) produce incremental log lines
        instead of one blob at the end. Also strips ANSI escape sequences
        that leak through when a PTY is allocated on Windows, and intercepts
        the exit-code sentinel we append when use_pty=True.
        """
        text = self._decode(buf).replace("\r\n", "\n")
        text = _ANSI_RE.sub("", text)
        parts = re.split(r"[\n\r]", text)
        leftover = parts.pop()  # trailing incomplete fragment
        for line in parts:
            if self._stop:
                return b""
            # Intercept sentinel: capture real exit code and suppress the line.
            # Track sentinel-seen separately from the parsed int so a broken
            # !ERRORLEVEL! expansion (rare on old cmd.exe) still lets us bail
            # out of the recv loop instead of waiting for the 15s timeout.
            if _EXIT_SENTINEL in line:
                self._sentinel_seen = True
                tail = line.split(_EXIT_SENTINEL, 1)[1].strip()
                try:
                    self._captured_exit = int(tail)
                except ValueError:
                    self._captured_exit = 1  # unknown — assume failure
                continue
            if line == "":
                continue
            self.output.emit(f"{prefix}{line}" if prefix else line)
        return leftover.encode("utf-8", errors="replace")

    def run(self):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.output.emit(f"[SSH] Connecting to {self.host}...")
            client.connect(
                self.host, username=self.user, password=self.password, timeout=15
            )
            self.output.emit(f"[SSH] Running: {self.command}")
            # When use_pty=True, stderr is merged into stdout — child processes
            # detect a TTY and stream output line-by-line instead of buffering.
            stdin, stdout, stderr = client.exec_command(
                self.command, timeout=self.timeout, get_pty=self.use_pty
            )
            channel = stdout.channel

            out_buf = b""
            err_buf = b""
            t_start = time.time()

            while not channel.exit_status_ready() or channel.recv_ready() or channel.recv_stderr_ready():
                if self._stop:
                    break
                # Sentinel short-circuit: once we saw __RF_EXIT__, the command
                # has finished. Windows OpenSSH + PTY can take tens of seconds
                # to flip exit_status_ready() True — no reason to wait.
                if self.use_pty and self._sentinel_seen \
                        and not channel.recv_ready() and not channel.recv_stderr_ready():
                    break
                # Hard timeout — if the remote process hangs (e.g. avrdude
                # stuck on a COM port), don't wait forever.
                if time.time() - t_start > self.timeout:
                    self.output.emit(
                        f"[SSH] Timed out after {self.timeout}s — remote process may be stuck. "
                        "Check if the COM port is available."
                    )
                    try:
                        channel.close()
                    except Exception:
                        pass
                    break
                if channel.recv_ready():
                    out_buf += channel.recv(4096)
                    out_buf = self._emit_lines(out_buf)
                    t_start = time.time()  # reset on activity
                if channel.recv_stderr_ready():
                    err_buf += channel.recv_stderr(4096)
                    err_buf = self._emit_lines(err_buf, prefix="")
                    t_start = time.time()  # reset on activity
                if not channel.recv_ready() and not channel.recv_stderr_ready():
                    time.sleep(0.1)

            # Flush remaining data
            while channel.recv_ready():
                out_buf += channel.recv(4096)
            while channel.recv_stderr_ready():
                err_buf += channel.recv_stderr(4096)
            if out_buf:
                self._emit_lines(out_buf + b"\n")
            if err_buf:
                self._emit_lines(err_buf + b"\n")

            # Prefer the sentinel we echoed to cmd's output — Windows OpenSSH
            # + PTY gives unreliable channel exit codes AND recv_exit_status
            # can block indefinitely if the channel never flipped ready.
            if self.use_pty and self._captured_exit is not None:
                exit_status = self._captured_exit
            elif self._stop:
                exit_status = -2  # cancelled by user
            else:
                exit_status = channel.recv_exit_status()
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


class PortsFetchWorker(QThread):
    """Download ports.json from a remote PC via SFTP and parse it."""
    output = Signal(str)
    # Emits (ok: bool, data: dict). When ok is False, data is empty.
    finished_signal = Signal(bool, dict)

    def __init__(self, host, user, password, remote_path, parent=None):
        super().__init__(parent)
        self.host = host
        self.user = user
        self.password = password
        self.remote_path = remote_path.replace("\\", "/")

    def run(self):
        client = None
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.output.emit(f"[Ports] Connecting to {self.host}...")
            client.connect(
                self.host, username=self.user, password=self.password, timeout=15
            )
            sftp = client.open_sftp()
            self.output.emit(f"[Ports] Fetching {self.remote_path}")
            buf = io.BytesIO()
            sftp.getfo(self.remote_path, buf)
            sftp.close()
            raw = buf.getvalue().decode("utf-8", errors="replace")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("ports.json must be a JSON object at the top level")
            self.output.emit(f"[Ports] Fetched {len(raw)} bytes, {len(data)} PC(s).")
            self.finished_signal.emit(True, data)
        except FileNotFoundError:
            self.output.emit(f"[Ports ERROR] Remote file not found: {self.remote_path}")
            self.finished_signal.emit(False, {})
        except json.JSONDecodeError as e:
            self.output.emit(f"[Ports ERROR] Invalid JSON: {e}")
            self.finished_signal.emit(False, {})
        except Exception as e:
            self.output.emit(f"[Ports ERROR] {e}")
            self.finished_signal.emit(False, {})
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass


class CameraWorker(QThread):
    """Fetch MJPEG frames from a camera URL."""
    frame_ready = Signal(QImage)
    error = Signal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self._running = True

    def run(self):
        import urllib3
        urllib3.disable_warnings()
        while self._running:
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
                if not self._running:
                    break
                self.error.emit(str(e))
                # Wait before retrying to avoid spamming
                for _ in range(50):  # 5 seconds in 100ms increments
                    if not self._running:
                        return
                    time.sleep(0.1)

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
            # Master semantics — ONE SSH session, no SFTP, no retries.
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
        except Exception as e:
            self.output.emit(f"[Serial ERROR] {e}")
        finally:
            # try/finally kept (not a new connection — just ensures the
            # existing SSH client+channel close cleanly on ANY exit path
            # instead of leaking sshd-session.exe on the remote whenever
            # the recv loop throws mid-read).
            try:
                if self._channel is not None:
                    self._channel.close()
            except Exception:
                pass
            try:
                if self._client is not None:
                    self._client.close()
            except Exception:
                pass
            self._client = None
            self._channel = None
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
            # Signal the remote python to shut down cleanly so the COM port
            # is released. Three-step sequence, because Windows OpenSSH
            # wraps our exec_command in `cmd.exe /c "..."` and we have to
            # reach the grandchild python reliably:
            #   1. Send Ctrl-C as a best-effort hint (ignored without a PTY,
            #      but harmless).
            #   2. shutdown_write() sends SSH_MSG_CHANNEL_EOF — sshd-session
            #      closes the write end of cmd's stdin pipe, which cmd
            #      inherits to python. python's sys.stdin.read() unblocks
            #      with '' and the writer thread exits → main exits →
            #      ser.close() → COM released. This is the reliable path.
            #   3. close() tears down the channel on our side.
            try:
                self._channel.send(b"\x03")
            except Exception:
                pass
            try:
                self._channel.shutdown_write()
            except Exception:
                pass
            try:
                self._channel.close()
            except Exception:
                pass


# -------------------------------------------------------------------------
# Local mode workers — used when the selected PC has flash_method='local'
# (currently only the aneb-sim simulator entry).  Their public API is a
# strict superset of SSHWorker / SerialWorker so the flash / serial /
# CAN tabs can swap workers based on flash_method without touching their
# UI code.
# -------------------------------------------------------------------------


class LocalCommandWorker(QThread):
    """Run a shell command on the local machine in a background thread.

    Drop-in replacement for SSHWorker — same constructor signature
    (host/user/password are accepted-and-ignored so callers don't need
    a separate code path) and the same output / finished_signal API."""

    output = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, host, user, password, command,
                 parent=None, timeout=120, use_pty=False):
        super().__init__(parent)
        # host/user/password kept for signature compatibility with SSHWorker
        self.host = host
        self.user = user
        self.password = password
        self.command = command
        self.timeout = timeout
        self.use_pty = use_pty   # ignored — local stdout is line-buffered fine
        self._stop = False
        self._proc = None

    def run(self):
        import subprocess
        try:
            self.output.emit(f"[LOCAL] Running on 127.0.0.1: {self.command}")
            # shell=True so the same `&` chains used in the SSH paths work
            # unchanged on cmd.exe.  CREATE_NO_WINDOW prevents a black
            # console window flashing up for each subprocess.
            creationflags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags = subprocess.CREATE_NO_WINDOW
            self._proc = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                # bufsize=1 (line-buffered) is silently ignored in binary
                # mode on Python 3.12+ and produces a RuntimeWarning;
                # default buffering + readline gives the same behavior here.
                creationflags=creationflags,
            )
            assert self._proc.stdout is not None
            buf = b""
            for raw in iter(self._proc.stdout.readline, b""):
                if self._stop:
                    self._proc.terminate()
                    break
                buf = raw
                try:
                    line = buf.decode("utf-8")
                except UnicodeDecodeError:
                    line = buf.decode("cp850", errors="replace")
                # Strip ANSI + CR/LF, drop empty lines so the log doesn't fill
                # with avrdude's progress-bar overwrites.
                line = _ANSI_RE.sub("", line).rstrip("\r\n")
                if line:
                    self.output.emit(line)
            try:
                self._proc.wait(timeout=self.timeout)
                self.finished_signal.emit(str(self._proc.returncode))
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self.output.emit(f"[LOCAL] Command timed out after {self.timeout}s")
                self.finished_signal.emit("-1")
        except Exception as e:
            self.output.emit(f"[LOCAL ERROR] {e}")
            self.finished_signal.emit("-1")

    def stop(self):
        self._stop = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass


class LocalSerialWorker(QThread):
    """Open a serial port directly with pyserial in a background thread.

    Drop-in replacement for SerialWorker (which spawns serialterm.py over
    SSH).  remote_dir is accepted-and-ignored for signature compat."""

    output = Signal(str)
    finished_signal = Signal()

    def __init__(self, host, user, password, com_port, baudrate, remote_dir, parent=None):
        super().__init__(parent)
        # Compat fields (unused locally)
        self.host = host
        self.user = user
        self.password = password
        self.remote_dir = remote_dir
        self.com_port = com_port
        self.baudrate = int(baudrate) if baudrate else 115200
        self._running = True
        self._serial = None

    def run(self):
        try:
            import serial as pyserial
        except ImportError:
            self.output.emit("[LOCAL SERIAL ERROR] pyserial not installed")
            self.finished_signal.emit()
            return

        try:
            self.output.emit(
                f"[Serial] Opening {self.com_port} @ {self.baudrate} (local)..."
            )
            self._serial = pyserial.Serial(
                self.com_port,
                baudrate=self.baudrate,
                timeout=0.05,
            )
            self.output.emit(f"[Serial] Connected to {self.com_port}")
            buf = b""
            while self._running:
                # Don't gate on in_waiting — com0com on Windows sometimes
                # returns 0 from ClearCommError even when bytes are queued
                # (a known driver quirk), which makes a polled-only loop
                # silently drop everything.  read(BUFFER) honours the
                # 0.05 s timeout from Serial.__init__, so this returns
                # promptly with whatever's available (possibly empty).
                try:
                    chunk = self._serial.read(4096)
                except (OSError, pyserial.SerialException):
                    break
                if not chunk:
                    continue
                buf += chunk
                # Emit complete lines as ONE batched signal per read, not
                # one-emit-per-line.  At full UART speed (≈11 KB/s) the
                # per-line path produces ~1000 queued signals/sec, which
                # backs up Qt's event loop so badly that pressing "Close
                # Serial" doesn't look like it worked: the worker stops
                # within milliseconds, but the GUI thread spends the next
                # several seconds draining the backlog of text-append
                # events, during which clicks feel unresponsive.
                lines = []
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        text = line.decode("utf-8")
                    except UnicodeDecodeError:
                        text = line.decode("cp850", errors="replace")
                    text = text.rstrip("\r")
                    if text:
                        lines.append(text)
                if lines:
                    self.output.emit("\n".join(lines))
            # Flush any trailing partial line
            if buf:
                try:
                    text = buf.decode("utf-8")
                except UnicodeDecodeError:
                    text = buf.decode("cp850", errors="replace")
                text = text.rstrip("\r\n")
                if text:
                    self.output.emit(text)
        except Exception as e:
            self.output.emit(f"[LOCAL SERIAL ERROR] {e}")
        finally:
            try:
                if self._serial and self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass
            self.finished_signal.emit()

    def send_data(self, text: str):
        """Send a line over the serial port (mirrors SerialWorker)."""
        if self._serial and self._serial.is_open:
            try:
                self._serial.write((text + "\n").encode("utf-8"))
            except Exception:
                pass

    def stop(self):
        self._running = False

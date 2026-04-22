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
            # Ensure serialterm.py exists in the user's remote dir. We run this
            # as its OWN short-lived exec on a throwaway channel — NOT chained
            # with the python launch below via `&`.
            #
            # Why not chain:
            #   cmd /c "ensure" & python -u serialterm.py ...
            # looks tidy but it's the exact pattern that leaks the COM port:
            # when we call channel.shutdown_write() on Close, the SSH EOF
            # goes to the outer cmd.exe. cmd.exe has already handed control
            # to python, and the EOF does NOT reliably reach python.exe's
            # stdin handle (observed: cmd.exe swallows the EOF until its
            # own &-script finishes, even though it finished long ago — an
            # OpenSSH-on-Windows quirk). Result: python's sys.stdin.read(1)
            # in serialterm.py's writer thread blocks forever, ser.close()
            # never runs, COM port stays held, next Open Serial fails with
            # "Acesso negado". The remote serialterm.py's own comment
            # specifically warns about this chaining pattern.
            #
            # With a dedicated channel for just `python -u serialterm.py ...`,
            # shutdown_write lands directly on python's stdin, the writer
            # thread unblocks on EOF, main exits, ser.close() runs, port
            # is released — so the NEXT open is clean.
            remote_script = f"{self.remote_dir}\\serialterm.py"
            ensure_cmd = (
                f"cmd /c \"if not exist {remote_script}"
                f" (mkdir {self.remote_dir} >nul 2>&1"
                f" ^& copy {REMOTE_BASE_DIR}\\serialterm.py {remote_script} >nul 2>&1)\""
            )
            self.output.emit(f"[Serial] Ensuring: {ensure_cmd}")
            ensure_ch = self._client.get_transport().open_session()
            ensure_ch.exec_command(ensure_cmd)
            # Short bounded wait for the copy; it's I/O-only, completes fast.
            _t = time.time()
            while not ensure_ch.exit_status_ready() and (time.time() - _t) < 5:
                time.sleep(0.05)
            try:
                ensure_ch.close()
            except Exception:
                pass

            cmd = (
                f"python -u {remote_script}"
                f" --port {self.com_port} --baudrate {self.baudrate}"
            )
            self.output.emit(f"[Serial] Running: {cmd}")
            self._channel = self._client.get_transport().open_session()
            # No PTY — use python -u for unbuffered output instead.
            # PTY echoes back stdin which corrupts VirtualIO commands.
            self._channel.exec_command(cmd)
            # Prime the remote python's stdin with a single newline. Windows
            # OpenSSH wraps every exec_command in `cmd.exe /c <cmd>`, and
            # observed behavior is that cmd.exe's stdin handle hits EOF at
            # startup on second-and-later SSH sessions — causing
            # serialterm's writer thread (sys.stdin.read(1)) to unblock with
            # '' immediately → main exits → "Connected to COMxx... Reading"
            # then instant close. Writing a harmless "\n" here puts a byte
            # in the pipe so read(1) returns that byte instead of EOF; the
            # writer sees "\n" as a no-op (flushes an empty buf) and keeps
            # running. Real user commands flow normally afterward.
            try:
                self._channel.send(b"\n")
            except Exception:
                pass
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
            # Cooperative shutdown — NEVER force-kill the remote python.
            # A Force kill (Stop-Process -Force / taskkill /F) doesn't run
            # Python's finally block, so ser.close() never fires, the FTDI
            # driver's USB endpoint doesn't cleanly release, and the next
            # cycle disturbs the USB bus enough to break the camera
            # (ERROR_GEN_FAILURE 0x8007001F on the BRIO).
            #
            # Sequence:
            #   1. __RF_QUIT__\n marker — if the writer thread is alive,
            #      it recognizes this and triggers clean shutdown (sets
            #      _stop, cancel_read on serial, wakes reader).
            #   2. shutdown_write — SSH EOF; breaks writer's stdin read if
            #      it's still blocked.
            #   3. channel.close — breaks stdout on the remote, the reader
            #      thread's next flush raises OSError and exits → main's
            #      while-reader-alive loop exits → finally block runs →
            #      ser.close() runs → FTDI releases cleanly.
            # Any of the three is sufficient; all three together cover every
            # path without ever abruptly terminating the process.
            try:
                self._channel.send(b"__RF_QUIT__\n")
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

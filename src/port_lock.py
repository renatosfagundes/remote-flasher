"""COM port lock manager — cross-instance synchronization via lock files on lab PCs.

Each active serial connection creates a lock file on the remote PC at
``C:\\2026\\locks\\COM25.lock`` (JSON with user, machine, timestamp).
Other instances poll this directory to see which ports are in use.
Stale locks (no heartbeat for >12 minutes) are auto-cleaned.
"""
import json
import os
import platform
import time
import logging

import paramiko

# Suppress paramiko's noisy transport-level tracebacks (SSH banner errors
# etc.) — they pollute stderr when the lock poller can't reach a PC.
logging.getLogger("paramiko").setLevel(logging.CRITICAL)
from PySide6.QtCore import QObject, QTimer, Signal

from lab_config import COMPUTERS
from settings import load_settings

log = logging.getLogger(__name__)

LOCK_DIR = r"C:\2026\locks"
STALE_SECONDS = 150  # 2.5 min — heartbeat is 60s, so this tolerates one missed
                     # refresh (age ~120s) with 30s grace before another user can
                     # steal the lock. Short enough that a crashed flash op frees
                     # the port quickly; long enough to survive a network blip.
HEARTBEAT_SECONDS = 60
POLL_INTERVAL_MS = 60_000  # 60 seconds (was 15s — too aggressive, hammered SSHD)


class LockInfo:
    """Parsed content of a .lock file."""
    __slots__ = ("user", "machine", "timestamp", "port")

    def __init__(self, user: str, machine: str, timestamp: float, port: str = ""):
        self.user = user
        self.machine = machine
        self.timestamp = timestamp
        self.port = port

    def is_stale(self) -> bool:
        return (time.time() - self.timestamp) > STALE_SECONDS

    def display(self) -> str:
        return f"{self.user} ({self.machine})"


def _my_user() -> str:
    settings = load_settings()
    return settings.get("user_name", os.getlogin())


def _my_machine() -> str:
    return platform.node()


def _lock_content() -> dict:
    return {
        "user": _my_user(),
        "machine": _my_machine(),
        "timestamp": time.time(),
    }


def _sftp_connect(pc_info: dict) -> paramiko.SFTPClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        pc_info["host"],
        username=pc_info["user"],
        password=pc_info["password"],
        timeout=10,
    )
    return client, client.open_sftp()


def _ensure_lock_dir(sftp: paramiko.SFTPClient):
    """Create the lock directory if it doesn't exist."""
    try:
        sftp.stat(LOCK_DIR)
    except FileNotFoundError:
        # mkdir doesn't support recursive on paramiko, create parents manually
        parts = LOCK_DIR.replace("/", "\\").split("\\")
        path = ""
        for part in parts:
            path = f"{path}\\{part}" if path else part
            try:
                sftp.stat(path)
            except FileNotFoundError:
                try:
                    sftp.mkdir(path)
                except OSError:
                    pass


def acquire_lock(pc_info: dict, com_port: str) -> tuple[bool, str]:
    """Try to acquire a lock for a COM port on a remote PC.

    Returns (True, "") on success, or (False, "owner description") if locked.
    """
    lock_path = f"{LOCK_DIR}\\{com_port}.lock"
    tmp_path = f"{LOCK_DIR}\\{com_port}.lock.tmp"

    try:
        client, sftp = _sftp_connect(pc_info)
    except Exception as e:
        log.warning("Lock acquire: SSH failed — %s", e)
        return True, ""  # fail open — don't block on SSH errors

    try:
        _ensure_lock_dir(sftp)

        # Check existing lock
        try:
            with sftp.open(lock_path, "r") as f:
                data = json.loads(f.read().decode("utf-8"))
            info = LockInfo(data["user"], data["machine"], data["timestamp"], com_port)

            # Is it ours? (same user + machine)
            if info.user == _my_user() and info.machine == _my_machine():
                # Refresh our own lock
                pass  # fall through to write
            elif info.is_stale():
                log.info("Lock %s is stale (%s), cleaning", com_port, info.display())
            else:
                return False, info.display()
        except FileNotFoundError:
            pass  # no lock — proceed

        # Write lock via atomic tmp+rename
        content = json.dumps(_lock_content()).encode("utf-8")
        with sftp.open(tmp_path, "w") as f:
            f.write(content)
        try:
            sftp.remove(lock_path)
        except FileNotFoundError:
            pass
        sftp.rename(tmp_path, lock_path)
        return True, ""

    except Exception as e:
        log.warning("Lock acquire error: %s", e)
        return True, ""  # fail open
    finally:
        try:
            sftp.close()
            client.close()
        except Exception:
            pass


def release_lock(pc_info: dict, com_port: str):
    """Delete the lock file for a COM port (best-effort)."""
    lock_path = f"{LOCK_DIR}\\{com_port}.lock"
    try:
        client, sftp = _sftp_connect(pc_info)
        try:
            # Only delete if it's ours
            with sftp.open(lock_path, "r") as f:
                data = json.loads(f.read().decode("utf-8"))
            if data.get("user") == _my_user() and data.get("machine") == _my_machine():
                sftp.remove(lock_path)
        except FileNotFoundError:
            pass
        finally:
            sftp.close()
            client.close()
    except Exception as e:
        log.warning("Lock release error for %s: %s", com_port, e)


def refresh_lock(pc_info: dict, com_port: str):
    """Update the timestamp on our lock file (heartbeat)."""
    lock_path = f"{LOCK_DIR}\\{com_port}.lock"
    try:
        client, sftp = _sftp_connect(pc_info)
        try:
            content = json.dumps(_lock_content()).encode("utf-8")
            with sftp.open(lock_path, "w") as f:
                f.write(content)
        finally:
            sftp.close()
            client.close()
    except Exception as e:
        log.warning("Lock refresh error for %s: %s", com_port, e)


def poll_locks(pc_info: dict) -> dict[str, LockInfo]:
    """Read all lock files on a remote PC. Returns {com_port: LockInfo}.
    Automatically cleans stale locks.
    """
    locks = {}
    try:
        client, sftp = _sftp_connect(pc_info)
    except Exception as e:
        log.debug("Lock poll: SSH failed — %s", e)
        return locks

    try:
        _ensure_lock_dir(sftp)
        for fname in sftp.listdir(LOCK_DIR):
            if not fname.endswith(".lock"):
                continue
            port = fname.replace(".lock", "")
            fpath = f"{LOCK_DIR}\\{fname}"
            try:
                with sftp.open(fpath, "r") as f:
                    data = json.loads(f.read().decode("utf-8"))
                info = LockInfo(data["user"], data["machine"], data["timestamp"], port)
                if info.is_stale():
                    log.info("Cleaning stale lock: %s (%s)", port, info.display())
                    try:
                        sftp.remove(fpath)
                    except Exception:
                        pass
                else:
                    locks[port] = info
            except Exception:
                pass
    except Exception as e:
        log.debug("Lock poll error: %s", e)
    finally:
        try:
            sftp.close()
            client.close()
        except Exception:
            pass

    return locks


class PortLockManager(QObject):
    """Periodically polls lock state across all PCs and emits updates.

    locks_changed is emitted with {(pc_label, com_port): LockInfo} whenever
    the cached state changes. Polling is disabled by default and should be
    enabled after VPN connects (set_enabled(True)).
    """
    locks_changed = Signal()  # emitted when cache changes; call cached_locks() to read

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache: dict[tuple[str, str], LockInfo] = {}
        self._enabled = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)

    def set_enabled(self, enabled: bool):
        """Enable/disable periodic polling (call after VPN connects/disconnects)."""
        self._enabled = enabled
        if enabled and not self._timer.isActive():
            self._timer.start(POLL_INTERVAL_MS)
        elif not enabled and self._timer.isActive():
            self._timer.stop()
            self._cache.clear()

    def get_lock(self, pc_label: str, com_port: str) -> LockInfo | None:
        return self._cache.get((pc_label, com_port))

    def cached_locks(self) -> dict[tuple[str, str], LockInfo]:
        return dict(self._cache)

    def force_poll(self):
        """Trigger an immediate poll (e.g., after connecting/disconnecting)."""
        self._poll()

    def _poll(self):
        import threading
        threading.Thread(target=self._do_poll, daemon=True).start()

    def _do_poll(self):
        new_cache = {}
        for pc_label, pc_info in COMPUTERS.items():
            locks = poll_locks(pc_info)
            for port, info in locks.items():
                new_cache[(pc_label, port)] = info

        if new_cache != self._cache:
            self._cache = new_cache
            self.locks_changed.emit()

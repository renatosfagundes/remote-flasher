"""
Automated Environment Setup for ESA (Engenharia de Software Automotivo)
========================================================================
Sets up the complete development environment described in apostila.pdf:

  1. Arduino CLI         — download + install + PATH
  2. AVR 8-bit Toolchain — download + extract + PATH
  3. Trampoline RTOS     — git clone + submodules
  4. goil compiler       — download + place in avr_tools bin
  5. Arduino Nano template for Trampoline
  6. MCP_CAN library     — for both arduino-cli and Trampoline
  7. arduino-cli core + config (enable unsafe install)
  8. Fix known build issues (e.g. -Wno-unused-but-set-variable)

Run:
    python setup_environment.py          # full setup
    python setup_environment.py --check  # only verify what's installed
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
import textwrap
import urllib.request
import zipfile

# ── Paths ────────────────────────────────────────────────────────────────────
ESA_DIR = r"C:\ESA"
ARDUINO_CLI_DIR = os.path.join(ESA_DIR, "arduino_cli", "bin")
AVR_TOOLS_DIR = os.path.join(ESA_DIR, "avr_tools")
AVR_TOOLCHAIN_DIR = os.path.join(AVR_TOOLS_DIR, "avr8-gnu-toolchain-win32_x86")
AVR_BIN_DIR = os.path.join(AVR_TOOLCHAIN_DIR, "bin")
TRAMPOLINE_DIR = os.path.join(ESA_DIR, "trampoline")
TRAMPOLINE_OPT = os.path.join(TRAMPOLINE_DIR, "opt")
DEVEL_DIR = os.path.join(TRAMPOLINE_OPT, "devel")

# ── Download URLs ────────────────────────────────────────────────────────────
# Arduino CLI — latest stable for Windows 64-bit
ARDUINO_CLI_URL = (
    "https://github.com/arduino/arduino-cli/releases/download/v1.4.1/"
    "arduino-cli_1.4.1_Windows_64bit.zip"
)
# AVR 8-bit Toolchain — Zak Kemble's builds (Microchip's URL returns 403)
AVR_TOOLCHAIN_URL = (
    "https://github.com/ZakKemble/avr-gcc-build/releases/download/v15.2.0-1/"
    "avr-gcc-15.2.0-x64-windows.zip"
)
AVR_TOOLCHAIN_INNER_DIR = "avr-gcc-15.2.0-x64-windows"  # top-level dir inside the zip
# goil pre-built for Windows (official, hosted by Univ. de Nantes)
GOIL_URL = "https://uncloud.univ-nantes.fr/index.php/s/ZAyZ4ngSqCaa4wD/download"
# Trampoline git repo
TRAMPOLINE_REPO = "https://github.com/TrampolineRTOS/trampoline.git"
# Arduino core for Trampoline (submodule reference lost in upstream repo)
ARDUINO_CORE_REPO = "https://github.com/TrampolineRTOS/ArduinoCore-avr.git"
# MCP_CAN library
MCP_CAN_REPO = "https://github.com/coryjfowler/MCP_CAN_lib.git"

# ── Helpers ──────────────────────────────────────────────────────────────────

class Colors:
    OK = "\033[92m"
    WARN = "\033[93m"
    FAIL = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


def info(msg):
    print(f"{Colors.BOLD}[INFO]{Colors.END} {msg}")


def ok(msg):
    print(f"{Colors.OK}[OK]{Colors.END}   {msg}")


def warn(msg):
    print(f"{Colors.WARN}[WARN]{Colors.END} {msg}")


def fail(msg):
    print(f"{Colors.FAIL}[FAIL]{Colors.END} {msg}")


def run(cmd, cwd=None, check=True):
    """Run a shell command with live output streaming.

    Filters verbose git progress (Updating files: XX%) to only show
    every 25% milestone instead of every line.
    """
    info(f"Running: {cmd}")
    proc = subprocess.Popen(
        cmd, shell=True, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    import re as _re
    _last_git_pct = {}  # track per-phase (e.g. "Counting objects", "Receiving objects")
    _git_pct_re = _re.compile(r'(\w[\w\s]+?):\s+(\d+)%')
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        # Filter verbose git progress lines — only show 0%, 25%, 50%, 75%, 100%
        m = _git_pct_re.search(line)
        if m and ("objects" in line or "deltas" in line or "files" in line):
            phase = m.group(1).strip()
            pct = int(m.group(2))
            milestone = (pct // 25) * 25
            prev = _last_git_pct.get(phase, -1)
            if milestone <= prev and pct < 100:
                continue
            _last_git_pct[phase] = milestone
            if pct == 100:
                _last_git_pct[phase] = -1
        print(line)
        sys.stdout.flush()
    proc.wait()
    if check and proc.returncode != 0:
        fail(f"Command failed with exit code {proc.returncode}")
        return False
    return True


def download(url, dest_path, allow_insecure=False):
    """Download a file with a progress indicator."""
    global _last_pct_reported
    _last_pct_reported = -1
    info(f"Downloading {os.path.basename(dest_path)}...")
    info(f"  URL: {url}")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dest_path, _download_progress)
        ok(f"Downloaded to {dest_path}")
        return True
    except Exception as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e) and not allow_insecure:
            warn(f"SSL certificate error — retrying without verification...")
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            try:
                req = urllib.request.urlopen(url, context=ctx)
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = req.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                ok(f"Downloaded to {dest_path} (SSL verification skipped)")
                return True
            except Exception as e2:
                fail(f"Download failed even without SSL verification: {e2}")
                return False
        fail(f"Download failed: {e}")
        return False


_last_pct_reported = -1

def _download_progress(block_num, block_size, total_size):
    global _last_pct_reported
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(100, int(downloaded * 100 / total_size))
        # Only print at every 10% milestone to avoid flooding the log
        milestone = (pct // 10) * 10
        if milestone > _last_pct_reported:
            _last_pct_reported = milestone
            mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            print(f"  {mb:.1f} MB / {total_mb:.1f} MB ({milestone}%)")
            sys.stdout.flush()
    elif block_num % 200 == 0:
        mb = downloaded / (1024 * 1024)
        print(f"  {mb:.1f} MB downloaded")
        sys.stdout.flush()


def extract_zip(zip_path, dest_dir):
    """Extract a zip file."""
    info(f"Extracting {os.path.basename(zip_path)} -> {dest_dir}")
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    ok("Extraction complete.")


def add_to_user_path(directory):
    """Add a directory to the current user's PATH (Windows registry)."""
    if sys.platform != "win32":
        warn("PATH modification is only supported on Windows.")
        return
    import winreg
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Environment",
        0,
        winreg.KEY_READ | winreg.KEY_WRITE,
    )
    try:
        current_path, _ = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        current_path = ""
    # Check if already present (case-insensitive)
    entries = [e.strip() for e in current_path.split(";") if e.strip()]
    dir_lower = directory.lower()
    if any(e.lower() == dir_lower for e in entries):
        ok(f"PATH already contains: {directory}")
    else:
        entries.append(directory)
        new_path = ";".join(entries)
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
        ok(f"Added to user PATH: {directory}")
        info("  (Open a new terminal for PATH changes to take effect)")
    winreg.CloseKey(key)
    # Broadcast WM_SETTINGCHANGE so new terminals pick up the PATH change immediately
    try:
        import ctypes
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0,
            "Environment", SMTO_ABORTIFHUNG, 5000, None
        )
    except Exception:
        pass
    # Also update current process PATH
    if directory.lower() not in os.environ.get("PATH", "").lower():
        os.environ["PATH"] = directory + ";" + os.environ.get("PATH", "")


def which(exe):
    """Check if an executable is in PATH."""
    return shutil.which(exe)


# ── Step functions ───────────────────────────────────────────────────────────

def check_git():
    if which("git"):
        ok(f"git found: {which('git')}")
        return True
    fail("git is not installed or not in PATH.")
    info("  Download from: https://git-scm.com/download/win")
    return False


def check_python2():
    """Python 2.7 is required by Trampoline's make.py / build.py."""
    for name in ("python2", "python"):
        path = which(name)
        if path:
            result = subprocess.run(
                [path, "--version"], capture_output=True, text=True
            )
            version_str = (result.stdout + result.stderr).strip()
            if "2.7" in version_str:
                ok(f"Python 2.7 found: {path} ({version_str})")
                return True
    # Check common locations
    common = [r"C:\Python27\python.exe", r"C:\ESA\Python27\python.exe"]
    for p in common:
        if os.path.isfile(p):
            ok(f"Python 2.7 found at: {p}")
            warn("  But it may not be in PATH — add it for make.py to work.")
            return True
    warn("Python 2.7 not found. Trampoline's make.py requires Python 2.7.")
    info("  Download from: https://www.python.org/downloads/release/python-2718/")
    return False


def setup_arduino_cli():
    """Download and install Arduino CLI."""
    print(f"\n{'='*60}")
    info("Step 1: Arduino CLI")
    print(f"{'='*60}")

    exe_path = os.path.join(ARDUINO_CLI_DIR, "arduino-cli.exe")
    if os.path.isfile(exe_path):
        ok(f"Arduino CLI already installed at {exe_path}")
    else:
        os.makedirs(ARDUINO_CLI_DIR, exist_ok=True)
        zip_path = os.path.join(ESA_DIR, "arduino-cli.zip")
        if not download(ARDUINO_CLI_URL, zip_path):
            return False
        extract_zip(zip_path, ARDUINO_CLI_DIR)
        os.remove(zip_path)
        if not os.path.isfile(exe_path):
            fail(f"arduino-cli.exe not found after extraction at {exe_path}")
            return False
        ok("Arduino CLI installed.")

    add_to_user_path(ARDUINO_CLI_DIR)

    # Initialize config with unsafe install enabled
    config_path = os.path.join(ARDUINO_CLI_DIR, "arduino-cli.yaml")
    if not os.path.isfile(config_path):
        info("Creating arduino-cli config...")
        run(f'"{exe_path}" config init --dest-dir "{ARDUINO_CLI_DIR}"')

    if os.path.isfile(config_path):
        with open(config_path, "r") as f:
            content = f.read()
        if "enable_unsafe_install: true" not in content:
            content = content.replace(
                "enable_unsafe_install: false",
                "enable_unsafe_install: true",
            )
            # If the key doesn't exist, add it under library section
            if "enable_unsafe_install: true" not in content:
                content += "\nlibrary:\n  enable_unsafe_install: true\n"
            with open(config_path, "w") as f:
                f.write(content)
            ok("Enabled unsafe install in arduino-cli config.")

    # Install AVR core
    info("Installing Arduino AVR core...")
    run(f'"{exe_path}" --config-file "{config_path}" core update-index')
    run(f'"{exe_path}" --config-file "{config_path}" core install arduino:avr', check=False)

    # Install MCP_CAN library via arduino-cli
    info("Installing MCP_CAN library via arduino-cli...")
    run(
        f'"{exe_path}" --config-file "{config_path}" '
        f'lib install --git-url {MCP_CAN_REPO}',
        check=False,
    )

    return True


def setup_avr_toolchain():
    """Download and install AVR 8-bit Toolchain."""
    print(f"\n{'='*60}")
    info("Step 2: AVR 8-bit Toolchain")
    print(f"{'='*60}")

    avr_gcc = os.path.join(AVR_BIN_DIR, "avr-gcc.exe")
    if os.path.isfile(avr_gcc):
        ok(f"AVR Toolchain already installed at {AVR_TOOLCHAIN_DIR}")
    else:
        os.makedirs(AVR_TOOLS_DIR, exist_ok=True)
        zip_path = os.path.join(ESA_DIR, "avr-toolchain.zip")
        if not download(AVR_TOOLCHAIN_URL, zip_path):
            warn("Could not download AVR Toolchain automatically.")
            info("  Download manually from:")
            info("  https://github.com/ZakKemble/avr-gcc-build/releases")
            info(f"  Extract to: {AVR_TOOLS_DIR}")
            return False
        extract_zip(zip_path, AVR_TOOLS_DIR)
        os.remove(zip_path)
        # The zip may extract to a different directory name — rename to our expected path
        if not os.path.isfile(avr_gcc):
            extracted = os.path.join(AVR_TOOLS_DIR, AVR_TOOLCHAIN_INNER_DIR)
            if os.path.isdir(extracted):
                info(f"Renaming {AVR_TOOLCHAIN_INNER_DIR} -> {os.path.basename(AVR_TOOLCHAIN_DIR)}")
                os.rename(extracted, AVR_TOOLCHAIN_DIR)
        if not os.path.isfile(avr_gcc):
            # Last resort: find avr-gcc.exe anywhere under avr_tools
            for root, dirs, files in os.walk(AVR_TOOLS_DIR):
                if "avr-gcc.exe" in files:
                    found_bin = root
                    found_toolchain = os.path.dirname(found_bin)
                    if found_toolchain != AVR_TOOLCHAIN_DIR:
                        info(f"Renaming {os.path.basename(found_toolchain)} -> {os.path.basename(AVR_TOOLCHAIN_DIR)}")
                        os.rename(found_toolchain, AVR_TOOLCHAIN_DIR)
                    break
        if not os.path.isfile(avr_gcc):
            fail("avr-gcc.exe not found after extraction.")
            return False
        ok("AVR Toolchain installed.")

    add_to_user_path(AVR_BIN_DIR)
    return True


def setup_trampoline():
    """Clone Trampoline RTOS and set up submodules."""
    print(f"\n{'='*60}")
    info("Step 3: Trampoline RTOS")
    print(f"{'='*60}")

    if not check_git():
        return False

    if os.path.isdir(os.path.join(TRAMPOLINE_DIR, ".git")):
        ok(f"Trampoline already cloned at {TRAMPOLINE_DIR}")
    else:
        # Remove broken/incomplete directory from a previous failed clone
        if os.path.isdir(TRAMPOLINE_DIR):
            warn(f"Removing incomplete Trampoline directory...")
            shutil.rmtree(TRAMPOLINE_DIR, ignore_errors=True)
        info("Cloning Trampoline RTOS (this may take a few minutes)...")
        run(f'git clone --progress {TRAMPOLINE_REPO} "{TRAMPOLINE_DIR}"')

    # Initialize Arduino core — the upstream repo has a broken submodule reference
    # (.gitmodules was removed but the submodule commit entry remains), so we clone directly.
    arduino_dir = os.path.join(TRAMPOLINE_DIR, "machines", "avr", "arduino")
    cores_dir = os.path.join(arduino_dir, "cores")
    if os.path.isdir(cores_dir) and os.listdir(cores_dir):
        ok("Arduino core already present.")
    else:
        info("Cloning Arduino core for Trampoline...")
        # Remove the empty/broken submodule entry and clone fresh
        temp_clone = os.path.join(TRAMPOLINE_OPT, "_ArduinoCore-avr")
        if os.path.isdir(temp_clone):
            import shutil as _shutil
            _shutil.rmtree(temp_clone)
        run(f'git clone --progress {ARDUINO_CORE_REPO} "{temp_clone}"', check=False)
        if os.path.isdir(temp_clone):
            # Copy everything from the clone into the trampoline arduino dir
            # (cores/, variants/, and root files like tpl_trace.cpp)
            import shutil as _shutil
            for item in os.listdir(temp_clone):
                if item.startswith("."):
                    continue  # skip .git etc.
                src = os.path.join(temp_clone, item)
                dst = os.path.join(arduino_dir, item)
                if os.path.exists(dst):
                    continue  # don't overwrite existing (e.g. libraries/)
                if os.path.isdir(src):
                    _shutil.copytree(src, dst)
                else:
                    _shutil.copy2(src, dst)
                ok(f"  Copied {item}")
            _shutil.rmtree(temp_clone, ignore_errors=True)
        if os.path.isdir(cores_dir):
            ok("Arduino core installed.")
        else:
            fail("Failed to install Arduino core.")

    # Create opt directory
    os.makedirs(TRAMPOLINE_OPT, exist_ok=True)
    os.makedirs(DEVEL_DIR, exist_ok=True)
    ok("Trampoline directories created.")

    return True


def setup_goil():
    """Ensure goil is available in the AVR toolchain bin."""
    print(f"\n{'='*60}")
    info("Step 4: goil (OIL compiler)")
    print(f"{'='*60}")

    goil_dest = os.path.join(AVR_BIN_DIR, "goil.exe")

    if os.path.isfile(goil_dest):
        ok(f"goil already available at {goil_dest}")
        return True

    # Check if goil exists in the trampoline build directory
    goil_build = os.path.join(TRAMPOLINE_DIR, "goil", "build", "goil.exe")
    if os.path.isfile(goil_build):
        info(f"Copying goil from {goil_build} -> {goil_dest}")
        shutil.copy2(goil_build, goil_dest)
        ok("goil copied to AVR toolchain bin.")
        return True

    # Check trampoline/opt for a goil zip
    goil_zip = None
    if os.path.isdir(TRAMPOLINE_OPT):
        for f in os.listdir(TRAMPOLINE_OPT):
            if "goil" in f.lower() and f.endswith(".zip"):
                goil_zip = os.path.join(TRAMPOLINE_OPT, f)
                break

    if goil_zip:
        info(f"Extracting goil from {goil_zip}...")
        extract_zip(goil_zip, AVR_BIN_DIR)
        if os.path.isfile(goil_dest):
            ok("goil extracted successfully.")
            return True

    # Download goil from the official Trampoline host
    info("Downloading goil from Univ. de Nantes...")
    os.makedirs(TRAMPOLINE_OPT, exist_ok=True)
    goil_zip = os.path.join(TRAMPOLINE_OPT, "goil-windows.zip")
    if download(GOIL_URL, goil_zip):
        extract_zip(goil_zip, AVR_BIN_DIR)
        if os.path.isfile(goil_dest):
            ok("goil downloaded and installed.")
            return True
        # goil.exe might be inside a subdirectory in the zip
        for root, dirs, files in os.walk(AVR_BIN_DIR):
            if "goil.exe" in files and root != AVR_BIN_DIR:
                for f in files:
                    src = os.path.join(root, f)
                    dst = os.path.join(AVR_BIN_DIR, f)
                    if not os.path.exists(dst):
                        shutil.move(src, dst)
                break
        if os.path.isfile(goil_dest):
            ok("goil downloaded and installed.")
            return True

    warn("goil.exe could not be installed automatically.")
    info("  Download manually from the Trampoline README and place in:")
    info(f"    {AVR_BIN_DIR}")
    return False


def setup_nano_template():
    """Create Arduino Nano template for Trampoline (copy from Uno)."""
    print(f"\n{'='*60}")
    info("Step 5: Arduino Nano template for Trampoline")
    print(f"{'='*60}")

    uno_template = os.path.join(
        TRAMPOLINE_DIR, "goil", "templates", "config", "avr", "arduino", "uno"
    )
    nano_template = os.path.join(
        TRAMPOLINE_DIR, "goil", "templates", "config", "avr", "arduino", "nano"
    )

    if os.path.isdir(nano_template):
        ok("Nano template already exists.")
    else:
        if not os.path.isdir(uno_template):
            fail(f"Uno template not found at {uno_template}")
            return False
        info("Copying Uno template -> Nano template...")
        shutil.copytree(uno_template, nano_template)
        ok("Nano template created.")

    # Patch config.oil: change PLATFORM_FILES name and path
    config_oil = os.path.join(nano_template, "config.oil")
    if os.path.isfile(config_oil):
        with open(config_oil, "r") as f:
            content = f.read()

        modified = False
        if "arduinoUno" in content:
            content = content.replace("arduinoUno", "arduinoNano")
            modified = True
        # The Nano uses the same variant as Uno (standard), so path stays the same.

        if modified:
            with open(config_oil, "w") as f:
                f.write(content)
            ok("Patched nano config.oil (arduinoUno -> arduinoNano).")
        else:
            ok("Nano config.oil already patched.")

    # Create Nano examples directory
    nano_examples = os.path.join(TRAMPOLINE_DIR, "examples", "avr", "arduinoNano")
    uno_examples = os.path.join(TRAMPOLINE_DIR, "examples", "avr", "arduinoUno")
    if not os.path.isdir(nano_examples) and os.path.isdir(uno_examples):
        info("Copying Uno examples -> Nano examples...")
        shutil.copytree(uno_examples, nano_examples)
        ok("Nano examples created.")
    elif os.path.isdir(nano_examples):
        ok("Nano examples already exist.")

    return True


def setup_mcp_can_trampoline():
    """Install MCP_CAN library for Trampoline (manual copy method)."""
    print(f"\n{'='*60}")
    info("Step 6: MCP_CAN library for Trampoline")
    print(f"{'='*60}")

    mcp_can_lib = os.path.join(
        TRAMPOLINE_DIR, "machines", "avr", "arduino", "libraries", "mcp_can", "src"
    )

    if os.path.isdir(mcp_can_lib) and os.listdir(mcp_can_lib):
        ok("MCP_CAN library already installed for Trampoline.")
        return True

    # Clone MCP_CAN_lib to opt/
    mcp_clone_dir = os.path.join(TRAMPOLINE_OPT, "MCP_CAN_lib")
    if not os.path.isdir(mcp_clone_dir):
        if not check_git():
            return False
        info("Cloning MCP_CAN library...")
        run(f'git clone --progress {MCP_CAN_REPO} "{mcp_clone_dir}"')

    # Create library directory and copy files
    os.makedirs(mcp_can_lib, exist_ok=True)
    count = 0
    for f in os.listdir(mcp_clone_dir):
        if f.startswith("mcp_can"):
            src = os.path.join(mcp_clone_dir, f)
            dst = os.path.join(mcp_can_lib, f)
            shutil.copy2(src, dst)
            count += 1
    ok(f"Copied {count} mcp_can files to Trampoline libraries.")

    # Patch the Arduino config.oil to declare the mcp_can library
    _patch_config_oil_library()

    return True


def _patch_config_oil_library():
    """Add LIBRARY = mcp_can to the Arduino config.oil if not present."""
    config_oil = os.path.join(
        TRAMPOLINE_DIR, "goil", "templates", "config", "avr", "arduino", "config.oil"
    )
    if not os.path.isfile(config_oil):
        warn(f"Could not find {config_oil} to patch.")
        return

    with open(config_oil, "r") as f:
        content = f.read()

    if "mcp_can" in content:
        ok("config.oil already declares mcp_can library.")
        return

    # Find a good insertion point — after the last LIBRARY line or after BUILD = TRUE block
    # We look for the closing }; of the BUILDOPTIONS block and add after it
    insertion_marker = "LIBRARY mcp_can"
    library_block = textwrap.dedent("""\

    LIBRARY mcp_can {
      PATH = "avr/arduino/libraries/mcp_can";
      CPPFILE = "src/mcp_can.cpp";
      CFILE = "";
    };
    """)

    # Insert before the last closing of the file
    # Find the main config.oil structure — add as a new block
    if "LIBRARY serial" in content:
        # Insert after the serial LIBRARY block
        idx = content.find("LIBRARY serial")
        # Find the closing }; of that block
        brace_count = 0
        pos = content.index("{", idx)
        for i in range(pos, len(content)):
            if content[i] == "{":
                brace_count += 1
            elif content[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    # Find the ; after }
                    semi = content.index(";", i)
                    content = content[:semi + 1] + library_block + content[semi + 1:]
                    break
    else:
        warn("Could not find insertion point in config.oil. Please add mcp_can LIBRARY manually.")
        info("  See apostila.pdf Section 5.1 for the exact syntax.")
        return

    with open(config_oil, "w") as f:
        f.write(content)
    ok("Patched config.oil to include mcp_can library.")


def fix_build_issues():
    """Fix known build issues mentioned in the apostila."""
    print(f"\n{'='*60}")
    info("Step 7: Fixing known build issues")
    print(f"{'='*60}")

    # Fix: comment out -Wno-unused-but-set-variable if present
    # This flag causes cc1.exe errors with some avr-gcc versions
    config_files = [
        os.path.join(
            TRAMPOLINE_DIR, "goil", "templates", "config", "avr", "arduino", "config.oil"
        ),
        os.path.join(
            TRAMPOLINE_DIR, "goil", "templates", "config", "avr", "arduino", "uno", "config.oil"
        ),
        os.path.join(
            TRAMPOLINE_DIR, "goil", "templates", "config", "avr", "arduino", "nano", "config.oil"
        ),
    ]

    for config_oil in config_files:
        if not os.path.isfile(config_oil):
            continue
        with open(config_oil, "r") as f:
            content = f.read()

        if "-Wno-unused-but-set-variable" in content:
            # Comment out the line containing that flag
            lines = content.split("\n")
            modified = False
            for i, line in enumerate(lines):
                if "-Wno-unused-but-set-variable" in line and not line.strip().startswith("//"):
                    lines[i] = "//" + line
                    modified = True
            if modified:
                with open(config_oil, "w") as f:
                    f.write("\n".join(lines))
                ok(f"Commented out -Wno-unused-but-set-variable in {os.path.basename(config_oil)}")
        else:
            ok(f"No -Wno-unused-but-set-variable issue in {os.path.basename(config_oil)}")

    return True


# ── Check mode ───────────────────────────────────────────────────────────────

def check_environment():
    """Verify what's installed without changing anything."""
    print(f"\n{'='*60}")
    info("Environment Check")
    print(f"{'='*60}\n")

    checks = [
        ("Git", lambda: bool(which("git"))),
        ("Python 2.7", lambda: os.path.isfile(r"C:\Python27\python.exe") or "2.7" in _get_python_version()),
        ("Arduino CLI", lambda: os.path.isfile(os.path.join(ARDUINO_CLI_DIR, "arduino-cli.exe"))),
        ("Arduino CLI in PATH", lambda: bool(which("arduino-cli"))),
        ("AVR Toolchain", lambda: os.path.isfile(os.path.join(AVR_BIN_DIR, "avr-gcc.exe"))),
        ("AVR tools in PATH", lambda: bool(which("avr-gcc"))),
        ("goil compiler", lambda: os.path.isfile(os.path.join(AVR_BIN_DIR, "goil.exe"))),
        ("Trampoline RTOS", lambda: os.path.isdir(os.path.join(TRAMPOLINE_DIR, ".git"))),
        ("Arduino submodule", lambda: os.path.isdir(os.path.join(TRAMPOLINE_DIR, "machines", "avr", "arduino", "cores"))),
        ("Nano template", lambda: os.path.isdir(os.path.join(TRAMPOLINE_DIR, "goil", "templates", "config", "avr", "arduino", "nano"))),
        ("MCP_CAN (Trampoline)", lambda: os.path.isdir(os.path.join(TRAMPOLINE_DIR, "machines", "avr", "arduino", "libraries", "mcp_can", "src"))),
        ("Nano examples", lambda: os.path.isdir(os.path.join(TRAMPOLINE_DIR, "examples", "avr", "arduinoNano"))),
    ]

    all_ok = True
    for name, check_fn in checks:
        try:
            result = check_fn()
        except Exception:
            result = False
        if result:
            ok(name)
        else:
            fail(name)
            all_ok = False

    print()
    if all_ok:
        ok("All components are installed!")
    else:
        warn("Some components are missing. Run without --check to install them.")
    return all_ok


def _get_python_version():
    try:
        r = subprocess.run(["python", "--version"], capture_output=True, text=True)
        return (r.stdout + r.stderr).strip()
    except Exception:
        return ""


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Automated ESA environment setup (apostila.pdf)"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Only check what's installed, don't modify anything",
    )
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip downloading tools (useful if you already have them)",
    )
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}{'='*60}")
    print("  ESA Environment Setup — apostila.pdf")
    print(f"{'='*60}{Colors.END}")
    print(f"  Base directory: {ESA_DIR}")
    print(f"  Platform: {platform.system()} {platform.machine()}")
    print()

    if args.check:
        check_environment()
        return

    # Pre-flight checks
    if sys.platform != "win32":
        fail("This script is designed for Windows.")
        sys.exit(1)

    os.makedirs(ESA_DIR, exist_ok=True)

    steps = [
        ("Arduino CLI", setup_arduino_cli),
        ("AVR Toolchain", setup_avr_toolchain),
        ("Trampoline RTOS", setup_trampoline),
        ("goil compiler", setup_goil),
        ("Nano template", setup_nano_template),
        ("MCP_CAN for Trampoline", setup_mcp_can_trampoline),
        ("Fix build issues", fix_build_issues),
    ]

    results = []
    for name, step_fn in steps:
        try:
            success = step_fn()
        except Exception as e:
            fail(f"Exception in {name}: {e}")
            success = False
        results.append((name, success))

    # Summary
    print(f"\n{'='*60}")
    info("SETUP SUMMARY")
    print(f"{'='*60}")
    for name, success in results:
        if success:
            ok(name)
        else:
            fail(name)

    print()
    all_ok = all(s for _, s in results)
    if all_ok:
        ok("Environment setup complete!")
    else:
        warn("Some steps had issues. Review the output above.")

    print()
    info("Next steps:")
    info("  1. Open a NEW terminal (for PATH changes)")
    info("  2. Verify with: python setup_environment.py --check")
    info("  3. Ensure Python 2.7 is installed (needed for Trampoline make.py)")
    info("  4. Try compiling an example:")
    info(f'     cd "{TRAMPOLINE_DIR}\\examples\\avr\\arduinoNano\\blink"')
    info('     goil --target=avr/arduino/nano --templates=../../../../goil/templates/ blink.oil')
    info("     make.py")


if __name__ == "__main__":
    main()

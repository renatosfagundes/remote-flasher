# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\main.py'],
    pathex=['src'],
    binaries=[],
    datas=[('assets/icon.ico', 'assets'), ('src/lab_config.py', '.'), ('src/serialterm.py', '.'), ('src/settings.py', '.'), ('src/workers.py', '.'), ('src/widgets.py', '.'), ('src/main_window.py', '.'), ('src/tabs/__init__.py', 'tabs'), ('src/tabs/vpn_tab.py', 'tabs'), ('src/tabs/flash_tab.py', 'tabs'), ('src/tabs/can_tab.py', 'tabs'), ('src/tabs/serial_tab.py', 'tabs'), ('src/tabs/ssh_tab.py', 'tabs'), ('src/tabs/setup_tab.py', 'tabs'), ('secrets.py', '.'), ('setup_environment.py', '.')],
    hiddenimports=['paramiko', 'requests', 'settings', 'workers', 'widgets', 'main_window', 'tabs', 'tabs.vpn_tab', 'tabs.flash_tab', 'tabs.can_tab', 'tabs.serial_tab', 'tabs.ssh_tab', 'tabs.setup_tab'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RemoteFlasher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)

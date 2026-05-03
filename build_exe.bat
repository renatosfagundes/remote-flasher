@echo off
REM Build standalone .exe with PyInstaller
REM Run from the remote_flasher (project root) directory

REM Use python from PATH by default. Override by setting PYTHON env var before running.
if not defined PYTHON set PYTHON=python

REM Read version from VERSION file
for /f %%v in (VERSION) do set VERSION=%%v
echo Version: %VERSION%

echo Installing PyInstaller if needed...
%PYTHON% -m pip install pyinstaller --quiet

echo Building executable...
%PYTHON% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "RemoteFlasher_v%VERSION%" ^
    --icon "assets\icon.ico" ^
    --add-data "assets\icon.ico;assets" ^
    --add-data "secrets.py;." ^
    --add-data "src\serialterm.py;." ^
    --add-data "setup_environment.py;." ^
    --paths "src" ^
    --hidden-import _version ^
    --hidden-import paramiko ^
    --hidden-import requests ^
    --hidden-import serial ^
    --hidden-import settings ^
    --hidden-import workers ^
    --hidden-import widgets ^
    --hidden-import main_window ^
    --hidden-import lab_config ^
    --hidden-import ports_sync ^
    --hidden-import dashboard_backend ^
    --hidden-import analog_gauge_widget ^
    --hidden-import radial_bar ^
    --hidden-import tabs ^
    --hidden-import tabs.vpn_tab ^
    --hidden-import tabs.flash_tab ^
    --hidden-import tabs.can_tab ^
    --hidden-import tabs.serial_tab ^
    --hidden-import tabs.ssh_tab ^
    --hidden-import tabs.setup_tab ^
    --hidden-import tabs.hmi_tab ^
    --hidden-import tabs.gauges_tab ^
    --hidden-import tabs.plotter_tab ^
    --hidden-import plotter ^
    --hidden-import plotter.ring_buffer ^
    --hidden-import plotter.signal_config ^
    --hidden-import plotter.signal_list_widget ^
    --hidden-import plotter.plotter_backend ^
    --hidden-import plotter.plotter_widget ^
    src\main.py

echo.
if exist "dist\RemoteFlasher_v%VERSION%.exe" (
    echo SUCCESS: dist\RemoteFlasher_v%VERSION%.exe
    echo Size:
    dir "dist\RemoteFlasher_v%VERSION%.exe" | findstr RemoteFlasher
) else (
    echo FAILED — check output above for errors.
)

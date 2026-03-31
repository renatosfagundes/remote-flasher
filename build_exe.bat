@echo off
REM Build standalone .exe with PyInstaller
REM Run from the remote_flasher (project root) directory

REM Use python from PATH by default. Override by setting PYTHON env var before running.
if not defined PYTHON set PYTHON=python

echo Installing PyInstaller if needed...
%PYTHON% -m pip install pyinstaller --quiet

echo Building executable...
%PYTHON% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "RemoteFlasher" ^
    --icon "assets\icon.ico" ^
    --add-data "assets\icon.ico;assets" ^
    --add-data "src\lab_config.py;." ^
    --add-data "src\serialterm.py;." ^
    --add-data "src\settings.py;." ^
    --add-data "src\workers.py;." ^
    --add-data "src\widgets.py;." ^
    --add-data "src\main_window.py;." ^
    --add-data "src\tabs\__init__.py;tabs" ^
    --add-data "src\tabs\vpn_tab.py;tabs" ^
    --add-data "src\tabs\flash_tab.py;tabs" ^
    --add-data "src\tabs\serial_tab.py;tabs" ^
    --add-data "src\tabs\ssh_tab.py;tabs" ^
    --add-data "src\tabs\setup_tab.py;tabs" ^
    --add-data "secrets.py;." ^
    --paths "src" ^
    --hidden-import paramiko ^
    --hidden-import requests ^
    --hidden-import settings ^
    --hidden-import workers ^
    --hidden-import widgets ^
    --hidden-import main_window ^
    --hidden-import tabs ^
    --hidden-import tabs.vpn_tab ^
    --hidden-import tabs.flash_tab ^
    --hidden-import tabs.serial_tab ^
    --hidden-import tabs.ssh_tab ^
    --hidden-import tabs.setup_tab ^
    src\main.py

echo.
if exist dist\RemoteFlasher.exe (
    echo SUCCESS: dist\RemoteFlasher.exe
    echo Size:
    dir dist\RemoteFlasher.exe | findstr RemoteFlasher
) else (
    echo FAILED — check output above for errors.
)

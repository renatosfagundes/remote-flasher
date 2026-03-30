@echo off
REM Build standalone .exe with PyInstaller
REM Run from the remote_flasher directory

REM Use python from PATH by default. Override by setting PYTHON env var before running.
if not defined PYTHON set PYTHON=python

echo Installing PyInstaller if needed...
%PYTHON% -m pip install pyinstaller --quiet

echo Building executable...
%PYTHON% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "RemoteFlasher" ^
    --icon "icon.ico" ^
    --add-data "icon.ico;." ^
    --add-data "lab_config.py;." ^
    --add-data "serialterm.py;." ^
    --hidden-import paramiko ^
    --hidden-import requests ^
    main.py

echo.
if exist dist\RemoteFlasher.exe (
    echo SUCCESS: dist\RemoteFlasher.exe
    echo Size:
    dir dist\RemoteFlasher.exe | findstr RemoteFlasher
) else (
    echo FAILED — check output above for errors.
)

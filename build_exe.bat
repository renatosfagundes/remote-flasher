@echo off
REM Build standalone .exe with PyInstaller.
REM Run from the remote_flasher (project root) directory.

if not defined PYTHON set PYTHON=python

for /f %%v in (VERSION) do set VERSION=%%v
echo Version: %VERSION%

echo Installing PyInstaller if needed...
%PYTHON% -m pip install pyinstaller --quiet

echo Building executable...
REM --collect-all PySide6 used to be here; it bundled every Qt module
REM (WebEngine, 3D, Multimedia, Charts, ...) and blew the .exe up to
REM ~270 MB. PyInstaller's built-in PySide6 hook already discovers the
REM modules we actually import — we just need to name the QML-related
REM ones with --collect-submodules so QQuickWidget + QML plugins land
REM in the bundle.
%PYTHON% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "RemoteFlasher_v%VERSION%" ^
    --icon "assets\icon.ico" ^
    --add-data "assets\icon.ico;assets" ^
    --add-data "src\_version.py;." ^
    --add-data "src\lab_config.py;." ^
    --add-data "src\ports_sync.py;." ^
    --add-data "src\serialterm.py;." ^
    --add-data "src\settings.py;." ^
    --add-data "src\workers.py;." ^
    --add-data "src\widgets.py;." ^
    --add-data "src\main_window.py;." ^
    --add-data "src\dashboard_backend.py;." ^
    --add-data "src\dashboard_config.json;." ^
    --add-data "src\analog_gauge_widget.py;." ^
    --add-data "src\radial_bar.py;." ^
    --add-data "src\qml;qml" ^
    --add-data "src\fonts;fonts" ^
    --add-data "src\plotter;plotter" ^
    --add-data "src\tabs;tabs" ^
    --add-data "secrets.py;." ^
    --paths "src" ^
    --paths "src\plotter" ^
    --hidden-import _version ^
    --hidden-import paramiko ^
    --hidden-import requests ^
    --hidden-import dashboard_backend ^
    --hidden-import analog_gauge_widget ^
    --hidden-import radial_bar ^
    --hidden-import pyqtgraph ^
    --hidden-import numpy ^
    --hidden-import PySide6.QtQml ^
    --hidden-import PySide6.QtQuick ^
    --hidden-import PySide6.QtQuickWidgets ^
    --hidden-import PySide6.QtQuickControls2 ^
    --collect-submodules PySide6.QtQml ^
    --collect-submodules PySide6.QtQuick ^
    --exclude-module PySide6.QtWebEngineCore ^
    --exclude-module PySide6.QtWebEngineWidgets ^
    --exclude-module PySide6.QtWebEngineQuick ^
    --exclude-module PySide6.QtMultimedia ^
    --exclude-module PySide6.QtMultimediaWidgets ^
    --exclude-module PySide6.Qt3DCore ^
    --exclude-module PySide6.Qt3DRender ^
    --exclude-module PySide6.Qt3DAnimation ^
    --exclude-module PySide6.Qt3DExtras ^
    --exclude-module PySide6.Qt3DInput ^
    --exclude-module PySide6.Qt3DLogic ^
    --exclude-module PySide6.QtCharts ^
    --exclude-module PySide6.QtDataVisualization ^
    --exclude-module PySide6.QtQuick3D ^
    --exclude-module PySide6.QtBluetooth ^
    --exclude-module PySide6.QtPositioning ^
    --exclude-module PySide6.QtLocation ^
    --exclude-module PySide6.QtNfc ^
    --exclude-module PySide6.QtSensors ^
    --exclude-module PySide6.QtSerialBus ^
    --exclude-module PySide6.QtTextToSpeech ^
    --exclude-module PySide6.QtPdf ^
    --exclude-module PySide6.QtPdfWidgets ^
    --exclude-module matplotlib ^
    --exclude-module tkinter ^
    src\main.py

echo.
if exist "dist\RemoteFlasher_v%VERSION%.exe" (
    echo SUCCESS: dist\RemoteFlasher_v%VERSION%.exe
    dir "dist\RemoteFlasher_v%VERSION%.exe" | findstr RemoteFlasher
) else (
    echo FAILED -- check output above for errors.
)

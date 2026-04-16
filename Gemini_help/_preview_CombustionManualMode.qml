import QtQuick 2.15
import QtQuick.Window 2.15
Window {
    id: win
    width: 1200
    height: 650
    // Floor so Qt layouts can't collapse to invalid (negative) sizes.
    // Below ~800x450 the QML modes start producing layout warnings.
    minimumWidth: 800
    minimumHeight: 450
    visible: true
    color: "black"
    title: "Preview: CombustionManualMode"

    // Scale-to-fit container: the loaded mode is always laid out at its
    // native 1200x650, then scaled down (never up) so it fits the window
    // while preserving aspect ratio.
    Item {
        id: scaler
        anchors.centerIn: parent
        width: 1200
        height: 650
        scale: Math.min(win.width / 1200, win.height / 650, 1.0)
        Loader {
            anchors.fill: parent
            source: "file:///c:/Users/rfagu/Codigos/Pos/RTOS/Gemini_help/CombustionManualMode.qml"
        }
    }
}

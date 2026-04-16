// TestAllModes.qml — cycles through all 3 modes every 5s
import QtQuick 2.15
import QtQuick.Layouts 1.15

Window {
    id: win
    width: 1200
    height: 650
    visible: true
    title: "Qt6 Dashboard Modes Preview"

    StackLayout {
        id: modeStack
        anchors.fill: parent
        currentIndex: 0

        ElectricMode { }
        CombustionAutoMode { }
        CombustionManualMode { }
    }

    Timer {
        interval: 5000
        running: true  // set to false to freeze on a single mode
        repeat: true
        onTriggered: {
            modeStack.currentIndex = (modeStack.currentIndex + 1) % modeStack.count
            console.log("[mode switch] to index " + modeStack.currentIndex)
        }
    }
}

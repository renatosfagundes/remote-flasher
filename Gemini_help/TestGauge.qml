import QtQuick 2.15
import QtQuick.Window 2.15

Window {
    id: win
    width: 600
    height: 600
    visible: true
    color: "#0c0c14"

    property real testValue: 0

    Gauge {
        id: speedo
        anchors.centerIn: parent
        s: 1.2
        value: win.testValue
        maximumValue: 260
        redZoneStart: 220
        accentColor: "#01E6DE"
        unitLabel: "km/h"
    }

    SequentialAnimation {
        running: true
        loops: Animation.Infinite
        NumberAnimation { target: win; property: "testValue"; from: 0; to: 260; duration: 4000; easing.type: Easing.InOutSine }
        NumberAnimation { target: win; property: "testValue"; from: 260; to: 0; duration: 2000; easing.type: Easing.InOutQuad }
    }
}

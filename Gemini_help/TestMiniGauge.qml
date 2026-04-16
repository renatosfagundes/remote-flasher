import QtQuick 2.15
import QtQuick.Window 2.15

Window {
    id: win
    width: 1000
    height: 600
    visible: true
    color: "#0c0c14"
    
    property real mockValue: 0

    MiniGauge {
        anchors.left: parent.left
        anchors.leftMargin: 60
        anchors.verticalCenter: parent.verticalCenter
        s: 1.2
        label: "TEMP"
        units: "°C"
        value: 40 + (win.mockValue * 0.9) 
        maxValue: 130
        dangerAbove: 115
    }

    MiniGauge {
        anchors.right: parent.right
        anchors.rightMargin: 60
        anchors.verticalCenter: parent.verticalCenter
        s: 1.2
        label: "FUEL"
        units: "%"
        value: win.mockValue
        maxValue: 100
        dangerBelow: 15
    }

    SequentialAnimation {
        running: true; loops: Animation.Infinite
        NumberAnimation { target: win; property: "mockValue"; from: 0; to: 100; duration: 5000; easing.type: Easing.InOutQuad }
        PauseAnimation { duration: 1000 }
        NumberAnimation { target: win; property: "mockValue"; from: 100; to: 0; duration: 5000; easing.type: Easing.InOutQuad }
    }
}
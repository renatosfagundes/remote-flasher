import QtQuick 2.15
import QtQuick.Window 2.15

Window {
    id: win
    width: 600; height: 300; visible: true; color: "#0c0c14"
    property real tv: 0

    PowerBar { 
        anchors.centerIn: parent; s: 1.5; value: tv
        width: 400; height: 80 
    }

    SequentialAnimation {
        running: true; loops: Animation.Infinite
        NumberAnimation { target: win; property: "tv"; from: -100; to: 300; duration: 3000 }
        NumberAnimation { target: win; property: "tv"; from: 300; to: -100; duration: 2000 }
    }
}
import QtQuick 2.15
import QtQuick.Window 2.15

Window {
    id: win
    width: 500; height: 300; visible: true; color: "#0c0c14"
    property int tg: 8

    Column {
        anchors.centerIn: parent
        spacing: 50
        
        GearSelector { s: 1.5; gearValue: tg; isAutomatic: true }
        GearSelector { s: 1.5; gearValue: 3; isAutomatic: false }
    }

    SequentialAnimation {
        running: true; loops: Animation.Infinite
        NumberAnimation { target: win; property: "tg"; from: 7; to: 8; duration: 1500 }
        NumberAnimation { target: win; property: "tg"; from: 8; to: 0; duration: 1500 }
        NumberAnimation { target: win; property: "tg"; from: 0; to: -1; duration: 1500 }
        NumberAnimation { target: win; property: "tg"; from: -1; to: 7; duration: 1500 }
    }
}
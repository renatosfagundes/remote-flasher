import QtQuick 2.15

Rectangle {
    id: root

    property string label: "INFO"
    property string value: "0"
    property string units: ""
    property color accentColor: "#3498db"

    implicitWidth: 140
    implicitHeight: 60
    radius: 8
    color: "#12122a"
    border.color: "#1a3a5a"
    border.width: 1

    // Top accent line
    Rectangle {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 1
        height: 2
        radius: 1
        color: root.accentColor
        opacity: 0.6
    }

    Column {
        anchors.centerIn: parent
        spacing: 2

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.label
            font.pixelSize: 10
            font.bold: true
            color: "#667"
            font.capitalization: Font.AllUppercase
            font.letterSpacing: 1
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 4
            Text {
                text: root.value
                font.pixelSize: 22
                font.bold: true
                color: root.accentColor
            }
            Text {
                text: root.units
                font.pixelSize: 11
                color: "#888"
                anchors.baseline: parent.children[0].baseline
            }
        }
    }
}

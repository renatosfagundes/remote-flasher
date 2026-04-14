import QtQuick 2.15

Item {
    id: root

    property string label: "STATUS"
    property bool active: false
    property color onColor: "#2ecc71"
    property color offColor: "#333"

    implicitWidth: 60
    implicitHeight: 50

    Column {
        anchors.centerIn: parent
        spacing: 4

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: 18; height: 18; radius: 9
            color: root.active ? root.onColor : root.offColor
            border.color: Qt.darker(root.active ? root.onColor : "#555", 1.3)
            border.width: 1

            // Glow effect when active
            Rectangle {
                visible: root.active
                anchors.centerIn: parent
                width: 26; height: 26; radius: 13
                color: "transparent"
                border.color: root.onColor
                border.width: 1
                opacity: 0.4
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.label
            font.pixelSize: 9
            font.bold: true
            color: root.active ? "#ccc" : "#666"
            font.capitalization: Font.AllUppercase
        }
    }
}

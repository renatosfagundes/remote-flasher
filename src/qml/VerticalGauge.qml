import QtQuick 2.15

Item {
    id: root

    property real value: 0
    property real minValue: 0
    property real maxValue: 100
    property string label: ""
    property string units: ""
    property color barColor: "#3498db"
    property real warningThreshold: -1

    implicitWidth: 65
    implicitHeight: 160

    readonly property real _fraction: maxValue > minValue
                                       ? Math.max(0, Math.min(1, (value - minValue) / (maxValue - minValue)))
                                       : 0
    readonly property real _warnFrac: warningThreshold >= 0 && maxValue > minValue
                                       ? (warningThreshold - minValue) / (maxValue - minValue)
                                       : 1.0

    // Label
    Text {
        id: labelText
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        text: root.label
        font.pixelSize: Math.max(10, root.height * 0.07)
        font.bold: true
        color: "#ccc"
    }

    // Bar track
    Rectangle {
        id: track
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.horizontalCenterOffset: 6
        anchors.top: labelText.bottom
        anchors.topMargin: 4
        anchors.bottom: valueText.top
        anchors.bottomMargin: 4
        width: 14
        radius: 3
        color: "#12122a"
        border.color: "#333"
        border.width: 1

        // Fill
        Rectangle {
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width - 4
            height: Math.max(0, (parent.height - 4) * _fraction)
            anchors.bottomMargin: 2
            radius: 2

            gradient: Gradient {
                GradientStop { position: 0.0; color: _fraction > _warnFrac ? "#ff4444" : Qt.lighter(barColor, 1.2) }
                GradientStop { position: 1.0; color: _fraction > _warnFrac ? "#cc2222" : barColor }
            }

            Behavior on height {
                NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
            }
        }

        // Scale ticks on left side
        Repeater {
            model: 6
            Rectangle {
                x: -7
                y: track.height - (track.height * index / 5) - 0.5
                width: 5; height: 1
                color: "#555"
            }
        }

        // High/Low labels
        Text {
            anchors.right: parent.left
            anchors.rightMargin: 8
            anchors.top: parent.top
            text: root.label === "Fuel" ? "E" : "C"
            font.pixelSize: 9; font.bold: true; color: "#666"
        }
        Text {
            anchors.right: parent.left
            anchors.rightMargin: 8
            anchors.bottom: parent.bottom
            text: root.label === "Fuel" ? "F" : "H"
            font.pixelSize: 9; font.bold: true; color: "#666"
        }
    }

    // Value + units
    Column {
        id: valueText
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        spacing: 0

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.value.toFixed(root.maxValue >= 100 ? 0 : 1)
            font.pixelSize: Math.max(11, root.height * 0.075)
            font.bold: true
            color: _fraction > _warnFrac ? "#ff4444" : "#fff"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.units
            font.pixelSize: Math.max(8, root.height * 0.05)
            color: "#888"
        }
    }
}

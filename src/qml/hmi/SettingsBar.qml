import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

/* Thin mode-selector bar at the top of the dashboard. */
Item {
    id: bar
    property int currentMode: 0
    signal modeSelected(int mode)
    property real s: 1.0  // set by parent

    Rectangle { anchors.fill: parent; color: "#161616"; opacity: 0.9 }

    Row {
        anchors.centerIn: parent
        spacing: 12 * bar.s

        Repeater {
            model: [
                { label: "Electric",  icon: "\u26A1" },
                { label: "Auto",      icon: "\u2699" },
                { label: "Manual",    icon: "\u2699" }
            ]

            Rectangle {
                width: Math.max(80, 130 * bar.s); height: Math.max(22, 28 * bar.s)
                radius: 4 * bar.s
                color: bar.currentMode === index ? "#01E6DE" : "#333"
                border.color: bar.currentMode === index ? "#01E6DE" : "#555"
                border.width: 1

                Label {
                    anchors.centerIn: parent
                    text: modelData.icon + " " + modelData.label
                    font.pixelSize: Math.max(9, 13 * bar.s)
                    font.family: "sans-serif"
                    color: bar.currentMode === index ? "#000" : "#ccc"
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: bar.modeSelected(index)
                }
            }
        }
    }

    Label {
        id: clock
        anchors { right: parent.right; rightMargin: 15 * bar.s; verticalCenter: parent.verticalCenter }
        font.pixelSize: Math.max(10, 16 * bar.s); font.family: "sans-serif"; color: "#aaa"
        text: Qt.formatDateTime(new Date(), "hh:mm  dd/MM/yyyy")
        Timer { interval: 1000; running: true; repeat: true; onTriggered: clock.text = Qt.formatDateTime(new Date(), "hh:mm  dd/MM/yyyy") }
    }
}

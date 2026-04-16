// test_radial_only.qml — only the Python RadialBar (QQuickPaintedItem)
import QtQuick 2.15
import CustomControls 1.0
Item {
    Rectangle { anchors.fill: parent; color: "#0c0c14" }
    RadialBar {
        anchors.centerIn: parent; width: 400; height: 400
        penStyle: Qt.RoundCap; dialType: 2
        progressColor: "#01E4E0"; backgroundColor: "transparent"
        dialWidth: 17
        startAngle: 270; spanAngle: 3.6 * value
        minValue: 0; maxValue: 100
        value: dashboard ? dashboard.battery : 71
        showText: false
    }
}

// test_one_gauge.qml — single Gauge bound to dashboard.speed
import QtQuick 2.15
Item {
    Rectangle { anchors.fill: parent; color: "#0c0c14" }
    Gauge {
        anchors.centerIn: parent
        width: 400; height: 400; s: 1.0
        value: dashboard ? dashboard.speed : 0
        maximumValue: 250; labelStepSize: 20; minorTickStep: 10
        unitLabel: "km/h"; redZoneStart: -1
    }
}

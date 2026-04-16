// test_two_minigauges.qml — only the 2 MiniGauges (TEMP + FUEL)
import QtQuick 2.15
Item {
    Rectangle { anchors.fill: parent; color: "#0c0c14" }
    Row {
        anchors.centerIn: parent; spacing: 200
        MiniGauge {
            label: "TEMP"; units: "°C"; minValue: 0; maxValue: 130
            barColor: "#3498db"; dangerAbove: 100
            value: dashboard ? dashboard.coolantTemp : 25
            s: 1.0
        }
        MiniGauge {
            label: "FUEL"; units: "%"; minValue: 0; maxValue: 100
            barColor: "#f39c12"; dangerBelow: 15
            value: dashboard ? dashboard.fuelLevel : 50
            s: 1.0
        }
    }
}

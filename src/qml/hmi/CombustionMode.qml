import QtQuick 2.15
import QtQuick.Controls 2.15

/* Combustion dashboard — gauges fill the full height like a real cluster. */
Item {
    id: cm
    property real s: 1.0
    property bool isAutomatic: true

    Rectangle { anchors.fill: parent; color: "#0c0c14" }

    // Gauges fill the FULL available height
    readonly property real gaugeSize: height * 0.98

    // ── RPM gauge (left, fills height) ────────────────────────────
    Gauge {
        id: rpmGauge
        s: cm.s
        width: cm.gaugeSize; height: width
        anchors {
            verticalCenter: parent.verticalCenter
            horizontalCenter: parent.horizontalCenter
            horizontalCenterOffset: -width * 0.42
        }
        value: dashboard ? dashboard.rpm : 0
        maximumValue: 8000; labelStepSize: 1000; minorTickStep: 500
        unitLabel: "x1000"; accentColor: "#3498db"; redZoneStart: 6500
        Behavior on value { NumberAnimation { duration: 400 } }
    }

    // ── Speed gauge (right, fills height) ─────────────────────────
    Gauge {
        id: speedGauge
        s: cm.s
        width: cm.gaugeSize; height: width
        anchors {
            verticalCenter: parent.verticalCenter
            horizontalCenter: parent.horizontalCenter
            horizontalCenterOffset: width * 0.42
        }
        value: dashboard ? dashboard.speed : 0
        maximumValue: 220; labelStepSize: 20; minorTickStep: 10
        unitLabel: "km/h"; accentColor: "#01E6DE"; redZoneStart: -1
        Behavior on value { NumberAnimation { duration: 600 } }
    }

    // ── Centre overlay (in the gap between gauges) ────────────────
    Column {
        anchors.centerIn: parent
        spacing: 6 * cm.s
        z: 10  // on top of gauges

        GearSelector {
            s: cm.s * 0.9
            gearValue: dashboard ? dashboard.gear : 7
            isAutomatic: cm.isAutomatic
            anchors.horizontalCenter: parent.horizontalCenter
        }

        // Odometer
        Rectangle {
            width: 120 * cm.s; height: 34 * cm.s
            color: "#0a0a18"; radius: 4 * cm.s
            border.color: "#252540"; border.width: 1
            anchors.horizontalCenter: parent.horizontalCenter
            Column {
                anchors.centerIn: parent
                Text {
                    text: (dashboard ? dashboard.distance : 0).toFixed(0) + " km"
                    font.pixelSize: Math.max(9, 12 * cm.s); font.family: "Consolas"; font.bold: true
                    color: "#bbb"; anchors.horizontalCenter: parent.horizontalCenter
                }
                Text {
                    text: (dashboard ? dashboard.speed : 0).toFixed(0) + " km/h"
                    font.pixelSize: Math.max(7, 9 * cm.s); font.family: "Consolas"
                    color: "#666"; anchors.horizontalCenter: parent.horizontalCenter
                }
            }
        }

        // Warning icons
        Row {
            spacing: 1
            anchors.horizontalCenter: parent.horizontalCenter
            WarningIcons { iconType: "engine";  iconColor: "#FF9F00"; active: false; s: cm.s * 0.22 }
            WarningIcons { iconType: "oil";     iconColor: "#FF3B30"; active: false; s: cm.s * 0.22 }
            WarningIcons { iconType: "battery"; iconColor: "#FF3B30"; active: false; s: cm.s * 0.22 }
            WarningIcons { iconType: "brake";   iconColor: "#FF3B30"; active: false; s: cm.s * 0.22 }
            WarningIcons { iconType: "abs";     iconColor: "#FF9F00"; active: false; s: cm.s * 0.22 }
            WarningIcons { iconType: "airbag";  iconColor: "#FF3B30"; active: false; s: cm.s * 0.22 }
        }
    }

    // ── Temp readout (bottom-left, overlaid on RPM gauge edge) ────
    Column {
        z: 10
        anchors { left: parent.left; leftMargin: 15 * cm.s; bottom: parent.bottom; bottomMargin: 10 * cm.s }
        Text {
            text: (dashboard ? dashboard.coolantTemp : 25).toFixed(0) + "\u00B0C"
            font.pixelSize: Math.max(10, 14 * cm.s); font.family: "Consolas"; font.bold: true
            color: (dashboard && dashboard.coolantTemp > 100) ? "#FF3B3B" : "#3498db"
        }
        Text { text: "TEMP"; font.pixelSize: Math.max(7, 8 * cm.s); font.family: "sans-serif"; color: "#555" }
    }

    // ── Fuel readout (bottom-right, overlaid on Speed gauge edge) ─
    Column {
        z: 10
        anchors { right: parent.right; rightMargin: 15 * cm.s; bottom: parent.bottom; bottomMargin: 10 * cm.s }
        Text {
            text: (dashboard ? dashboard.fuelLevel : 50).toFixed(0) + "%"
            font.pixelSize: Math.max(10, 14 * cm.s); font.family: "Consolas"; font.bold: true
            color: (dashboard && dashboard.fuelLevel < 15) ? "#FF3B3B" : "#f39c12"
            anchors.right: parent.right
        }
        Text { text: "FUEL"; font.pixelSize: Math.max(7, 8 * cm.s); font.family: "sans-serif"; color: "#555"; anchors.right: parent.right }
    }
}

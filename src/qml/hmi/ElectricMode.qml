import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import CustomControls 1.0

/* Electric vehicle dashboard — speed gauge centre, battery left, info right. */
Item {
    id: ev
    property real s: 1.0

    Rectangle { anchors.fill: parent; color: "#0c0c14" }

    readonly property real gaugeSize: Math.min(height * 0.78, width * 0.36)

    // ── Speed gauge (centre) ──────────────────────────────────────
    Gauge {
        id: speedGauge
        s: ev.s
        width: ev.gaugeSize; height: width
        value: dashboard ? dashboard.speed : 0
        maximumValue: 250; labelStepSize: 20; minorTickStep: 10
        unitLabel: "km/h"; redZoneStart: -1
        Behavior on value { NumberAnimation { duration: 600 } }
        anchors { horizontalCenter: parent.horizontalCenter; verticalCenter: parent.verticalCenter; verticalCenterOffset: -20 * ev.s }
    }

    // ── Power bar (below speed gauge) ─────────────────────────────
    PowerBar {
        s: ev.s
        width: speedGauge.width * 0.75; height: 45 * ev.s
        value: dashboard ? dashboard.power : 0
        anchors { horizontalCenter: parent.horizontalCenter; top: speedGauge.bottom; topMargin: 5 * ev.s }
    }

    // ── Battery radial (left) ─────────────────────────────────────
    RadialBar {
        id: batBar
        width: ev.gaugeSize * 0.55; height: width
        anchors { verticalCenter: speedGauge.verticalCenter; left: parent.left; leftMargin: parent.width * 0.05 }
        penStyle: Qt.RoundCap; dialType: 2
        progressColor: "#01E4E0"; backgroundColor: "transparent"
        dialWidth: Math.max(5, width * 0.06)
        startAngle: 270; spanAngle: 3.6 * value
        minValue: 0; maxValue: 100
        value: dashboard ? dashboard.battery : 71
        showText: false; suffixText: ""; textColor: "#FFFFFF"
        Behavior on value { NumberAnimation { duration: 800 } }

        Column {
            anchors.centerIn: parent
            Text {
                text: batBar.value.toFixed(0) + "%"
                font.pixelSize: Math.max(16, batBar.width * 0.22)
                font.family: "Consolas"; font.bold: true; color: "#fff"
                anchors.horizontalCenter: parent.horizontalCenter
            }
            Text {
                text: "Battery"
                font.pixelSize: Math.max(9, batBar.width * 0.10)
                font.family: "sans-serif"; color: "#aaa"
                anchors.horizontalCenter: parent.horizontalCenter
            }
        }
    }

    // ── Info panel (right) ────────────────────────────────────────
    Column {
        spacing: 18 * ev.s
        anchors { verticalCenter: speedGauge.verticalCenter; right: parent.right; rightMargin: parent.width * 0.05 }

        Row {
            spacing: 10 * ev.s
            Image { width: 32 * ev.s; height: 24 * ev.s; source: "assets/road.svg"; fillMode: Image.PreserveAspectFit; anchors.verticalCenter: parent.verticalCenter }
            Column {
                Text { text: (dashboard ? dashboard.rangeKm : 188).toFixed(0) + " km"; font.pixelSize: Math.max(11, 18 * ev.s); font.family: "Consolas"; font.bold: true; color: "#fff" }
                Text { text: "Range"; font.pixelSize: Math.max(8, 11 * ev.s); font.family: "sans-serif"; color: "#888" }
            }
        }
        Row {
            spacing: 10 * ev.s
            Image { width: 32 * ev.s; height: 32 * ev.s; source: "assets/speedometer.svg"; fillMode: Image.PreserveAspectFit; anchors.verticalCenter: parent.verticalCenter }
            Column {
                Text { text: (dashboard ? dashboard.avgSpeed : 0).toFixed(0) + " km/h"; font.pixelSize: Math.max(11, 18 * ev.s); font.family: "Consolas"; font.bold: true; color: "#fff" }
                Text { text: "Avg. Speed"; font.pixelSize: Math.max(8, 11 * ev.s); font.family: "sans-serif"; color: "#888" }
            }
        }
        Row {
            spacing: 10 * ev.s
            Image { width: 32 * ev.s; height: 24 * ev.s; source: "assets/road.svg"; fillMode: Image.PreserveAspectFit; anchors.verticalCenter: parent.verticalCenter }
            Column {
                Text { text: (dashboard ? dashboard.distance : 0).toFixed(0) + " km"; font.pixelSize: Math.max(11, 18 * ev.s); font.family: "Consolas"; font.bold: true; color: "#fff" }
                Text { text: "Distance"; font.pixelSize: Math.max(8, 11 * ev.s); font.family: "sans-serif"; color: "#888" }
            }
        }
    }

    // ── Warning lights (bottom-left) ──────────────────────────────
    Row {
        spacing: 2 * ev.s
        anchors { left: parent.left; leftMargin: parent.width * 0.05; bottom: parent.bottom; bottomMargin: 8 * ev.s }

        WarningIcons { iconType: "engine";  iconColor: "#FF9F00"; active: false; s: ev.s * 0.3 }
        WarningIcons { iconType: "battery"; iconColor: "#FF3B30"; active: false; s: ev.s * 0.3 }
        WarningIcons { iconType: "brake";   iconColor: "#FF3B30"; active: false; s: ev.s * 0.3 }
    }
}

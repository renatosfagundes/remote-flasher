import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

/*
  Adaptive car dashboard shell.
  Switches between Electric / Combustion Auto / Combustion Manual.
  Bottom bar: door status + speed readout + gear selector.
  All null-safe: dashboard ? dashboard.X : default
*/
Rectangle {
    id: root
    color: "#0c0c14"

    readonly property real sx: width  / 1200
    readonly property real sy: height / 650
    readonly property real s:  Math.min(sx, sy)

    // ── Settings bar (top) ────────────────────────────────────────
    SettingsBar {
        id: settingsBar
        s: root.s
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: Math.max(28, 36 * root.s)
        currentMode: dashboard ? dashboard.vehicleMode : 1
        onModeSelected: function(mode) {
            if (dashboard) dashboard.setVehicleMode(mode)
        }
    }

    // ── Mode content area ─────────────────────────────────────────
    StackLayout {
        id: modeStack
        currentIndex: dashboard ? dashboard.vehicleMode : 1
        anchors {
            top: settingsBar.bottom
            left: parent.left; right: parent.right
            bottom: bottomBar.top
        }

        ElectricMode         { s: root.s }
        CombustionAutoMode   { s: root.s }
        CombustionManualMode { s: root.s }
    }

    // ── Bottom bar ────────────────────────────────────────────────
    Rectangle {
        id: bottomBar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: Math.max(50, 70 * root.s)
        color: "#080810"

        // Door status (left)
        DoorStatus {
            s: root.s * 0.35
            anchors { verticalCenter: parent.verticalCenter; left: parent.left; leftMargin: 15 * root.s }
            doorFL: dashboard ? dashboard.doorFL : false
            doorFR: dashboard ? dashboard.doorFR : false
            doorRL: dashboard ? dashboard.doorRL : false
            doorRR: dashboard ? dashboard.doorRR : false
            trunk:  dashboard ? dashboard.trunk  : false
            hood:   dashboard ? dashboard.hood   : false
        }

        // Speed readout (centre)
        Text {
            anchors.centerIn: parent
            text: (dashboard ? dashboard.speed : 0).toFixed(0) + " km/h"
            font.pixelSize: Math.max(14, 22 * root.s)
            font.family: "Consolas"; font.bold: true
            color: "#01E6DE"
        }

        // Gear selector (right)
        GearSelector {
            s: root.s * 0.8
            gearValue: dashboard ? dashboard.gear : 7
            isAutomatic: dashboard ? (dashboard.vehicleMode !== 2) : true
            anchors { right: parent.right; rightMargin: 15 * root.s; verticalCenter: parent.verticalCenter }
        }
    }
}

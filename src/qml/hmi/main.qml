import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

/*
  Adaptive car dashboard shell.
  Modes are always laid out at their native 1200×650, then uniformly
  scaled to fit the available window — no RowLayout sizing issues.
  Bottom bar: speed readout + gear selector.
*/
Rectangle {
    id: root
    color: "#0c0c14"

    // Scale factor for the thin top/bottom bars (responsive)
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
    // Modes render at a fixed 1200×650 canvas (s=1) and are uniformly
    // scaled to fit the available space. This avoids all Layout sizing
    // fights — the modes always see the same coordinate space.
    Item {
        id: modeArea
        clip: true
        anchors {
            top: settingsBar.bottom
            left: parent.left; right: parent.right
            bottom: bottomBar.top
        }

        Item {
            id: scaler
            width: 1200; height: 650
            anchors.centerIn: parent
            scale: Math.min(modeArea.width / 1200, modeArea.height / 650)

            StackLayout {
                id: modeStack
                anchors.fill: parent
                currentIndex: dashboard ? dashboard.vehicleMode : 1

                ElectricMode         { }
                CombustionAutoMode   { }
                CombustionManualMode { }
            }
        }
    }

    // ── Bottom bar ────────────────────────────────────────────────
    Rectangle {
        id: bottomBar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: Math.max(50, 70 * root.s)
        color: "#080810"

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

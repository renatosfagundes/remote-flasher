// CombustionAutoMode.qml
import QtQuick 2.15
import QtQuick.Layouts 1.15

Item {
    id: root
    property real s: 1.0 // Scale factor

    width: 1200 * s
    height: 650 * s

    Rectangle {
        anchors.fill: parent
        color: "#101616" // Dark background
        radius: 10 * s
        border.color: "#252540"
        border.width: 1 * s
    }

    // Turn-signal indicators flanking the top edges
    StatusLight {
        id: turnLeftSignal
        s: root.s; iconSize: 72 * root.s
        anchors.left: parent.left
        anchors.verticalCenter: statusRow.verticalCenter
        anchors.verticalCenterOffset: 14 * s
        anchors.leftMargin: 24 * s
        active: dashboard ? dashboard.turnLeft : false
        activeSvg: "assets/turn_left_active.svg"
        inactiveSvg: "assets/turn_left_inactive.svg"
        z: 5
    }
    StatusLight {
        id: turnRightSignal
        s: root.s; iconSize: 72 * root.s
        anchors.right: parent.right
        anchors.verticalCenter: statusRow.verticalCenter
        anchors.verticalCenterOffset: 14 * s
        anchors.rightMargin: 24 * s
        active: dashboard ? dashboard.turnRight : false
        activeSvg: "assets/turn_right_active.svg"
        inactiveSvg: "assets/turn_right_inactive.svg"
        z: 5
    }

    // Top status-light row — wide spacing so the row spans most of the
    // width between the two big turn signals.
    Row {
        id: statusRow
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 18 * s
        spacing: 80 * s
        z: 5
        property real iSize: 40 * root.s

        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.parkingLights : false
            activeSvg: "assets/Parking lights.svg"
            inactiveSvg: "assets/Parking_lights_white.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.lowBeam : false
            activeSvg: "assets/Low beam headlights.svg"
            inactiveSvg: "assets/Low_beam_headlights_white.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.highBeam : false
            activeSvg: "assets/high_beam_active.svg"
            inactiveSvg: "assets/high_beam_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.fogLights : false
            activeSvg: "assets/Rare_fog_lights_red.svg"
            inactiveSvg: "assets/Rare fog lights.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.cruiseActive : false
            activeSvg: "assets/cruise_control_active.svg"
            inactiveSvg: "assets/cruise_control_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.seatbeltUnbuckled : false
            activeSvg: "assets/FirstRightIcon.svg"
            inactiveSvg: "assets/FirstRightIcon_grey.svg"
        }
    }

    // Main layout: small elements fixed-width, gauges fill remaining space
    RowLayout {
        anchors.top: turnLeftSignal.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.topMargin: 8 * s
        anchors.leftMargin: 20 * s
        anchors.rightMargin: 20 * s
        anchors.bottomMargin: 20 * s
        spacing: 6 * s

        MiniGauge {
            id: tempMiniGauge
            Layout.preferredWidth: 110 * root.s
            Layout.fillHeight: true
            label: "TEMP"; units: "°C"
            minValue: 0; maxValue: 130
            barColor: "#3498db"; dangerAbove: 100
            value: dashboard ? dashboard.coolantTemp : 25
            s: root.s
        }

        Gauge {
            id: rpmGauge
            s: root.s
            // RPM is the *secondary* gauge — sized so it ends up ~70% of the
            // speed gauge. Bound to the RowLayout width directly (NOT to
            // speedGauge.width) to avoid a Layout polish cycle.
            Layout.preferredWidth: 300 * root.s
            Layout.fillHeight: true
            value: dashboard ? dashboard.rpm : 0
            maximumValue: 8000; labelStepSize: 2000; minorTickStep: 1000
            unitLabel: "x1000"; accentColor: "#3498db"; redZoneStart: 6500
            // Display value as e.g. "1.0" rather than "1023" so the centre
            // text doesn't overlap the gauge ticks.
            displayDivisor: 1000; decimals: 1
            // DISABLED for perf test: Behavior on value { NumberAnimation { duration: 400 } }
        }

        // Centre VERTICAL column: Gear Selector + Odometer
        ColumnLayout {
            Layout.preferredWidth: 220 * root.s
            Layout.fillHeight: true
            spacing: 12 * s

            Item { Layout.fillHeight: true }  // top spacer (centres content)

            // Horizontal P/R/N/D gear selector
            Rectangle {
                id: gearSelectorBox
                // If the incoming gear isn't P/R/N/D, fall back to N so
                // auto always shows at least one gear lit.
                readonly property int rawGear: dashboard ? dashboard.gear : 7
                readonly property int currentGear:
                    (rawGear === 7 || rawGear === -1 || rawGear === 0 || rawGear === 8)
                        ? rawGear : 0
                Layout.preferredWidth: 200 * root.s
                Layout.preferredHeight: 56 * root.s
                Layout.alignment: Qt.AlignHCenter
                color: "#0a0a18"; radius: 8 * root.s
                border.color: "#252540"; border.width: 1

                Row {
                    anchors.centerIn: parent
                    spacing: 18 * root.s

                    Repeater {
                        model: [
                            { t: "P", v: 7 },
                            { t: "R", v: -1 },
                            { t: "N", v: 0 },
                            { t: "D", v: 8 }
                        ]

                        Text {
                            text: modelData.t
                            font.pixelSize: 28 * root.s
                            font.family: "Consolas"; font.bold: true
                            color: (gearSelectorBox.currentGear === modelData.v) ? "#01E6DE" : "#444"
                            Behavior on color { ColorAnimation { duration: 200 } }
                        }
                    }
                }
            }

            // Bigger, prominent odometer directly below
            Rectangle {
                Layout.preferredWidth: 200 * root.s
                Layout.preferredHeight: 56 * root.s
                Layout.alignment: Qt.AlignHCenter
                color: "#0a0a18"; radius: 8 * root.s
                border.color: "#252540"; border.width: 1

                Column {
                    anchors.centerIn: parent
                    spacing: 2 * root.s
                    Text {
                        text: (dashboard ? dashboard.distance : 0).toFixed(0) + " km"
                        font.pixelSize: 22 * root.s
                        font.family: "Consolas"; font.bold: true; color: "#bbb"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text {
                        text: "ODOMETER"
                        font.pixelSize: 10 * root.s
                        font.family: "sans-serif"; color: "#555"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }
            }

            // Top-down car silhouette with door / hood / trunk indicators
            DoorStatus {
                id: doorStatus
                s: root.s
                Layout.preferredWidth: 120 * root.s
                Layout.preferredHeight: 190 * root.s
                Layout.alignment: Qt.AlignHCenter
                doorFL: dashboard ? dashboard.doorFL : false
                doorFR: dashboard ? dashboard.doorFR : false
                doorRL: dashboard ? dashboard.doorRL : false
                doorRR: dashboard ? dashboard.doorRR : false
                hood:   dashboard ? dashboard.hood   : false
                trunk:  dashboard ? dashboard.trunk  : false
            }

            Item { Layout.fillHeight: true }  // bottom spacer
        }

        Gauge {
            id: speedGauge
            s: root.s
            Layout.fillWidth: true
            Layout.fillHeight: true
            value: dashboard ? dashboard.speed : 0
            maximumValue: 220; labelStepSize: 40; minorTickStep: 20
            unitLabel: "km/h"; accentColor: "#01E6DE"; redZoneStart: -1
        }

        MiniGauge {
            id: fuelMiniGauge
            Layout.preferredWidth: 110 * root.s
            Layout.fillHeight: true
            label: "FUEL"; units: "%"
            minValue: 0; maxValue: 100
            barColor: "#f39c12"; dangerBelow: 15
            value: dashboard ? dashboard.fuelLevel : 50
            s: root.s
        }
    }

    // Peripheral element anchors (placed outside of RowLayout to avoid moving main gauges)

    // Row of warnings at the bottom centre — Canvas-drawn critical icons +
    // SVG-based service / tire / door / traction-control indicators.
    Row {
        id: warningIcons
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 15 * root.s
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 18 * root.s

        WarningIcons { iconType: "engine";  iconColor: "#FF9F00"; active: dashboard ? dashboard.checkEngine : false; s: root.s * 0.9 }
        WarningIcons { iconType: "oil";     iconColor: "#FF3B30"; active: dashboard ? dashboard.oilPressure : false; s: root.s * 0.9 }
        WarningIcons { iconType: "battery"; iconColor: "#FF3B30"; active: dashboard ? dashboard.batteryWarn : false; s: root.s * 0.9 }
        WarningIcons { iconType: "brake";   iconColor: "#FF3B30"; active: dashboard ? dashboard.brakeWarn   : false; s: root.s * 0.9 }
        WarningIcons { iconType: "abs";     iconColor: "#FF9F00"; active: dashboard ? dashboard.absWarn     : false; s: root.s * 0.9 }
        WarningIcons { iconType: "airbag";  iconColor: "#FF3B30"; active: dashboard ? dashboard.airbagWarn  : false; s: root.s * 0.9 }

        StatusLight {
            s: root.s; iconSize: 36 * root.s
            anchors.verticalCenter: parent.verticalCenter
            active: dashboard ? dashboard.tirePressure : false
            activeSvg: "assets/tire_pressure_active.svg"
            inactiveSvg: "assets/tire_pressure_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: 36 * root.s
            anchors.verticalCenter: parent.verticalCenter
            active: dashboard ? dashboard.doorOpen : false
            activeSvg: "assets/door_open_active.svg"
            inactiveSvg: "assets/door_open_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: 36 * root.s
            anchors.verticalCenter: parent.verticalCenter
            active: dashboard ? dashboard.tractionControl : false
            activeSvg: "assets/traction_control_active.svg"
            inactiveSvg: "assets/traction_control_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: 36 * root.s
            anchors.verticalCenter: parent.verticalCenter
            active: dashboard ? dashboard.serviceDue : false
            activeSvg: "assets/service_active.svg"
            inactiveSvg: "assets/service_inactive.svg"
        }
    }
}
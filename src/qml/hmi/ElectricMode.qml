// ElectricMode.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import CustomControls 1.0

Item {
    id: root
    property real s: 1.0

    width: 1200 * s
    height: 650 * s

    Rectangle {
        anchors.fill: parent
        color: "#101616"
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
        tooltipText: "Turn signal — left — signal: turnLeft"
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
        tooltipText: "Turn signal — right — signal: turnRight"
        activeSvg: "assets/turn_right_active.svg"
        inactiveSvg: "assets/turn_right_inactive.svg"
        z: 5
    }

    // Top status-light row — spans nearly the full width between the two
    // turn signals so the row uses the available horizontal space instead
    // of clustering tightly in the middle.
    Row {
        id: statusRow
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 18 * s
        spacing: 56 * s
        z: 5
        property real iSize: 40 * root.s

        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.parkingLights : false
            tooltipText: "Parking lights — signal: parkingLights"
            activeSvg: "assets/Parking lights.svg"
            inactiveSvg: "assets/Parking_lights_white.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.lowBeam : false
            tooltipText: "Low beam headlights — signal: lowBeam"
            activeSvg: "assets/Low beam headlights.svg"
            inactiveSvg: "assets/Low_beam_headlights_white.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.highBeam : false
            tooltipText: "High beam headlights — signal: highBeam"
            activeSvg: "assets/high_beam_active.svg"
            inactiveSvg: "assets/high_beam_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.fogLights : false
            tooltipText: "Fog lights — signal: fogLights"
            activeSvg: "assets/Rare_fog_lights_red.svg"
            inactiveSvg: "assets/Rare fog lights.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.cruiseActive : false
            tooltipText: "Cruise control — signal: cruiseActive"
            activeSvg: "assets/cruise_control_active.svg"
            inactiveSvg: "assets/cruise_control_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.ecoMode : false
            tooltipText: "Eco mode — signal: ecoMode"
            activeSvg: "assets/eco_active.svg"
            inactiveSvg: "assets/eco_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.evCharging : false
            tooltipText: "EV charging — signal: evCharging"
            activeSvg: "assets/ev_charging_active.svg"
            inactiveSvg: "assets/ev_charging_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: statusRow.iSize
            active: dashboard ? dashboard.seatbeltUnbuckled : false
            tooltipText: "Seatbelt unbuckled — signal: seatbeltUnbuckled"
            activeSvg: "assets/FirstRightIcon.svg"
            inactiveSvg: "assets/FirstRightIcon_grey.svg"
        }
    }

    // Bottom-centre warning row (above the PowerBar) — combines Canvas-drawn
    // critical warnings with new SVG-based ones (service, tire, door).
    Row {
        id: warningIcons
        anchors.bottom: bottomBar.top
        anchors.bottomMargin: 4 * root.s
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 18 * root.s
        z: 5

        WarningIcons { iconType: "engine"; iconColor: "#FF9F00"; active: dashboard ? dashboard.checkEngine : false; s: root.s * 0.9; tooltipText: "Check engine (MIL) — signal: checkEngine" }
        WarningIcons { iconType: "oil"; iconColor: "#FF3B30"; active: dashboard ? dashboard.oilPressure : false; s: root.s * 0.9; tooltipText: "Oil pressure — signal: oilPressure" }
        WarningIcons { iconType: "battery"; iconColor: "#FF3B30"; active: dashboard ? dashboard.batteryWarn : false; s: root.s * 0.9; tooltipText: "Battery warning — signal: batteryWarn" }
        WarningIcons { iconType: "brake"; iconColor: "#FF3B30"; active: dashboard ? dashboard.brakeWarn : false; s: root.s * 0.9; tooltipText: "Brake warning — signal: brakeWarn" }
        WarningIcons { iconType: "abs"; iconColor: "#FF9F00"; active: dashboard ? dashboard.absWarn : false; s: root.s * 0.9; tooltipText: "ABS warning — signal: absWarn" }
        WarningIcons { iconType: "airbag"; iconColor: "#FF3B30"; active: dashboard ? dashboard.airbagWarn : false; s: root.s * 0.9; tooltipText: "Airbag / SRS — signal: airbagWarn" }

        // New SVG-based warnings, sized to roughly match WarningIcons
        StatusLight {
            s: root.s; iconSize: 45 * root.s
            anchors.verticalCenter: parent.verticalCenter
            active: dashboard ? dashboard.tirePressure : false
            tooltipText: "Tire pressure (TPMS) — signal: tirePressure"
            activeSvg: "assets/tire_pressure_active.svg"
            inactiveSvg: "assets/tire_pressure_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: 45 * root.s
            anchors.verticalCenter: parent.verticalCenter
            active: dashboard ? dashboard.doorOpen : false
            tooltipText: "Door open — signal: doorOpen"
            activeSvg: "assets/door_open_active.svg"
            inactiveSvg: "assets/door_open_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: 45 * root.s
            anchors.verticalCenter: parent.verticalCenter
            active: dashboard ? dashboard.serviceDue : false
            tooltipText: "Service due — signal: serviceDue"
            activeSvg: "assets/service_active.svg"
            inactiveSvg: "assets/service_inactive.svg"
        }
    }

    // Main gauge row — battery (small left) + speed (BIG centre) + info (right)
    RowLayout {
        id: mainRow
        anchors.top: turnLeftSignal.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: warningIcons.top
        anchors.topMargin: 8 * s
        anchors.leftMargin: 20 * s
        anchors.rightMargin: 20 * s
        anchors.bottomMargin: 4 * s
        spacing: 6 * s

        // Battery — smaller, half the size of the speedometer
        RadialBar {
            id: batteryBar
            Layout.preferredWidth: 220 * root.s
            Layout.preferredHeight: 220 * root.s
            Layout.alignment: Qt.AlignVCenter
            penStyle: Qt.RoundCap
            dialType: 2
            progressColor: "#01E4E0"
            backgroundColor: "transparent"
            dialWidth: Math.max(5 * s, width * 0.06)
            startAngle: 270
            spanAngle: 3.6 * value
            minValue: 0
            maxValue: 100
            value: dashboard ? dashboard.battery : 71
            showText: false
            textColor: "#FFFFFF"
            // DISABLED for perf test: Behavior on value { NumberAnimation { duration: 800 } }

            Column {
                anchors.centerIn: parent
                spacing: 2 * root.s
                Text {
                    text: batteryBar.value.toFixed(0) + "%"
                    font.pixelSize: Math.max(22 * root.s, batteryBar.width * 0.22)
                    font.family: "Consolas"
                    font.bold: true
                    color: "#fff"
                    anchors.horizontalCenter: parent.horizontalCenter
                }
                Text {
                    text: "Battery"
                    font.pixelSize: Math.max(11 * root.s, batteryBar.width * 0.10)
                    font.family: "sans-serif"
                    color: "#aaa"
                    anchors.horizontalCenter: parent.horizontalCenter
                }
            }

            MouseArea {
                id: batteryHover
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.NoButton

                ToolTip {
                    parent: batteryHover
                    x: batteryHover.mouseX + width + 15 > batteryHover.width
                       ? batteryHover.mouseX - width - 5
                       : batteryHover.mouseX + 15
                    y: batteryHover.mouseY + 20
                    visible: batteryHover.containsMouse
                    text: "Battery state of charge — signal: battery (%)"
                    delay: 500
                }
            }
        }

        // Speed gauge — DOMINANT centre element (fills the rest)
        Gauge {
            id: speedGauge
            s: root.s
            Layout.fillWidth: true
            Layout.fillHeight: true
            value: dashboard ? dashboard.speed : 0
            tooltipText: "Vehicle speed — signal: speed (km/h)"
            maximumValue: 250; labelStepSize: 50; minorTickStep: 25
            // Red zone at 80% of max, fade from 70% → 80%.
            unitLabel: "km/h"; redZoneStart: 200; redFadeRange: 25
            odometerValue: dashboard ? dashboard.distance : 0
            odometerTooltipText: "Odometer — signal: distance (km)"
        }

        // Info column — range, distance, avg speed (right side)
        ColumnLayout {
            Layout.preferredWidth: 220 * root.s
            Layout.fillHeight: true
            spacing: 18 * s

            Item { Layout.fillHeight: true }  // top spacer

            // Range
            RowLayout {
                id: rangeRow
                Layout.alignment: Qt.AlignHCenter
                spacing: 10 * s
                Image {
                    Layout.preferredWidth: 36 * s
                    Layout.preferredHeight: 28 * s
                    source: "assets/road.svg"
                    sourceSize.width: 36 * s
                    sourceSize.height: 28 * s
                    fillMode: Image.PreserveAspectFit
                    Layout.alignment: Qt.AlignVCenter
                }
                ColumnLayout {
                    spacing: 0
                    Text {
                        text: (dashboard ? dashboard.rangeKm : 188).toFixed(0) + " km"
                        font.pixelSize: 22 * s
                        font.family: "Consolas"; font.bold: true
                        color: "#fff"
                    }
                    Text {
                        text: "Range"
                        font.pixelSize: 12 * s; font.family: "sans-serif"
                        color: "#888"
                    }
                }
                HoverHandler { id: rangeHover }
                ToolTip {
                    parent: rangeRow
                    visible: rangeHover.hovered
                    text: "Estimated range — signal: rangeKm (km)"
                    delay: 500
                }
            }

            // Distance — car silhouette to differentiate from Range
            RowLayout {
                id: distanceRow
                Layout.alignment: Qt.AlignHCenter
                spacing: 10 * s
                Image {
                    Layout.preferredWidth: 36 * s
                    Layout.preferredHeight: 28 * s
                    source: "assets/Car.svg"
                    sourceSize.width: 36 * s
                    sourceSize.height: 28 * s
                    fillMode: Image.PreserveAspectFit
                    Layout.alignment: Qt.AlignVCenter
                }
                ColumnLayout {
                    spacing: 0
                    Text {
                        text: (dashboard ? dashboard.distance : 0).toFixed(0) + " km"
                        font.pixelSize: 22 * s
                        font.family: "Consolas"; font.bold: true
                        color: "#fff"
                    }
                    Text {
                        text: "Distance"
                        font.pixelSize: 12 * s; font.family: "sans-serif"
                        color: "#888"
                    }
                }
                HoverHandler { id: distanceHover }
                ToolTip {
                    parent: distanceRow
                    visible: distanceHover.hovered
                    text: "Odometer / trip distance — signal: distance (km)"
                    delay: 500
                }
            }

            // Avg speed
            RowLayout {
                id: avgSpeedRow
                Layout.alignment: Qt.AlignHCenter
                spacing: 10 * s
                Image {
                    Layout.preferredWidth: 36 * s
                    Layout.preferredHeight: 36 * s
                    source: "assets/speedometer.svg"
                    sourceSize.width: 36 * s
                    sourceSize.height: 36 * s
                    fillMode: Image.PreserveAspectFit
                    Layout.alignment: Qt.AlignVCenter
                }
                ColumnLayout {
                    spacing: 0
                    Text {
                        text: (dashboard ? dashboard.avgSpeed : 0).toFixed(0) + " km/h"
                        font.pixelSize: 22 * s
                        font.family: "Consolas"; font.bold: true
                        color: "#fff"
                    }
                    Text {
                        text: "Avg. Speed"
                        font.pixelSize: 12 * s; font.family: "sans-serif"
                        color: "#888"
                    }
                }
                HoverHandler { id: avgSpeedHover }
                ToolTip {
                    parent: avgSpeedRow
                    visible: avgSpeedHover.hovered
                    text: "Average speed — signal: avgSpeed (km/h)"
                    delay: 500
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
    }

    // Bottom bar — just the PowerBar centred (warnings are now in corners)
    Rectangle {
        id: bottomBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 80 * s
        color: "transparent"

        PowerBar {
            id: powerBar
            s: root.s
            width: parent.width * 0.45
            height: 55 * s
            anchors.centerIn: parent
            value: dashboard ? dashboard.power : 0
            tooltipText: "Power / regen — signal: power (kW)"
            maxPower: 150
            maxRegen: 50
        }
    }
}

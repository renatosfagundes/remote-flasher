// CombustionManualMode.qml
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

    // Modified spacing and alignment within RowLayout
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

        // ADD: MiniGauge on the FAR LEFT (TEMP, same as auto)
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

        // RPM Gauge — secondary, sized so it ends up ~70% of the speed gauge.
        // Bound to the RowLayout width directly (NOT to speedGauge.width) to
        // avoid a Layout polish cycle.
        Gauge {
            id: rpmGauge
            s: root.s
            Layout.preferredWidth: 300 * root.s
            Layout.fillHeight: true
            value: dashboard ? dashboard.rpm : 0
            maximumValue: 8000; labelStepSize: 2000; minorTickStep: 1000
            unitLabel: "x1000"; accentColor: "#3498db"; redZoneStart: 6500
            displayDivisor: 1000; decimals: 1
            // DISABLED for perf test: Behavior on value { NumberAnimation { duration: 400 } }
        }

        // Centre: H-PATTERN SHIFT DIAGRAM + Odometer (Upgraded)
        ColumnLayout {
            Layout.preferredWidth: 220 * root.s
            Layout.fillHeight: true
            spacing: 10 * s // Space between diagram and odometer

            Item { Layout.fillHeight: true }  // top spacer

            // Odometer — matches auto mode size for consistency
            Rectangle {
                id: odometerBox
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

            // Big current-gear readout (between odometer and H-pattern)
            Rectangle {
                id: currentGearBox
                Layout.preferredWidth: 80 * root.s
                Layout.preferredHeight: 80 * root.s
                Layout.alignment: Qt.AlignHCenter
                color: "#0a0a18"; radius: 10 * root.s
                border.color: "#01E6DE"; border.width: 1

                Text {
                    anchors.centerIn: parent
                    // Manual transmission: only N, R, 1-6 are valid
                    text: {
                        var g = dashboard ? dashboard.gear : 0;
                        if (g === 0) return "N";
                        if (g === -1) return "R";
                        if (g >= 1 && g <= 6) return g.toString();
                        return "–";  // invalid for manual (e.g. P or D from signal)
                    }
                    font.pixelSize: 50 * root.s
                    font.family: "Consolas"; font.bold: true; color: "#01E6DE"
                }
            }

            // Fix labels overlaps, Increase spacing, Shift Diagram
            // Constrained height so the DoorStatus widget fits below it.
            Canvas {
                id: shiftCanvas
                Layout.fillWidth: true
                Layout.preferredHeight: 130 * root.s
                Layout.alignment: Qt.AlignHCenter
                // Repaint whenever the gear value changes
                Connections {
                    target: dashboard
                    ignoreUnknownSignals: true
                    function onGearChanged() { shiftCanvas.requestPaint() }
                }
                onPaint: {
                    var ctx = getContext("2d");
                    ctx.reset();
                    ctx.save();

                    // Centre diagram inside canvas space
                    var cx = width / 2;
                    var cy = height / 2;

                    ctx.lineWidth = 3 * root.s; // Dynamic width
                    ctx.strokeStyle = "rgba(255,255,255,0.4)"; // faint line
                    ctx.lineCap = "round"; // gate dimensions (Increased)

                    var gateW = 28 * root.s; // horizontal rail spacing
                    var gateH = 60 * root.s; // vertical line length
                    var railY = cy; // center

                    // Four separate gates including isolated R gate
                    var x_12 = cx - gateW * 1.5; // Left gate (1-2)
                    var x_34 = cx - gateW * 0.5; // Middle-left gate (3-4)
                    var x_56 = cx + gateW * 0.5; // Middle-right gate (5-6)
                    var x_R  = cx + gateW * 1.5; // Right isolated gate (R only)

                    // Main horizontal rail connects 1-2, 3-4, 5-6
                    ctx.beginPath();
                    ctx.moveTo(x_12, railY);
                    ctx.lineTo(x_56, railY);
                    ctx.stroke();

                    // Gate 1-2
                    ctx.beginPath();
                    ctx.moveTo(x_12, railY - gateH / 2);
                    ctx.lineTo(x_12, railY + gateH / 2);
                    ctx.stroke();

                    // Gate 3-4
                    ctx.beginPath();
                    ctx.moveTo(x_34, railY - gateH / 2);
                    ctx.lineTo(x_34, railY + gateH / 2);
                    ctx.stroke();

                    // Gate 5-6
                    ctx.beginPath();
                    ctx.moveTo(x_56, railY - gateH / 2);
                    ctx.lineTo(x_56, railY + gateH / 2);
                    ctx.stroke();

                    // Separate R gate (only top position — isolated with a gap)
                    ctx.beginPath();
                    ctx.moveTo(x_R, railY);
                    ctx.lineTo(x_R, railY - gateH / 2);
                    ctx.stroke();
                    // Short diagonal/horizontal connector showing R is reachable
                    ctx.beginPath();
                    ctx.moveTo(x_56, railY);
                    ctx.lineTo(x_R, railY);
                    ctx.stroke();

                    // Labels
                    ctx.font = (16 * root.s) + "px sans-serif";
                    ctx.fillStyle = "#aaa";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";

                    // Top row: 1, 3, 5, R
                    ctx.fillText("1", x_12, railY - gateH / 2 - 12 * root.s);
                    ctx.fillText("3", x_34, railY - gateH / 2 - 12 * root.s);
                    ctx.fillText("5", x_56, railY - gateH / 2 - 12 * root.s);
                    ctx.fillText("R", x_R,  railY - gateH / 2 - 12 * root.s);

                    // Bottom row: 2, 4, 6 (no R at bottom)
                    ctx.fillText("2", x_12, railY + gateH / 2 + 12 * root.s);
                    ctx.fillText("4", x_34, railY + gateH / 2 + 12 * root.s);
                    ctx.fillText("6", x_56, railY + gateH / 2 + 12 * root.s);

                    // N label at the centre of the rail (between 3-4 and 5-6 gates)
                    ctx.fillText("N", (x_34 + x_56) / 2, railY + 14 * root.s);

                    // Highlight logic — N lights up on the rail centre;
                    // P and D are invalid for manual, so we draw nothing for them.
                    var currentGear = dashboard ? dashboard.gear : 0;
                    if (currentGear === 0) {
                        // N at rail centre (between 3-4 and 5-6)
                        var nx = (x_34 + x_56) / 2;
                        var ny = railY;
                        ctx.shadowBlur = 15 * root.s;
                        ctx.shadowColor = "#01E6DE";
                        ctx.fillStyle = "#01E6DE";
                        ctx.beginPath();
                        ctx.arc(nx, ny, 6 * root.s, 0, 2 * Math.PI);
                        ctx.fill();
                        ctx.shadowBlur = 0;
                    } else if (currentGear !== 7 && currentGear !== 8) { // Not N, P, or D
                        var px = cx;
                        var py = cy;
                        switch (currentGear) {
                            case -1: px = x_R; py = railY - gateH / 2; break; // R top-right (isolated gate)
                            case 1: px = x_12; py = railY - gateH / 2; break; // 1 top-left
                            case 2: px = x_12; py = railY + gateH / 2; break; // 2 bottom-left
                            case 3: px = x_34; py = railY - gateH / 2; break; // 3 top-middle
                            case 4: px = x_34; py = railY + gateH / 2; break; // 4 bottom-middle
                            case 5: px = x_56; py = railY - gateH / 2; break; // 5 top-right
                            case 6: px = x_56; py = railY + gateH / 2; break; // 6 bottom-right
                        }

                        // Glow effect
                        ctx.shadowBlur = 15 * root.s;
                        ctx.shadowColor = "#01E6DE";
                        ctx.fillStyle = "#01E6DE"; // Glow color

                        // Cyan filled dot
                        ctx.beginPath(); // center hub logic reference
                        ctx.arc(px, py, 6 * root.s, 0, 2 * Math.PI); // scaled radius
                        ctx.fill();
                    }

                    ctx.restore();
                }
            }

            // NOTE: currentGearBox is now placed earlier in the column
            // (see above the Canvas H-pattern) using Layout.alignment.

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

            // Spacer for RowLayout balance
            Item { Layout.fillHeight: true }
        }

        // Speed Gauge
        Gauge {
            id: speedGauge
            s: root.s
            Layout.fillWidth: true
            Layout.fillHeight: true
            value: dashboard ? dashboard.speed : 0
            maximumValue: 220; labelStepSize: 40; minorTickStep: 20
            unitLabel: "km/h"; accentColor: "#01E6DE"; redZoneStart: -1 // redZoneStart is -1
            // DISABLED for perf test: Behavior on value { NumberAnimation { duration: 600 } }
        }

        // ADD: MiniGauge on the FAR RIGHT (FUEL, same as auto)
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

    // Bottom warning row — split into left and right clusters with a gap
    // in the middle so nothing overlaps the DoorStatus car silhouette above.
    // Order: brake | engine | oil | battery | [gap] | ABS | airbag | SVG icons
    RowLayout {
        id: warningIcons
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 15 * root.s
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.horizontalCenterOffset: -27 * root.s
        spacing: 12 * root.s

        // Left cluster
        WarningIcons { iconType: "brake";   iconColor: "#FF3B30"; active: dashboard ? dashboard.brakeWarn   : false; s: root.s * 0.9 }
        WarningIcons { iconType: "engine";  iconColor: "#FF9F00"; active: dashboard ? dashboard.checkEngine : false; s: root.s * 0.9 }
        WarningIcons { iconType: "oil";     iconColor: "#FF3B30"; active: dashboard ? dashboard.oilPressure : false; s: root.s * 0.9 }
        WarningIcons { iconType: "battery"; iconColor: "#FF3B30"; active: dashboard ? dashboard.batteryWarn : false; s: root.s * 0.9 }

        // Gap to clear the DoorStatus silhouette
        Item { Layout.preferredWidth: 150 * root.s }

        // Right cluster
        WarningIcons { iconType: "abs";     iconColor: "#FF9F00"; active: dashboard ? dashboard.absWarn     : false; s: root.s * 0.9 }
        WarningIcons { iconType: "airbag";  iconColor: "#FF3B30"; active: dashboard ? dashboard.airbagWarn  : false; s: root.s * 0.9 }

        StatusLight {
            s: root.s; iconSize: 36 * root.s
            active: dashboard ? dashboard.tirePressure : false
            activeSvg: "assets/tire_pressure_active.svg"
            inactiveSvg: "assets/tire_pressure_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: 36 * root.s
            active: dashboard ? dashboard.doorOpen : false
            activeSvg: "assets/door_open_active.svg"
            inactiveSvg: "assets/door_open_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: 36 * root.s
            active: dashboard ? dashboard.tractionControl : false
            activeSvg: "assets/traction_control_active.svg"
            inactiveSvg: "assets/traction_control_inactive.svg"
        }
        StatusLight {
            s: root.s; iconSize: 36 * root.s
            active: dashboard ? dashboard.serviceDue : false
            activeSvg: "assets/service_active.svg"
            inactiveSvg: "assets/service_inactive.svg"
        }
    }
}
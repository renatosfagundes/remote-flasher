import QtQuick 2.15

Item {
    id: root
    
    // --- Properties ---
    property real value: 0
    property real minimumValue: 0
    property real maximumValue: 250
    property real minimumValueAngle: -140    // 0 degrees is 3 o'clock
    property real maximumValueAngle: 140
    property int labelStepSize: 20
    property int minorTickStep: 5
    property string unitLabel: "km/h"
    property color accentColor: "#01E6DE"
    property real redZoneStart: 200
    property real s: 1.0                    // Scale factor
    // Display formatting for the centre value (e.g. RPM 1023 with
    // displayDivisor=1000, decimals=1 → "1.0").
    property real displayDivisor: 1
    property int  decimals: 0
    // Optional odometer inside the gauge face (like a real dashboard).
    // Set to >= 0 to show; negative hides it.
    property real odometerValue: -1

    // Use implicit sizes so RowLayout can freely override via
    // Layout.preferredWidth / Layout.fillWidth without fighting a binding.
    implicitWidth: 400 * s
    implicitHeight: 400 * s

    // Internal helper for angle calculations
    readonly property real _range: maximumValue - minimumValue
    readonly property real _angleRange: maximumValueAngle - minimumValueAngle
    
    function valueToAngle(val) {
        let normalized = (val - minimumValue) / _range;
        return (minimumValueAngle + (normalized * _angleRange)) * (Math.PI / 180);
    }

    // Trigger repaint when value changes
    onValueChanged: canvas.requestPaint()

    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true
        renderTarget: Canvas.Image  // CPU-backed — avoids GPU sync stalls

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            if (width < 10 || height < 10) return;  // not yet laid out

            var centerX = width / 2;
            var centerY = height / 2;
            var radius = (Math.min(width, height) / 2) - (10 * s);
            
            // 1. Draw Outer Bevel Ring (3D effect)
            ctx.beginPath();
            var gradient = ctx.createRadialGradient(centerX, centerY, radius - (5 * s), centerX, centerY, radius);
            gradient.addColorStop(0, "#1a1a24");
            gradient.addColorStop(0.5, "#353540");
            gradient.addColorStop(1, "#050508");
            ctx.strokeStyle = gradient;
            ctx.lineWidth = 6 * s;
            ctx.arc(centerX, centerY, radius - (3 * s), 0, 2 * Math.PI);
            ctx.stroke();

            // 2. Draw Background Track
            ctx.beginPath();
            ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
            ctx.lineWidth = 12 * s;
            ctx.lineCap = "round";
            ctx.arc(centerX, centerY, radius - (25 * s), 
                    (minimumValueAngle - 90) * Math.PI / 180, 
                    (maximumValueAngle - 90) * Math.PI / 180);
            ctx.stroke();

            // 3. Draw Red Zone (if applicable)
            if (redZoneStart > 0) {
                ctx.beginPath();
                ctx.strokeStyle = "rgba(255, 30, 30, 0.4)";
                ctx.lineWidth = 12 * s;
                ctx.arc(centerX, centerY, radius - (25 * s), 
                        valueToAngle(redZoneStart) - Math.PI/2, 
                        valueToAngle(maximumValue) - Math.PI/2);
                ctx.stroke();
            }

            // 4. Draw Active "Glow" Progress Arc
            if (value > minimumValue) {
                var arcStartRad = (minimumValueAngle - 90) * Math.PI / 180;
                var arcEndRad = valueToAngle(value) - Math.PI/2;
                var arcRadius = radius - (25 * s);

                // If value is past the red zone, draw in two segments
                if (redZoneStart > 0 && value > redZoneStart) {
                    var rzRad = valueToAngle(redZoneStart) - Math.PI/2;

                    // Normal segment (up to red zone)
                    ctx.beginPath();
                    var glowGrad = ctx.createRadialGradient(centerX, centerY, radius - 35*s, centerX, centerY, radius - 15*s);
                    glowGrad.addColorStop(0, "transparent");
                    glowGrad.addColorStop(0.5, accentColor);
                    glowGrad.addColorStop(1, "transparent");
                    ctx.strokeStyle = glowGrad;
                    ctx.lineWidth = 14 * s;
                    ctx.arc(centerX, centerY, arcRadius, arcStartRad, rzRad);
                    ctx.stroke();

                    // Red segment (neon red glow)
                    ctx.beginPath();
                    var redGrad = ctx.createRadialGradient(centerX, centerY, radius - 35*s, centerX, centerY, radius - 15*s);
                    redGrad.addColorStop(0, "transparent");
                    redGrad.addColorStop(0.5, "#ff2244");
                    redGrad.addColorStop(1, "transparent");
                    ctx.strokeStyle = redGrad;
                    ctx.lineWidth = 14 * s;
                    ctx.arc(centerX, centerY, arcRadius, rzRad, arcEndRad);
                    ctx.stroke();
                } else {
                    // All within normal range
                    ctx.beginPath();
                    var glowGrad2 = ctx.createRadialGradient(centerX, centerY, radius - 35*s, centerX, centerY, radius - 15*s);
                    glowGrad2.addColorStop(0, "transparent");
                    glowGrad2.addColorStop(0.5, accentColor);
                    glowGrad2.addColorStop(1, "transparent");
                    ctx.strokeStyle = glowGrad2;
                    ctx.lineWidth = 14 * s;
                    ctx.arc(centerX, centerY, arcRadius, arcStartRad, arcEndRad);
                    ctx.stroke();
                }
            }

            // 5. Ticks and Labels — font scales with gauge size, not global s
            var tickFontPx = Math.max(9, Math.min(width, height) * 0.04);
            ctx.font = tickFontPx + "px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";

            for (var i = minimumValue; i <= maximumValue; i += minorTickStep) {
                var angle = valueToAngle(i) - Math.PI/2;
                var isMajor = (i % labelStepSize === 0);
                var innerR = radius - (isMajor ? 50 * s : 45 * s);
                var outerR = radius - (35 * s);

                // Highlight ticks if needle passed them
                ctx.strokeStyle = (i <= value) ? accentColor : "rgba(255,255,255,0.4)";
                ctx.lineWidth = (isMajor ? 3 : 1.5) * s;

                ctx.beginPath();
                ctx.moveTo(centerX + Math.cos(angle) * innerR, centerY + Math.sin(angle) * innerR);
                ctx.lineTo(centerX + Math.cos(angle) * outerR, centerY + Math.sin(angle) * outerR);
                ctx.stroke();

                if (isMajor) {
                    var labelR = radius - (70 * s);
                    ctx.fillStyle = (i <= value) ? "white" : "rgba(255,255,255,0.6)";
                    ctx.fillText(i.toString(), 
                                 centerX + Math.cos(angle) * labelR, 
                                 centerY + Math.sin(angle) * labelR);
                }
            }

            // 6. Center Hub (Bottom layer)
            ctx.beginPath();
            ctx.fillStyle = "#111118";
            ctx.arc(centerX, centerY, 25 * s, 0, 2 * Math.PI);
            ctx.fill();

            // 7. The Needle
            var needleAngle = valueToAngle(value) - Math.PI/2;
            ctx.save();
            ctx.translate(centerX, centerY);
            ctx.rotate(needleAngle);
            
            // Needle Body
            ctx.beginPath();
            var needleGrad = ctx.createLinearGradient(0, 0, radius - 40*s, 0);
            needleGrad.addColorStop(0, "white");
            needleGrad.addColorStop(1, accentColor);
            ctx.strokeStyle = needleGrad;
            ctx.lineWidth = 3 * s;
            ctx.lineCap = "round";
            ctx.moveTo(0, 0);
            ctx.lineTo(radius - 45 * s, 0);
            ctx.stroke();
            
            ctx.restore();

            // 8. Center Cap (Metal look)
            var capGrad = ctx.createLinearGradient(centerX - 15*s, centerY - 15*s, centerX + 15*s, centerY + 15*s);
            capGrad.addColorStop(0, "#888");
            capGrad.addColorStop(0.5, "#222");
            capGrad.addColorStop(1, "#000");
            ctx.beginPath();
            ctx.fillStyle = capGrad;
            ctx.arc(centerX, centerY, 12 * s, 0, 2 * Math.PI);
            ctx.fill();
            ctx.strokeStyle = "#444";
            ctx.lineWidth = 1 * s;
            ctx.stroke();
        }
    }

    // Value Display Center — sizes scale with the *actual* gauge dimensions
    // (not the global `s` factor) so a 70%-sized RPM gauge gets 70%-sized
    // text instead of overflowing onto the tick labels.
    readonly property real _dim: Math.min(width, height)
    Column {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: root._dim * 0.15
        spacing: -root._dim * 0.01

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: (root.value / root.displayDivisor).toFixed(root.decimals)
            color: (root.redZoneStart > 0 && root.value >= root.redZoneStart) ? "#ff2244" : "white"
            font.pixelSize: root._dim * 0.10
            font.bold: true
            Behavior on color { ColorAnimation { duration: 300 } }
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.unitLabel.toUpperCase()
            color: root.accentColor
            font.pixelSize: root._dim * 0.028
            font.letterSpacing: root._dim * 0.004
        }
    }

    // ── 7-segment odometer at bottom of gauge face ────────────────
    // Positioned independently near the bottom of the dial arc,
    // like a real mechanical/LED trip counter.
    FontLoader {
        id: dseg7
        source: "assets/DSEG7Classic-Bold.ttf"
    }

    Rectangle {
        visible: root.odometerValue >= 0
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: root._dim * 0.33
        width: odoText.width + root._dim * 0.04
        height: odoText.height + root._dim * 0.02
        color: "#050510"
        radius: root._dim * 0.012
        border.color: "#1a1a30"; border.width: 1

        Text {
            id: odoText
            anchors.centerIn: parent
            text: {
                var s = Math.floor(root.odometerValue).toString();
                while (s.length < 6) s = "0" + s;
                return s;
            }
            font.pixelSize: root._dim * 0.048
            font.family: dseg7.name
            color: "#01E6DE"
        }
    }
}
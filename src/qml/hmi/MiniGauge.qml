import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    property real value: 50
    property real minValue: 0
    property real maxValue: 100
    property string label: "TEMP"
    property string units: "°C"
    property color barColor: "#01E6DE"
    property real dangerAbove: -1
    property real dangerBelow: -1
    property real s: 1.0
    property string tooltipText: ""  // Set to show a tooltip on hover

    implicitWidth: 160 * s
    implicitHeight: 320 * s

    readonly property bool isLeft: label === "TEMP"
    
    readonly property color _activeColor: {
        if (dangerAbove > 0 && value >= dangerAbove) return "#FF3B3B";
        if (dangerBelow > 0 && value <= dangerBelow) return "#FF3B3B";
        return barColor;
    }

    // Geometry Logic
    readonly property real _pivotX: isLeft ? width * 1.5 : -width * 0.5
    readonly property real _pivotY: height / 2
    readonly property real _radius: width * 1.2
    readonly property real _sweep: 45 * (Math.PI / 180)
    
    // Fixed Angle Logic: High is always Top, Low is always Bottom
    // Top-left is ~157°, Top-right is ~22°
    readonly property real _highAngle: isLeft ? Math.PI - (_sweep/2) : (_sweep/2)
    readonly property real _lowAngle: isLeft ? Math.PI + (_sweep/2) : -(_sweep/2)

    onValueChanged: canvas.requestPaint()

    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true

        function drawRoundedRect(ctx, x, y, w, h, r) {
            ctx.beginPath();
            ctx.moveTo(x + r, y);
            ctx.lineTo(x + w - r, y);
            ctx.arcTo(x + w, y, x + w, y + r, r);
            ctx.lineTo(x + w, y + h - r);
            ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
            ctx.lineTo(x + r, y + h);
            ctx.arcTo(x, y + h, x, y + h - r, r);
            ctx.lineTo(x, y + r);
            ctx.arcTo(x, y, x + r, y, r);
            ctx.closePath();
        }

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            
            var segments = 16;
            var bw = 22 * s;
            var bh = 8 * s;
            var progress = (value - minValue) / (maxValue - minValue);

            for (var i = 0; i < segments; i++) {
                var p = i / (segments - 1);
                // Fill from screen-bottom (C/E) upward to screen-top (H/F)
                var angle = _highAngle + (p * (_lowAngle - _highAngle));
                var isLit = p <= progress;
                
                // Red Zone: Last 3 segments for Temp (High), First 3 segments for Fuel (Low)
                var isDangerSegment = (isLeft && i >= segments - 3) || (!isLeft && i < 3);

                ctx.save();
                ctx.translate(_pivotX, _pivotY);
                ctx.rotate(angle);

                if (isLit) {
                    var segmentColor = isDangerSegment ? "#FF3B3B" : barColor;
                    
                    ctx.globalAlpha = 0.3;
                    ctx.fillStyle = segmentColor;
                    drawRoundedRect(ctx, _radius - (bw/2) - 4*s, -bh/2 - 2*s, bw + 8*s, bh + 4*s, 2*s);
                    ctx.fill();
                    
                    ctx.globalAlpha = 1.0;
                    ctx.fillStyle = segmentColor;
                    drawRoundedRect(ctx, _radius - (bw/2), -bh/2, bw, bh, 1*s);
                    ctx.fill();
                } else {
                    ctx.globalAlpha = 1.0;
                    // Faint red for danger segments, no border
                    ctx.fillStyle = isDangerSegment ? "rgba(255, 60, 60, 0.12)" : "#1a1a24";
                    drawRoundedRect(ctx, _radius - (bw/2), -bh/2, bw, bh, 1*s);
                    ctx.fill();
                    
                    if (!isDangerSegment) {
                        ctx.strokeStyle = "rgba(255,255,255,0.05)";
                        ctx.lineWidth = 1 * s;
                        ctx.stroke();
                    }
                }
                ctx.restore();
            }

            // Needle Pin
            var needleAngle = _highAngle + (progress * (_lowAngle - _highAngle));
            ctx.save();
            ctx.translate(_pivotX, _pivotY);
            ctx.rotate(needleAngle);
            
            var grad = ctx.createLinearGradient(_radius - 30*s, 0, _radius + 20*s, 0);
            grad.addColorStop(0, "transparent");
            grad.addColorStop(0.5, "white");
            grad.addColorStop(1, "transparent");

            ctx.beginPath();
            ctx.strokeStyle = grad;
            ctx.lineWidth = 4 * s;
            ctx.moveTo(_radius - 35 * s, 0);
            ctx.lineTo(_radius + 20 * s, 0);
            ctx.stroke();

            ctx.beginPath();
            ctx.fillStyle = "white";
            ctx.moveTo(_radius - 35 * s, -1.5 * s);
            ctx.lineTo(_radius + 15 * s, -0.5 * s);
            ctx.lineTo(_radius + 15 * s, 0.5 * s);
            ctx.lineTo(_radius - 35 * s, 1.5 * s);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
        }
    }

    function getPoint(angle, offset) {
        // Always pull `offset` px toward the pivot (inside the arc) so text
        // sits inside the element bounds regardless of left/right orientation.
        var rx = _pivotX + Math.cos(angle) * (_radius - offset);
        var ry = _pivotY + Math.sin(angle) * _radius;
        return { "x": rx, "y": ry };
    }

    // TOP (C / E — cold/empty)
    Text {
        property var pt: getPoint(_highAngle, 35 * s)
        x: pt.x - width/2
        y: pt.y - height/2
        text: root.label === "TEMP" ? "C" : "E"
        color: (!isLeft && value <= dangerBelow && dangerBelow > 0) ? "#FF3B3B" : "white"
        font.pixelSize: 18 * s; font.bold: true
    }

    // CENTER INFO
    Column {
        property var pt: getPoint((_highAngle + _lowAngle)/2, 65 * s)
        x: pt.x - width/2
        y: pt.y - height/2
        spacing: 4 * s
        Text {
            text: root.label === "TEMP" ? "🌡" : "⛽"
            color: root._activeColor
            font.pixelSize: 32 * s
            anchors.horizontalCenter: parent.horizontalCenter
        }
        Text {
            text: Math.round(root.value) + root.units
            color: "white"
            font.pixelSize: 20 * s; font.family: "Consolas"; font.bold: true
            anchors.horizontalCenter: parent.horizontalCenter
        }
    }

    // BOTTOM (H / F — hot/full)
    Text {
        property var pt: getPoint(_lowAngle, 35 * s)
        x: pt.x - width/2
        y: pt.y - height/2
        text: root.label === "TEMP" ? "H" : "F"
        color: (isLeft && value >= dangerAbove && dangerAbove > 0) ? "#FF3B3B" : "white"
        font.pixelSize: 18 * s; font.bold: true
    }

    MouseArea {
        id: hover
        anchors.fill: parent
        hoverEnabled: root.tooltipText !== ""
        acceptedButtons: Qt.NoButton

        ToolTip {
            parent: hover
            x: hover.mouseX + width + 15 > hover.width
               ? hover.mouseX - width - 5
               : hover.mouseX + 15
            y: hover.mouseY + 20
            visible: hover.containsMouse && root.tooltipText !== ""
            text: root.tooltipText
            delay: 500
        }
    }
}
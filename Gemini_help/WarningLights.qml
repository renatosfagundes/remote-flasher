import QtQuick 2.15

Item {
    id: root
    property bool checkEngine: false
    property bool oilPressure: false
    property bool batteryWarn: false
    property bool brakeWarn: false
    property bool absWarn: false
    property bool airbagWarn: false
    property real s: 1.0

    width: row.width; height: row.height

    Row {
        id: row
        spacing: 20 * root.s

        Repeater {
            model: [
                { label: "ENG", prop: "checkEngine", col: "#FF9F00", icon: "engine" },
                { label: "OIL", prop: "oilPressure", col: "#FF3B30", icon: "oil" },
                { label: "BAT", prop: "batteryWarn", col: "#FF3B30", icon: "battery" },
                { label: "BRK", prop: "brakeWarn",    col: "#FF3B30", icon: "brake" },
                { label: "ABS", prop: "absWarn",      col: "#FF9F00", icon: "abs" },
                { label: "AIR", prop: "airbagWarn",   col: "#FF3B30", icon: "airbag" }
            ]

            Item {
                width: 54 * root.s; height: 80 * root.s
                readonly property bool active: root[modelData.prop]

                Canvas {
                    id: iconCanvas
                    anchors.top: parent.top
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 50 * root.s; height: width
                    antialiasing: true

                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.reset();
                        var w = width, h = height;
                        var cx = w / 2, cy = h / 2;
                        var col = modelData.col;

                        if (active) {
                            // Layered Glow Bloom
                            var bloom = ctx.createRadialGradient(cx, cy, 0, cx, cy, w/2);
                            bloom.addColorStop(0, Qt.rgba(1, 1, 1, 0.1)); // Center hot spot
                            bloom.addColorStop(0.2, Qt.alpha(col, 0.4));
                            bloom.addColorStop(1, "transparent");
                            ctx.fillStyle = bloom;
                            ctx.fillRect(0, 0, w, h);
                        }

                        ctx.save();
                        ctx.translate(cx, cy);
                        // Scale slightly smaller to prevent edge clipping
                        var iconScale = (w / 42) * root.s;
                        ctx.scale(iconScale, iconScale);
                        
                        ctx.strokeStyle = active ? col : "#151515";
                        ctx.fillStyle = ctx.strokeStyle;
                        ctx.lineWidth = 2.0;
                        ctx.lineCap = "round";
                        ctx.lineJoin = "round";

                        drawIcon(ctx, modelData.icon, active);
                        ctx.restore();
                    }

                    function drawIcon(ctx, type, isLit) {
                        if (type === "engine") {
                            ctx.beginPath();
                            ctx.moveTo(-9, 4); ctx.lineTo(-9, -2);
                            ctx.lineTo(-11, -2); ctx.lineTo(-11, -5);
                            ctx.lineTo(-9, -5); ctx.lineTo(-9, -6);
                            ctx.lineTo(-4, -6); ctx.lineTo(-4, -9);
                            ctx.lineTo(2, -9); ctx.lineTo(2, -6);
                            ctx.lineTo(6, -6); ctx.lineTo(6, -2);
                            ctx.lineTo(10, -2); ctx.lineTo(10, 1);
                            ctx.lineTo(12, 1); ctx.lineTo(12, 4);
                            ctx.lineTo(10, 4); ctx.lineTo(10, 7);
                            ctx.lineTo(-9, 7); ctx.closePath();
                            ctx.stroke();
                        } else if (type === "oil") {
                            // Classic Aladdin-style Oil Can
                            ctx.beginPath();
                            ctx.moveTo(-10, 4); ctx.lineTo(4, 4);
                            ctx.bezierCurveTo(10, 4, 12, 0, 14, -4); // Spout
                            ctx.stroke();
                            ctx.beginPath(); // Drip
                            ctx.moveTo(14, -2); ctx.bezierCurveTo(13, 1, 15, 1, 14, 4); ctx.stroke();
                            ctx.beginPath(); // Handle
                            ctx.moveTo(-10, 1); ctx.bezierCurveTo(-13, 1, -13, -5, -10, -5);
                            ctx.lineTo(-2, -5); ctx.stroke();
                            ctx.beginPath(); ctx.moveTo(-10, 1); ctx.lineTo(4, 1); ctx.stroke();
                        } else if (type === "battery") {
                            ctx.strokeRect(-10, -3, 20, 11);
                            ctx.fillRect(-7, -6, 4, 3); ctx.fillRect(3, -6, 4, 3);
                            ctx.font = "bold 7px sans-serif";
                            ctx.textAlign = "center";
                            ctx.fillText("-", -5, 5); ctx.fillText("+", 5, 5);
                        } else if (type === "brake") {
                            ctx.beginPath(); ctx.arc(0, 0, 8, 0, 6.28); ctx.stroke();
                            ctx.fillRect(-1, -4, 2, 5);
                            ctx.beginPath(); ctx.arc(0, 4, 1.2, 0, 6.28); ctx.fill();
                            ctx.beginPath(); ctx.arc(0, 0, 11, -2.2, -0.95); ctx.stroke();
                            ctx.beginPath(); ctx.arc(0, 0, 11, 0.95, 2.2); ctx.stroke();
                        } else if (type === "abs") {
                            ctx.beginPath(); ctx.arc(0, 0, 11, 0, 6.28); ctx.stroke();
                            ctx.font = "bold 9px sans-serif"; ctx.textAlign = "center";
                            ctx.textBaseline = "middle"; ctx.fillText("ABS", 0, 0);
                        } else if (type === "airbag") {
                            ctx.beginPath(); ctx.arc(-5, -7, 3.5, 0, 6.28); ctx.stroke();
                            ctx.beginPath(); ctx.moveTo(-6, -3); ctx.lineTo(-8, 5); ctx.lineTo(2, 5); ctx.stroke();
                            ctx.beginPath(); ctx.arc(8, -1, 6, 0, 6.28); ctx.stroke();
                        }
                    }

                    // Refresh logic
                    Connections {
                        target: root
                        function onCheckEngineChanged() { iconCanvas.requestPaint() }
                        function onOilPressureChanged() { iconCanvas.requestPaint() }
                        function onBatteryWarnChanged() { iconCanvas.requestPaint() }
                        function onBrakeWarnChanged() { iconCanvas.requestPaint() }
                        function onAbsWarnChanged() { iconCanvas.requestPaint() }
                        function onAirbagWarnChanged() { iconCanvas.requestPaint() }
                    }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    text: modelData.label
                    font.pixelSize: 11 * root.s; font.bold: true
                    color: active ? modelData.col : "#1a1a1a"
                }
            }
        }
    }
}
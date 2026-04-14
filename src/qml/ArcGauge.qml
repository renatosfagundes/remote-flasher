import QtQuick 2.15

Item {
    id: root

    property real value: 0
    property real minValue: 0
    property real maxValue: 100
    property string label: ""
    property string units: ""
    property color arcColor: "#f39c12"
    property real warningThreshold: -1
    property bool flipHorizontal: false   // mirror for right-side gauges

    implicitWidth: 100
    implicitHeight: 120

    readonly property real _fraction: maxValue > minValue
                                       ? Math.max(0, Math.min(1, (value - minValue) / (maxValue - minValue)))
                                       : 0
    readonly property real _warnFrac: warningThreshold >= 0 && maxValue > minValue
                                       ? (warningThreshold - minValue) / (maxValue - minValue) : 1.0

    // Mirror transform
    transform: Scale {
        xScale: flipHorizontal ? -1 : 1
        origin.x: root.width / 2
    }

    Canvas {
        id: canvas
        anchors.fill: parent

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();

            var w = width, h = height;
            var cx = w * 0.5;
            var cy = h * 0.55;
            var r = Math.min(w, h) * 0.4;
            var arcW = r * 0.22;

            // Arc spans 180 degrees (half circle)
            var startA = Math.PI;       // 9 o'clock
            var endA = 2 * Math.PI;     // 3 o'clock

            // Track
            ctx.beginPath();
            ctx.arc(cx, cy, r, startA, endA);
            ctx.lineWidth = arcW;
            ctx.strokeStyle = "#1a1a30";
            ctx.lineCap = "round";
            ctx.stroke();

            // Value arc
            if (_fraction > 0) {
                var valEnd = startA + _fraction * Math.PI;
                var normalEnd = Math.min(valEnd, startA + _warnFrac * Math.PI);

                // Normal color portion
                if (normalEnd > startA) {
                    ctx.beginPath();
                    ctx.arc(cx, cy, r, startA, normalEnd);
                    ctx.lineWidth = arcW;
                    ctx.strokeStyle = arcColor;
                    ctx.lineCap = "round";
                    ctx.stroke();

                    // Glow
                    ctx.beginPath();
                    ctx.arc(cx, cy, r, startA, normalEnd);
                    ctx.lineWidth = arcW + 6;
                    ctx.strokeStyle = Qt.rgba(arcColor.r, arcColor.g, arcColor.b, 0.15);
                    ctx.lineCap = "round";
                    ctx.stroke();
                }

                // Warning portion
                if (valEnd > normalEnd) {
                    ctx.beginPath();
                    ctx.arc(cx, cy, r, normalEnd, valEnd);
                    ctx.lineWidth = arcW;
                    ctx.strokeStyle = "#ff3333";
                    ctx.lineCap = "round";
                    ctx.stroke();
                }
            }

            // Tick marks
            var ticks = 5;
            for (var i = 0; i <= ticks; i++) {
                var frac = i / ticks;
                var ang = startA + frac * Math.PI;
                var cos_a = Math.cos(ang), sin_a = Math.sin(ang);
                var outerR = r + arcW / 2 + 2;
                var innerR = r + arcW / 2 + 7;
                ctx.beginPath();
                ctx.moveTo(cx + outerR * cos_a, cy + outerR * sin_a);
                ctx.lineTo(cx + innerR * cos_a, cy + innerR * sin_a);
                ctx.lineWidth = 1.5;
                ctx.strokeStyle = "#666";
                ctx.stroke();
            }
        }

        Connections {
            target: root
            function onValueChanged() { canvas.requestPaint(); }
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Component.onCompleted: requestPaint()
    }

    // Label (needs un-mirror if flipped)
    Item {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 2
        transform: Scale { xScale: flipHorizontal ? -1 : 1; origin.x: labelCol.width / 2 }

        Column {
            id: labelCol
            spacing: 0
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.label
                font.pixelSize: Math.max(9, root.height * 0.08)
                font.bold: true
                color: "#aaa"
            }
        }
    }

    // Value text (un-mirrored)
    Item {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 2
        transform: Scale { xScale: flipHorizontal ? -1 : 1; origin.x: valCol.width / 2 }

        Column {
            id: valCol
            spacing: 0
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.value.toFixed(root.maxValue >= 100 ? 0 : 1)
                font.pixelSize: Math.max(11, root.height * 0.1)
                font.bold: true
                color: _fraction > _warnFrac ? "#ff4444" : "#fff"
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.units
                font.pixelSize: Math.max(8, root.height * 0.065)
                color: "#888"
            }
        }
    }
}

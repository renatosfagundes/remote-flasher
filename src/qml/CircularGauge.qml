import QtQuick 2.15
import QtQuick.Shapes 1.15

Item {
    id: root

    property real value: 0
    property real minValue: 0
    property real maxValue: 100
    property string label: "RPM"
    property string units: "rpm"
    property color arcColor: "#00e5ff"
    property real warningThreshold: -1
    property bool large: false

    implicitWidth: 220
    implicitHeight: 220

    readonly property real _startAngle: 135
    readonly property real _sweepAngle: 270
    readonly property real _deg2rad: Math.PI / 180
    readonly property real _size: Math.min(width, height)
    readonly property real _cx: width / 2
    readonly property real _cy: height / 2
    readonly property real _r: _size / 2 - 8
    readonly property real _arcW: large ? _r * 0.13 : _r * 0.11

    readonly property real _clamped: Math.max(minValue, Math.min(maxValue, value))
    readonly property real _fraction: maxValue > minValue
                                       ? (_clamped - minValue) / (maxValue - minValue) : 0
    readonly property real _warnFrac: warningThreshold >= 0 && maxValue > minValue
                                       ? (warningThreshold - minValue) / (maxValue - minValue) : 1.0

    // Helper: angle in degrees for a fraction of the sweep
    function angleAt(frac) { return _startAngle + frac * _sweepAngle; }

    // Helper: point on circle at angle (degrees)
    function px(angle, radius) { return _cx + radius * Math.cos(angle * _deg2rad); }
    function py(angle, radius) { return _cy + radius * Math.sin(angle * _deg2rad); }

    // ============================================================
    // Background circle
    // ============================================================
    Rectangle {
        anchors.centerIn: parent
        width: _size; height: _size
        radius: _size / 2
        color: "#0c0c20"
        border.color: "#1a1a3a"
        border.width: 1.5

        // Inner shadow ring
        Rectangle {
            anchors.centerIn: parent
            width: parent.width - _arcW * 2 - 12
            height: width
            radius: width / 2
            color: "transparent"
            border.color: "#0e0e22"
            border.width: 1
        }
    }

    // ============================================================
    // Track arc (dark background arc)
    // ============================================================
    Shape {
        anchors.centerIn: parent
        width: _size; height: _size
        layer.enabled: true
        layer.samples: 4

        ShapePath {
            fillColor: "transparent"
            strokeColor: "#151530"
            strokeWidth: _arcW
            capStyle: ShapePath.FlatCap

            startX: px(_startAngle, _r)
            startY: py(_startAngle, _r)

            PathArc {
                x: px(angleAt(1), _r)
                y: py(angleAt(1), _r)
                radiusX: _r; radiusY: _r
                useLargeArc: _sweepAngle > 180
                direction: PathArc.Clockwise
            }
        }
    }

    // ============================================================
    // Value arc (colored, glowing)
    // ============================================================
    Shape {
        anchors.centerIn: parent
        width: _size; height: _size
        visible: _fraction > 0.005
        layer.enabled: true
        layer.samples: 4

        // Outer glow
        ShapePath {
            fillColor: "transparent"
            strokeColor: Qt.rgba(arcColor.r, arcColor.g, arcColor.b, 0.08)
            strokeWidth: _arcW + 18
            capStyle: ShapePath.RoundCap

            startX: px(_startAngle, _r)
            startY: py(_startAngle, _r)

            PathArc {
                x: px(angleAt(Math.min(_fraction, _warnFrac)), _r)
                y: py(angleAt(Math.min(_fraction, _warnFrac)), _r)
                radiusX: _r; radiusY: _r
                useLargeArc: (Math.min(_fraction, _warnFrac) * _sweepAngle) > 180
                direction: PathArc.Clockwise
            }
        }

        // Inner glow
        ShapePath {
            fillColor: "transparent"
            strokeColor: Qt.rgba(arcColor.r, arcColor.g, arcColor.b, 0.15)
            strokeWidth: _arcW + 8
            capStyle: ShapePath.RoundCap

            startX: px(_startAngle, _r)
            startY: py(_startAngle, _r)

            PathArc {
                x: px(angleAt(Math.min(_fraction, _warnFrac)), _r)
                y: py(angleAt(Math.min(_fraction, _warnFrac)), _r)
                radiusX: _r; radiusY: _r
                useLargeArc: (Math.min(_fraction, _warnFrac) * _sweepAngle) > 180
                direction: PathArc.Clockwise
            }
        }

        // Main arc
        ShapePath {
            fillColor: "transparent"
            strokeColor: arcColor
            strokeWidth: _arcW
            capStyle: ShapePath.RoundCap

            startX: px(_startAngle, _r)
            startY: py(_startAngle, _r)

            PathArc {
                x: px(angleAt(Math.min(_fraction, _warnFrac)), _r)
                y: py(angleAt(Math.min(_fraction, _warnFrac)), _r)
                radiusX: _r; radiusY: _r
                useLargeArc: (Math.min(_fraction, _warnFrac) * _sweepAngle) > 180
                direction: PathArc.Clockwise
            }
        }
    }

    // Warning arc (red)
    Shape {
        anchors.centerIn: parent
        width: _size; height: _size
        visible: _fraction > _warnFrac
        layer.enabled: true
        layer.samples: 4

        ShapePath {
            fillColor: "transparent"
            strokeColor: "#e74c3c"
            strokeWidth: _arcW
            capStyle: ShapePath.FlatCap

            startX: px(angleAt(_warnFrac), _r)
            startY: py(angleAt(_warnFrac), _r)

            PathArc {
                x: px(angleAt(_fraction), _r)
                y: py(angleAt(_fraction), _r)
                radiusX: _r; radiusY: _r
                useLargeArc: ((_fraction - _warnFrac) * _sweepAngle) > 180
                direction: PathArc.Clockwise
            }
        }
    }

    // ============================================================
    // Tick marks (Canvas — fine for static elements)
    // ============================================================
    Canvas {
        anchors.centerIn: parent
        width: _size; height: _size

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            var cx = width / 2, cy = height / 2;
            var r = _r;
            var arcW = _arcW;
            var majorTicks = large ? 10 : 8;
            var minorPerMajor = 5;

            for (var i = 0; i <= majorTicks; i++) {
                var frac = i / majorTicks;
                var ang = (_startAngle + frac * _sweepAngle) * _deg2rad;
                var cos_a = Math.cos(ang), sin_a = Math.sin(ang);
                var outerR = r - arcW / 2 - 3;
                var innerR = outerR - (large ? 14 : 10);

                // Major tick
                ctx.beginPath();
                ctx.moveTo(cx + innerR * cos_a, cy + innerR * sin_a);
                ctx.lineTo(cx + outerR * cos_a, cy + outerR * sin_a);
                ctx.lineWidth = large ? 2.5 : 2;
                ctx.strokeStyle = "#8899aa";
                ctx.stroke();

                // Label
                var labelR = innerR - (large ? 15 : 10);
                var val = minValue + frac * (maxValue - minValue);
                var labelText = maxValue >= 1000
                    ? Math.round(val / 1000).toString()
                    : Math.round(val).toString();
                var fs = large ? Math.max(12, r * 0.11) : Math.max(9, r * 0.1);
                ctx.font = "bold " + fs.toFixed(0) + "px 'Segoe UI', sans-serif";
                ctx.fillStyle = "#8899aa";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(labelText, cx + labelR * cos_a, cy + labelR * sin_a);

                // Minor ticks
                if (i < majorTicks) {
                    for (var m = 1; m < minorPerMajor; m++) {
                        var mFrac = (i + m / minorPerMajor) / majorTicks;
                        var mAng = (_startAngle + mFrac * _sweepAngle) * _deg2rad;
                        var mCos = Math.cos(mAng), mSin = Math.sin(mAng);
                        ctx.beginPath();
                        ctx.moveTo(cx + (outerR - 3) * mCos, cy + (outerR - 3) * mSin);
                        ctx.lineTo(cx + outerR * mCos, cy + outerR * mSin);
                        ctx.lineWidth = 1;
                        ctx.strokeStyle = "#334";
                        ctx.stroke();
                    }
                }
            }

            // x1000 label for RPM
            if (maxValue >= 1000) {
                ctx.font = "bold " + Math.max(8, r * 0.06).toFixed(0) + "px sans-serif";
                ctx.fillStyle = "#445";
                ctx.textAlign = "center";
                ctx.fillText("x1000", cx, cy - r * 0.22);
            }
        }

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Component.onCompleted: requestPaint()
    }

    // ============================================================
    // Needle (Shape for smooth rendering)
    // ============================================================
    Item {
        anchors.centerIn: parent
        width: _size; height: _size

        // Needle
        Rectangle {
            id: needle
            width: large ? 4 : 3
            height: _r - _arcW / 2 - 8
            radius: width / 2
            antialiasing: true
            anchors.bottom: parent.verticalCenter
            anchors.horizontalCenter: parent.horizontalCenter
            transformOrigin: Item.Bottom
            rotation: _startAngle + _fraction * _sweepAngle - 90

            gradient: Gradient {
                GradientStop { position: 0.0; color: arcColor }
                GradientStop { position: 0.4; color: Qt.lighter(arcColor, 1.5) }
                GradientStop { position: 0.7; color: "#ffffff" }
                GradientStop { position: 1.0; color: "#bbbbbb" }
            }

            Behavior on rotation {
                NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
            }
        }

        // Hub
        Rectangle {
            width: large ? 20 : 14; height: width; radius: width / 2
            anchors.centerIn: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#ddd" }
                GradientStop { position: 1.0; color: "#555" }
            }
            border.color: "#333"
            border.width: 0.5
        }
    }

    // ============================================================
    // Text labels
    // ============================================================

    // Label name
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        y: _cy + _size * 0.06
        text: root.label
        font.pixelSize: large ? Math.max(15, _size * 0.09) : Math.max(10, _size * 0.085)
        font.bold: true
        font.family: "Segoe UI"
        color: "#99aabb"
    }

    // Digital readout
    Column {
        anchors.horizontalCenter: parent.horizontalCenter
        y: _cy + _size * 0.16
        spacing: 0

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.value.toFixed(root.maxValue >= 1000 ? 0 : 1)
            font.pixelSize: large ? Math.max(30, _size * 0.22) : Math.max(14, _size * 0.13)
            font.bold: true
            font.family: "Segoe UI"
            color: "#ffffff"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.units
            font.pixelSize: large ? Math.max(13, _size * 0.085) : Math.max(9, _size * 0.07)
            color: "#778899"
            font.family: "Segoe UI"
        }
    }
}

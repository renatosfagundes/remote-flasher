import QtQuick 2.15
import QtQuick.Controls 2.15

Canvas {
    id: iconCanvas
    property string iconType: "engine"
    property color iconColor: "#FF9F00"
    property bool active: false
    property real s: 1.0
    property string tooltipText: ""   // Set to show a tooltip on hover

    // Cached gradient — created once per (size, color) pair, reused
    // across paints to avoid JS allocation pressure that triggers V4 GC.
    property var _bloomGradient: null

    width: 100 * s
    height: 100 * s
    antialiasing: true

    onActiveChanged: requestPaint()
    onIconTypeChanged: requestPaint()
    onIconColorChanged: { _bloomGradient = null; requestPaint() }
    onSChanged: { _bloomGradient = null; requestPaint() }
    onWidthChanged: { _bloomGradient = null }

    onPaint: {
        var ctx = getContext("2d");
        ctx.reset();
        
        var w = width;
        var h = height;
        var cx = w / 2;
        var cy = h / 2;
        var col = active ? iconColor : "#4a4d5c";  // dim but visible when inactive

        // 1. Draw Background Bloom (only when active) — gradient cached
        if (active) {
            if (_bloomGradient === null) {
                var grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, w/2);
                grad.addColorStop(0, Qt.rgba(1, 1, 1, 0.15));
                grad.addColorStop(0.3, Qt.alpha(iconColor, 0.3));
                grad.addColorStop(1, "transparent");
                _bloomGradient = grad;
            }
            ctx.fillStyle = _bloomGradient;
            ctx.fillRect(0, 0, w, h);
        }

        ctx.save();
        ctx.translate(cx, cy);

        // (Shadow glow removed — ctx.shadowBlur is O(blur²) per pixel and
        // caused multi-second event-loop stalls every ~10s. The radial-
        // gradient bloom drawn above gives a similar visual effect at a
        // tiny fraction of the cost.)

        ctx.strokeStyle = col;
        ctx.fillStyle = col;
        ctx.lineWidth = 2.2;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";

        if (iconType === "engine") {
            // Normalized Scale for Engine SVG Data
            ctx.scale(0.055 * s, 0.055 * s);
            ctx.translate(-640, -512);
            ctx.lineWidth = 60;  // thick at SVG scale (60 * 0.04 ≈ 2.4px)

            ctx.beginPath();
            ctx.moveTo(527, 190); ctx.lineTo(527, 79);
            ctx.lineTo(812, 79); ctx.lineTo(812, 190);
            ctx.lineTo(874, 190); ctx.lineTo(953, 269);
            ctx.lineTo(1014, 269); ctx.lineTo(1014, 390);
            ctx.lineTo(1144, 390); ctx.lineTo(1144, 711);
            ctx.lineTo(1014, 711); ctx.lineTo(1014, 840);
            ctx.lineTo(535, 840); ctx.lineTo(408, 712);
            ctx.lineTo(194, 712); ctx.lineTo(194, 337);
            ctx.lineTo(286, 333); ctx.lineTo(388, 231);
            ctx.lineTo(527, 231);
            ctx.closePath();
            ctx.stroke();

            // The intake/accessory details (the yellow stubs)
            ctx.fillRect(1, 332, 96, 479);     // Left stub
            ctx.fillRect(446, 30, 479, 96);    // Top stub
            ctx.fillRect(1182, 332, 96, 613);  // Right stub

        } else if (iconType === "oil") {
            // Normalized Scale for Oil SVG Data
            ctx.scale(0.065 * s, 0.065 * s);
            ctx.translate(-512, -512);
            ctx.lineWidth = 45;  // thick at SVG scale (45 * 0.05 ≈ 2.25px)

            ctx.beginPath();
            ctx.moveTo(954, 457);
            ctx.lineTo(902, 393);
            ctx.lineTo(582, 482);
            ctx.lineTo(543, 435);
            ctx.lineTo(432, 435);
            ctx.lineTo(432, 384);
            ctx.lineTo(486, 384);
            ctx.lineTo(486, 333);
            ctx.lineTo(326, 333);
            ctx.lineTo(326, 384);
            ctx.lineTo(380, 384);
            ctx.lineTo(380, 435);
            ctx.lineTo(274, 435);
            ctx.lineTo(275, 388);
            ctx.lineTo(90, 323);
            ctx.lineTo(65, 477);
            ctx.lineTo(224, 534);
            ctx.lineTo(224, 713);
            ctx.lineTo(653, 713);
            ctx.lineTo(828, 466);
            ctx.lineTo(883, 451);
            ctx.lineTo(914, 489);
            ctx.closePath();
            ctx.stroke();

            // The Oil Drip
            ctx.beginPath();
            ctx.arc(934, 617, 38, 0, Math.PI * 2);
            ctx.fill();
            // Pointed top of drip
            ctx.beginPath();
            ctx.moveTo(896, 617);
            ctx.lineTo(934, 534);
            ctx.lineTo(972, 617);
            ctx.fill();
        } else if (iconType === "battery") {
            var bs = 2.5 * s;
            ctx.scale(bs, bs);
            // Body
            ctx.strokeRect(-10, -3, 20, 12);
            // Terminals
            ctx.fillRect(-7, -6, 5, 3);
            ctx.fillRect(2, -6, 5, 3);
            // + / -
            ctx.lineWidth = 1.8;
            ctx.beginPath();
            ctx.moveTo(-6, 3); ctx.lineTo(-2, 3);
            ctx.moveTo(-4, 1); ctx.lineTo(-4, 5);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(2, 3); ctx.lineTo(6, 3);
            ctx.stroke();

        } else if (iconType === "brake") {
            var bks = 2.2 * s;
            ctx.scale(bks, bks);
            // Inner circle
            ctx.beginPath(); ctx.arc(0, 0, 8, 0, 2 * Math.PI); ctx.stroke();
            // Exclamation
            ctx.lineWidth = 2.2;
            ctx.beginPath();
            ctx.moveTo(0, -4); ctx.lineTo(0, 2);
            ctx.stroke();
            ctx.beginPath(); ctx.arc(0, 4.5, 1.5, 0, 2 * Math.PI); ctx.fill();
            ctx.lineWidth = 2.2;
            // Outer brake arcs
            ctx.beginPath(); ctx.arc(0, 0, 11.5, -2.3, -0.85); ctx.stroke();
            ctx.beginPath(); ctx.arc(0, 0, 11.5, 0.85, 2.3); ctx.stroke();

        } else if (iconType === "abs") {
            var as2 = 2.2 * s;
            ctx.scale(as2, as2);
            ctx.beginPath(); ctx.arc(0, 0, 12, 0, 2 * Math.PI); ctx.stroke();
            ctx.font = "bold 11px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText("ABS", 0, 0.5);

        } else if (iconType === "airbag") {
            var ais = 2.0 * s;
            ctx.scale(ais, ais);
            // Head
            ctx.beginPath(); ctx.arc(-5, -8, 3.5, 0, 2 * Math.PI); ctx.stroke();
            // Body (leaning forward)
            ctx.beginPath();
            ctx.moveTo(-5, -4.5);
            ctx.lineTo(-3, 4);
            ctx.stroke();
            // Arm reaching to airbag
            ctx.beginPath();
            ctx.moveTo(-4, -1);
            ctx.lineTo(3, -2);
            ctx.stroke();
            // Legs (seated, bent)
            ctx.beginPath();
            ctx.moveTo(-3, 4);
            ctx.lineTo(2, 7);
            ctx.lineTo(-1, 10);
            ctx.stroke();
            // Airbag circle
            ctx.beginPath(); ctx.arc(8, -1, 6.5, 0, 2 * Math.PI); ctx.stroke();
        }

        ctx.restore();
    }

    MouseArea {
        id: hover
        anchors.fill: parent
        hoverEnabled: iconCanvas.tooltipText !== ""
        acceptedButtons: Qt.NoButton
        ToolTip.visible: containsMouse && iconCanvas.tooltipText !== ""
        ToolTip.text: iconCanvas.tooltipText
        ToolTip.delay: 500
    }
}
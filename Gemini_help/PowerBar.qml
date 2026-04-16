import QtQuick 2.15

/*
  Horizontal power/regen bar for EV mode.
  Left of centre = regen (green), right = power (cyan).
*/
Item {
    id: root
    property real value: 0        // kW, negative = regen
    property real maxPower: 300
    property real maxRegen: 100
    property real s: 1.0

    width: 300 * s
    height: 55 * s

    onValueChanged: canvas.requestPaint()

    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();

            var w = width, h = height;
            var barH = 14 * s;
            var barY = 6 * s;
            var barL = 12 * s;               // left edge
            var barR = w - 12 * s;           // right edge
            var barW = barR - barL;
            // Zero point shifted left (regen range is shorter)
            var zeroX = barL + barW * (root.maxRegen / (root.maxRegen + root.maxPower));
            var r = barH / 2;               // rounded end radius

            // ── Background track ──────────────────────────────────
            ctx.beginPath();
            ctx.moveTo(barL + r, barY);
            ctx.lineTo(barR - r, barY);
            ctx.arcTo(barR, barY, barR, barY + r, r);
            ctx.arcTo(barR, barY + barH, barR - r, barY + barH, r);
            ctx.lineTo(barL + r, barY + barH);
            ctx.arcTo(barL, barY + barH, barL, barY + barH - r, r);
            ctx.arcTo(barL, barY, barL + r, barY, r);
            ctx.closePath();
            ctx.fillStyle = "#1a1a28";
            ctx.fill();
            ctx.strokeStyle = "rgba(255,255,255,0.06)";
            ctx.lineWidth = 1;
            ctx.stroke();

            // ── Helper: clip to the rounded background shape ─────
            function clipToTrack() {
                ctx.beginPath();
                ctx.moveTo(barL + r, barY);
                ctx.lineTo(barR - r, barY);
                ctx.arcTo(barR, barY, barR, barY + r, r);
                ctx.arcTo(barR, barY + barH, barR - r, barY + barH, r);
                ctx.lineTo(barL + r, barY + barH);
                ctx.arcTo(barL, barY + barH, barL, barY + barH - r, r);
                ctx.arcTo(barL, barY, barL + r, barY, r);
                ctx.closePath();
                ctx.clip();
            }

            // ── Filled portion (clipped to rounded track) ─────────
            if (root.value < -0.5) {
                var regenFrac = Math.min(1, Math.abs(root.value) / root.maxRegen);
                var regenW = regenFrac * (zeroX - barL);
                var rx = zeroX - regenW;

                // Glow
                ctx.fillStyle = "rgba(46, 204, 113, 0.15)";
                ctx.fillRect(rx - 2 * s, barY - 3 * s, regenW + 4 * s, barH + 6 * s);

                // Bar fill (clipped)
                ctx.save();
                clipToTrack();
                var rGrad = ctx.createLinearGradient(rx, 0, zeroX, 0);
                rGrad.addColorStop(0, "#2ecc71");
                rGrad.addColorStop(1, "rgba(46, 204, 113, 0.2)");
                ctx.fillStyle = rGrad;
                ctx.fillRect(rx, barY, regenW, barH);
                ctx.restore();

            } else if (root.value > 0.5) {
                var powerFrac = Math.min(1, root.value / root.maxPower);
                var powerW = powerFrac * (barR - zeroX);

                // Glow
                ctx.fillStyle = "rgba(1, 230, 222, 0.12)";
                ctx.fillRect(zeroX - 2 * s, barY - 3 * s, powerW + 4 * s, barH + 6 * s);

                // Bar fill (clipped)
                ctx.save();
                clipToTrack();
                var pGrad = ctx.createLinearGradient(zeroX, 0, zeroX + powerW, 0);
                pGrad.addColorStop(0, "rgba(1, 230, 222, 0.2)");
                pGrad.addColorStop(1, "#01E6DE");
                ctx.fillStyle = pGrad;
                ctx.fillRect(zeroX, barY, powerW, barH);
                ctx.restore();
            }

            // ── Zero marker ───────────────────────────────────────
            ctx.beginPath();
            ctx.moveTo(zeroX, barY - 3 * s);
            ctx.lineTo(zeroX, barY + barH + 3 * s);
            ctx.strokeStyle = "rgba(255,255,255,0.5)";
            ctx.lineWidth = 1.5 * s;
            ctx.stroke();

            // ── Scale ticks ───────────────────────────────────────
            ctx.strokeStyle = "rgba(255,255,255,0.15)";
            ctx.lineWidth = 1;
            // Regen ticks
            for (var ri = 25; ri < root.maxRegen; ri += 25) {
                var rtx = zeroX - (ri / root.maxRegen) * (zeroX - barL);
                ctx.beginPath();
                ctx.moveTo(rtx, barY + barH + 1);
                ctx.lineTo(rtx, barY + barH + 4 * s);
                ctx.stroke();
            }
            // Power ticks
            for (var pi = 50; pi < root.maxPower; pi += 50) {
                var ptx = zeroX + (pi / root.maxPower) * (barR - zeroX);
                ctx.beginPath();
                ctx.moveTo(ptx, barY + barH + 1);
                ctx.lineTo(ptx, barY + barH + 4 * s);
                ctx.stroke();
            }
        }
    }

    // ── Labels ────────────────────────────────────────────────────
    Text {
        anchors { left: parent.left; leftMargin: 12 * s; bottom: parent.bottom }
        text: "REGEN"
        color: "#2ecc71"; opacity: 0.5
        font.pixelSize: 9 * s; font.family: "Consolas"; font.bold: true
    }

    Text {
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom }
        text: (root.value >= 0 ? "+" : "") + Math.round(root.value) + " kW"
        color: root.value < 0 ? "#2ecc71" : "#01E6DE"
        font.pixelSize: 13 * s; font.family: "Consolas"; font.bold: true
    }

    Text {
        anchors { right: parent.right; rightMargin: 12 * s; bottom: parent.bottom }
        text: "POWER"
        color: "#01E6DE"; opacity: 0.5
        font.pixelSize: 9 * s; font.family: "Consolas"; font.bold: true
    }
}

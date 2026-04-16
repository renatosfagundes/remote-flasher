import QtQuick 2.15

/*
  Top-down bird's-eye car with door-ajar indicators.
  Open doors show red arcs swinging outward from the hinge.
  Hood/trunk glow red when open.
*/
Item {
    id: root
    property bool doorFL: false
    property bool doorFR: false
    property bool doorRL: false
    property bool doorRR: false
    property bool trunk: false
    property bool hood: false
    property real s: 1.0

    width: 120 * s
    height: 190 * s

    onDoorFLChanged: canvas.requestPaint()
    onDoorFRChanged: canvas.requestPaint()
    onDoorRLChanged: canvas.requestPaint()
    onDoorRRChanged: canvas.requestPaint()
    onTrunkChanged:  canvas.requestPaint()
    onHoodChanged:   canvas.requestPaint()

    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            ctx.save();

            var w = width, h = height;
            var cx = w / 2;

            // Body dimensions
            var bodyW = w * 0.48;
            var bodyH = h * 0.78;
            var bodyX = cx - bodyW / 2;
            var bodyY = (h - bodyH) / 2;
            var rFront = bodyW * 0.45;  // rounder front
            var rRear = bodyW * 0.35;

            // ── Shadow / ground plane ─────────────────────────────
            ctx.beginPath();
            ctx.ellipse(cx - bodyW * 0.6, bodyY + bodyH * 0.45, bodyW * 1.2, bodyH * 0.25);
            ctx.fillStyle = "rgba(0,0,0,0.15)";
            ctx.fill();

            // ── Car body ──────────────────────────────────────────
            ctx.beginPath();
            ctx.moveTo(bodyX + rFront, bodyY);
            ctx.lineTo(bodyX + bodyW - rFront, bodyY);
            ctx.arcTo(bodyX + bodyW, bodyY, bodyX + bodyW, bodyY + rFront, rFront);
            ctx.lineTo(bodyX + bodyW, bodyY + bodyH - rRear);
            ctx.arcTo(bodyX + bodyW, bodyY + bodyH, bodyX + bodyW - rRear, bodyY + bodyH, rRear);
            ctx.lineTo(bodyX + rRear, bodyY + bodyH);
            ctx.arcTo(bodyX, bodyY + bodyH, bodyX, bodyY + bodyH - rRear, rRear);
            ctx.lineTo(bodyX, bodyY + rFront);
            ctx.arcTo(bodyX, bodyY, bodyX + rFront, bodyY, rFront);
            ctx.closePath();

            // Body gradient
            var bodyGrad = ctx.createLinearGradient(bodyX, bodyY, bodyX + bodyW, bodyY);
            bodyGrad.addColorStop(0, "#1e1e30");
            bodyGrad.addColorStop(0.5, "#252540");
            bodyGrad.addColorStop(1, "#1e1e30");
            ctx.fillStyle = bodyGrad;
            ctx.fill();
            ctx.strokeStyle = "#4a4a65";
            ctx.lineWidth = 1.2 * s;
            ctx.stroke();

            // ── Windshield ────────────────────────────────────────
            var wsY = bodyY + bodyH * 0.22;
            var wsInset = bodyW * 0.12;
            ctx.beginPath();
            ctx.moveTo(bodyX + wsInset, wsY + 2 * s);
            ctx.bezierCurveTo(
                bodyX + bodyW * 0.3, wsY - 5 * s,
                bodyX + bodyW * 0.7, wsY - 5 * s,
                bodyX + bodyW - wsInset, wsY + 2 * s);
            ctx.lineTo(bodyX + bodyW - wsInset - 2 * s, wsY + bodyH * 0.08);
            ctx.bezierCurveTo(
                bodyX + bodyW * 0.65, wsY + bodyH * 0.06,
                bodyX + bodyW * 0.35, wsY + bodyH * 0.06,
                bodyX + wsInset + 2 * s, wsY + bodyH * 0.08);
            ctx.closePath();
            ctx.fillStyle = "rgba(80, 130, 180, 0.12)";
            ctx.fill();
            ctx.strokeStyle = "#4a4a65";
            ctx.lineWidth = 1 * s;
            ctx.stroke();

            // ── Rear window ───────────────────────────────────────
            var rwY = bodyY + bodyH * 0.65;
            ctx.beginPath();
            ctx.moveTo(bodyX + wsInset, rwY);
            ctx.bezierCurveTo(
                bodyX + bodyW * 0.3, rwY - 3 * s,
                bodyX + bodyW * 0.7, rwY - 3 * s,
                bodyX + bodyW - wsInset, rwY);
            ctx.lineTo(bodyX + bodyW - wsInset - 3 * s, rwY + bodyH * 0.06);
            ctx.bezierCurveTo(
                bodyX + bodyW * 0.65, rwY + bodyH * 0.07,
                bodyX + bodyW * 0.35, rwY + bodyH * 0.07,
                bodyX + wsInset + 3 * s, rwY + bodyH * 0.06);
            ctx.closePath();
            ctx.fillStyle = "rgba(80, 130, 180, 0.10)";
            ctx.fill();
            ctx.strokeStyle = "#4a4a65";
            ctx.lineWidth = 1 * s;
            ctx.stroke();

            // ── Door panel seams (subtle lines on the body) ───────
            var doorSeamFront = bodyY + bodyH * 0.34;
            var doorSeamRear = bodyY + bodyH * 0.56;
            ctx.strokeStyle = "rgba(255,255,255,0.06)";
            ctx.lineWidth = 0.8 * s;
            // Left seams
            ctx.beginPath();
            ctx.moveTo(bodyX + 1, doorSeamFront);
            ctx.lineTo(bodyX + 1, doorSeamRear);
            ctx.stroke();
            // Right seams
            ctx.beginPath();
            ctx.moveTo(bodyX + bodyW - 1, doorSeamFront);
            ctx.lineTo(bodyX + bodyW - 1, doorSeamRear);
            ctx.stroke();
            // Cross seam between front/rear doors
            var midSeam = (doorSeamFront + doorSeamRear) / 2;
            ctx.beginPath();
            ctx.moveTo(bodyX, midSeam);
            ctx.lineTo(bodyX + 2 * s, midSeam);
            ctx.moveTo(bodyX + bodyW, midSeam);
            ctx.lineTo(bodyX + bodyW - 2 * s, midSeam);
            ctx.stroke();

            // ── Wheels ────────────────────────────────────────────
            var wheelW = 5 * s, wheelH = 15 * s;
            ctx.fillStyle = "#2a2a3a";
            ctx.strokeStyle = "#3a3a50";
            ctx.lineWidth = 1 * s;

            function drawWheel(x, y) {
                var wr = 2 * s;
                ctx.beginPath();
                ctx.moveTo(x + wr, y);
                ctx.lineTo(x + wheelW - wr, y);
                ctx.arcTo(x + wheelW, y, x + wheelW, y + wr, wr);
                ctx.lineTo(x + wheelW, y + wheelH - wr);
                ctx.arcTo(x + wheelW, y + wheelH, x + wheelW - wr, y + wheelH, wr);
                ctx.lineTo(x + wr, y + wheelH);
                ctx.arcTo(x, y + wheelH, x, y + wheelH - wr, wr);
                ctx.lineTo(x, y + wr);
                ctx.arcTo(x, y, x + wr, y, wr);
                ctx.closePath();
                ctx.fill();
                ctx.stroke();
            }

            drawWheel(bodyX - wheelW - 1 * s, bodyY + bodyH * 0.12);
            drawWheel(bodyX + bodyW + 1 * s, bodyY + bodyH * 0.12);
            drawWheel(bodyX - wheelW - 1 * s, bodyY + bodyH * 0.68);
            drawWheel(bodyX + bodyW + 1 * s, bodyY + bodyH * 0.68);

            // ── Headlights (two small bright dots at front) ───────
            ctx.fillStyle = "rgba(255, 255, 200, 0.4)";
            ctx.beginPath();
            ctx.arc(bodyX + bodyW * 0.2, bodyY + 4 * s, 2.5 * s, 0, 2 * Math.PI);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(bodyX + bodyW * 0.8, bodyY + 4 * s, 2.5 * s, 0, 2 * Math.PI);
            ctx.fill();

            // ── Taillights (two small red dots at rear) ───────────
            ctx.fillStyle = "rgba(255, 50, 50, 0.35)";
            ctx.beginPath();
            ctx.arc(bodyX + bodyW * 0.2, bodyY + bodyH - 4 * s, 2.5 * s, 0, 2 * Math.PI);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(bodyX + bodyW * 0.8, bodyY + bodyH - 4 * s, 2.5 * s, 0, 2 * Math.PI);
            ctx.fill();

            // ── Hood panel outline (small, offset upward) ─────────
            if (root.hood) {
                var hGap = 5 * s;
                var hInset = bodyW * 0.15;  // narrower than the body
                var hR = rFront * 0.7;      // smaller corner radius
                var hTop = bodyY + bodyH * 0.04;
                var hBot = wsY - 2 * s;

                function drawHoodShape(g) {
                    ctx.beginPath();
                    ctx.moveTo(bodyX + hInset, hBot - g);
                    ctx.lineTo(bodyX + hInset, hTop + hR - g);
                    ctx.arcTo(bodyX + hInset, hTop - g, bodyX + hInset + hR, hTop - g, hR);
                    ctx.lineTo(bodyX + bodyW - hInset - hR, hTop - g);
                    ctx.arcTo(bodyX + bodyW - hInset, hTop - g, bodyX + bodyW - hInset, hTop + hR - g, hR);
                    ctx.lineTo(bodyX + bodyW - hInset, hBot - g);
                }
                // Glow
                drawHoodShape(hGap);
                ctx.strokeStyle = "rgba(255, 59, 59, 0.25)";
                ctx.lineWidth = 6 * s;
                ctx.lineCap = "round"; ctx.lineJoin = "round";
                ctx.stroke();
                // Line
                drawHoodShape(hGap);
                ctx.strokeStyle = "#FF3B3B";
                ctx.lineWidth = 2 * s;
                ctx.stroke();
            }

            // ── Trunk panel outline (small, offset downward) ──────
            if (root.trunk) {
                var tGap = 5 * s;
                var tInset = bodyW * 0.15;
                var tR = rRear * 0.7;
                var tTop = rwY + bodyH * 0.04;
                var tBot = bodyY + bodyH - bodyH * 0.04;

                function drawTrunkShape(g) {
                    ctx.beginPath();
                    ctx.moveTo(bodyX + tInset, tTop + g);
                    ctx.lineTo(bodyX + tInset, tBot - tR + g);
                    ctx.arcTo(bodyX + tInset, tBot + g, bodyX + tInset + tR, tBot + g, tR);
                    ctx.lineTo(bodyX + bodyW - tInset - tR, tBot + g);
                    ctx.arcTo(bodyX + bodyW - tInset, tBot + g, bodyX + bodyW - tInset, tBot - tR + g, tR);
                    ctx.lineTo(bodyX + bodyW - tInset, tTop + g);
                }
                // Glow
                drawTrunkShape(tGap);
                ctx.strokeStyle = "rgba(255, 59, 59, 0.25)";
                ctx.lineWidth = 6 * s;
                ctx.lineCap = "round"; ctx.lineJoin = "round";
                ctx.stroke();
                // Line
                drawTrunkShape(tGap);
                ctx.strokeStyle = "#FF3B3B";
                ctx.lineWidth = 2 * s;
                ctx.stroke();
            }

            // ── Door indicators ───────────────────────────────────
            // Like a real dashboard: closed = green dot, open = red line
            // swinging outward from the hinge point.
            var doorLen = bodyH * 0.13;    // length of the door line
            var openAngle = 55 * Math.PI / 180;  // how far the door opens

            function drawDoor(hx, hy, side, isOpen) {
                // side: -1=left, +1=right
                // Door closed along the car body = vertical line
                // Door open = line angled outward

                if (!isOpen) {
                    // Closed: subtle green line flush with body
                    ctx.beginPath();
                    ctx.moveTo(hx, hy);
                    ctx.lineTo(hx, hy + doorLen);
                    ctx.strokeStyle = "rgba(46, 204, 113, 0.5)";
                    ctx.lineWidth = 2 * s;
                    ctx.stroke();
                    return;
                }

                // Open: door line swings outward
                var tipX = hx + Math.sin(openAngle) * doorLen * side;
                var tipY = hy + Math.cos(openAngle) * doorLen;

                // Glow behind the door
                ctx.beginPath();
                ctx.moveTo(hx, hy);
                ctx.lineTo(tipX, tipY);
                ctx.strokeStyle = "rgba(255, 59, 59, 0.25)";
                ctx.lineWidth = 8 * s;
                ctx.lineCap = "round";
                ctx.stroke();

                // Door panel line
                ctx.beginPath();
                ctx.moveTo(hx, hy);
                ctx.lineTo(tipX, tipY);
                ctx.strokeStyle = "#FF3B3B";
                ctx.lineWidth = 2.5 * s;
                ctx.lineCap = "round";
                ctx.stroke();

                // Hinge dot
                ctx.beginPath();
                ctx.arc(hx, hy, 2.5 * s, 0, 2 * Math.PI);
                ctx.fillStyle = "#FF3B3B";
                ctx.fill();
            }

            // Front doors: hinge at top of door zone
            drawDoor(bodyX,         bodyY + bodyH * 0.30, -1, root.doorFL);
            drawDoor(bodyX + bodyW, bodyY + bodyH * 0.30,  1, root.doorFR);
            // Rear doors: hinge at top of rear door zone
            drawDoor(bodyX,         bodyY + bodyH * 0.48, -1, root.doorRL);
            drawDoor(bodyX + bodyW, bodyY + bodyH * 0.48,  1, root.doorRR);

            ctx.restore();
        }
    }

    // Labels
    Text {
        anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 2 * s }
        text: root.hood ? "HOOD OPEN" : ""
        color: "#FF3B3B"; font.pixelSize: 9 * s; font.family: "Consolas"; font.bold: true
    }
    Text {
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 2 * s }
        text: root.trunk ? "TRUNK OPEN" : ""
        color: "#FF3B3B"; font.pixelSize: 9 * s; font.family: "Consolas"; font.bold: true
    }
}

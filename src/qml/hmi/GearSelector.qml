import QtQuick 2.15

/*
  Gear indicator — active gear is bright with glow + underline.
  All gears same size for stable layout.
*/
Item {
    id: root
    property int gearValue: 7    // -1=R, 0=N, 1-6=fwd, 7=P, 8=D
    property bool isAutomatic: true
    property real s: 1.0

    readonly property var _gears: isAutomatic
        ? [{ t: "P", v: 7 }, { t: "R", v: -1 }, { t: "N", v: 0 }, { t: "D", v: 8 }]
        : [{ t: "N", v: 0 }, { t: "R", v: -1 }, { t: "1", v: 1 }, { t: "2", v: 2 },
           { t: "3", v: 3 }, { t: "4", v: 4 }, { t: "5", v: 5 }, { t: "6", v: 6 }]

    width: row.width
    height: row.height

    Row {
        id: row
        spacing: 4 * root.s

        Repeater {
            model: root._gears

            Item {
                width: Math.max(28, 32 * root.s)
                height: Math.max(36, 44 * root.s)

                readonly property bool active: root.gearValue === modelData.v

                // Glow behind active gear
                Rectangle {
                    anchors.fill: parent
                    radius: 6 * root.s
                    color: active ? "rgba(1, 230, 222, 0.12)" : "transparent"
                    border.color: active ? "rgba(1, 230, 222, 0.3)" : "transparent"
                    border.width: 1 * root.s

                    Behavior on color { ColorAnimation { duration: 200 } }
                    Behavior on border.color { ColorAnimation { duration: 200 } }
                }

                // Gear letter
                Text {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: -3 * root.s
                    text: modelData.t
                    font.pixelSize: Math.max(16, 22 * root.s)
                    font.family: "Consolas"
                    font.bold: true
                    color: active ? "#ffffff" : "#444"

                    Behavior on color { ColorAnimation { duration: 200 } }
                }

                // Underline indicator
                Rectangle {
                    width: parent.width * 0.5
                    height: 2.5 * root.s
                    radius: height / 2
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 4 * root.s
                    color: active ? "#01E6DE" : "transparent"

                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }
        }
    }
}

// StatusLight.qml — small SVG-based status indicator (e.g. parking lights,
// low beam, fog, seatbelt). Swaps between an "active" and an "inactive"
// SVG asset based on the `active` property. Cheap (just two SVG images),
// no Canvas allocation.
import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    property bool active: false
    property string activeSvg: ""
    property string inactiveSvg: ""
    property real s: 1.0
    property real iconSize: 32 * s
    property string tooltipText: ""   // Set to show a tooltip on hover

    width: iconSize
    height: iconSize

    Image {
        anchors.fill: parent
        source: root.active ? root.activeSvg : root.inactiveSvg
        sourceSize.width: parent.width
        sourceSize.height: parent.height
        fillMode: Image.PreserveAspectFit
        opacity: root.active ? 1.0 : 0.45
        Behavior on opacity { NumberAnimation { duration: 200 } }
    }

    MouseArea {
        id: hover
        anchors.fill: parent
        hoverEnabled: root.tooltipText !== ""
        acceptedButtons: Qt.NoButton  // don't swallow clicks
        ToolTip.visible: containsMouse && root.tooltipText !== ""
        ToolTip.text: root.tooltipText
        ToolTip.delay: 500
    }
}

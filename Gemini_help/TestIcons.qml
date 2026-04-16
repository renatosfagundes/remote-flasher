import QtQuick 2.15
import QtQuick.Window 2.15

Window {
    width: 800; height: 200; visible: true; color: "#050505"

    Row {
        anchors.centerIn: parent
        spacing: 30

        WarningIcons { iconType: "engine";  iconColor: "#FF9F00"; active: true; s: 1.5 }
        WarningIcons { iconType: "oil";     iconColor: "#FF3B30"; active: true; s: 1.5 }
        WarningIcons { iconType: "battery"; iconColor: "#FF3B30"; active: true; s: 1.5 }
        WarningIcons { iconType: "brake";   iconColor: "#FF3B30"; active: true; s: 1.5 }
        WarningIcons { iconType: "abs";     iconColor: "#FF9F00"; active: true; s: 1.5 }
        WarningIcons { iconType: "airbag";  iconColor: "#FF3B30"; active: true; s: 1.5 }
    }
}
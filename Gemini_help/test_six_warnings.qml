// test_six_warnings.qml — only the 6 warning icons updating
import QtQuick 2.15
Item {
    Rectangle { anchors.fill: parent; color: "#0c0c14" }
    Row {
        anchors.centerIn: parent; spacing: 10
        WarningIcons { iconType: "engine";  iconColor: "#FF9F00"; active: dashboard ? dashboard.checkEngine : false; s: 1.5 }
        WarningIcons { iconType: "oil";     iconColor: "#FF3B30"; active: dashboard ? dashboard.oilPressure : false; s: 1.5 }
        WarningIcons { iconType: "battery"; iconColor: "#FF3B30"; active: dashboard ? dashboard.batteryWarn : false; s: 1.5 }
        WarningIcons { iconType: "brake";   iconColor: "#FF3B30"; active: dashboard ? dashboard.brakeWarn : false; s: 1.5 }
        WarningIcons { iconType: "abs";     iconColor: "#FF9F00"; active: dashboard ? dashboard.absWarn : false; s: 1.5 }
        WarningIcons { iconType: "airbag";  iconColor: "#FF3B30"; active: dashboard ? dashboard.airbagWarn : false; s: 1.5 }
    }
}

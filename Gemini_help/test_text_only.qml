// test_text_only.qml — NO Canvas, just text labels updating from dashboard
import QtQuick 2.15
Item {
    Rectangle { anchors.fill: parent; color: "#0c0c14" }
    Column {
        anchors.centerIn: parent
        spacing: 10
        Text { text: "speed: " + (dashboard ? dashboard.speed.toFixed(1) : 0); color: "white"; font.pixelSize: 24 }
        Text { text: "rpm:   " + (dashboard ? dashboard.rpm.toFixed(0) : 0); color: "white"; font.pixelSize: 24 }
        Text { text: "bat:   " + (dashboard ? dashboard.battery.toFixed(1) : 0); color: "white"; font.pixelSize: 24 }
        Text { text: "fuel:  " + (dashboard ? dashboard.fuelLevel.toFixed(1) : 0); color: "white"; font.pixelSize: 24 }
        Text { text: "cool:  " + (dashboard ? dashboard.coolantTemp.toFixed(1) : 0); color: "white"; font.pixelSize: 24 }
        Text { text: "pow:   " + (dashboard ? dashboard.power.toFixed(1) : 0); color: "white"; font.pixelSize: 24 }
        Text { text: "gear:  " + (dashboard ? dashboard.gear : 0); color: "white"; font.pixelSize: 24 }
    }
}

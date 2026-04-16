import QtQuick 2.15
import QtQuick.Window 2.15

Window {
    id: win
    width: 600; height: 200; visible: true; color: "#0c0c14"

    property int idx: 0
    property var scenarios: [
        { e: true,  o: false, b: false, k: false, a: false, r: false },
        { e: true,  o: true,  b: false, k: false, a: false, r: false },
        { e: false, o: false, b: true,  k: true,  a: false, r: false },
        { e: false, o: false, b: false, k: false, a: true,  r: true  },
        { e: true,  o: true,  b: true,  k: true,  a: true,  r: true  },
        { e: false, o: false, b: false, k: false, a: false, r: false },
    ]

    Timer {
        interval: 2000; running: true; repeat: true
        onTriggered: win.idx = (win.idx + 1) % win.scenarios.length
    }

    WarningLights {
        anchors.centerIn: parent
        s: 2.0
        checkEngine: win.scenarios[win.idx].e
        oilPressure: win.scenarios[win.idx].o
        batteryWarn: win.scenarios[win.idx].b
        brakeWarn:   win.scenarios[win.idx].k
        absWarn:     win.scenarios[win.idx].a
        airbagWarn:  win.scenarios[win.idx].r
    }
}

import QtQuick 2.15
import QtQuick.Window 2.15

Window {
    id: win
    width: 400; height: 500; visible: true; color: "#0c0c14"

    property int idx: 0
    property var scenarios: [
        { fl: true,  fr: false, rl: false, rr: false, h: false, t: false },
        { fl: false, fr: true,  rl: false, rr: false, h: false, t: false },
        { fl: false, fr: false, rl: true,  rr: false, h: false, t: false },
        { fl: false, fr: false, rl: false, rr: true,  h: false, t: false },
        { fl: true,  fr: true,  rl: false, rr: false, h: false, t: false },
        { fl: false, fr: false, rl: true,  rr: true,  h: false, t: false },
        { fl: true,  fr: true,  rl: true,  rr: true,  h: false, t: false },
        { fl: false, fr: false, rl: false, rr: false, h: true,  t: false },
        { fl: false, fr: false, rl: false, rr: false, h: false, t: true  },
        { fl: true,  fr: false, rl: false, rr: true,  h: true,  t: true  },
        { fl: false, fr: false, rl: false, rr: false, h: false, t: false }
    ]

    Timer {
        interval: 3000; running: true; repeat: true
        onTriggered: win.idx = (win.idx + 1) % win.scenarios.length
    }

    DoorStatus {
        anchors.centerIn: parent
        s: 2.5
        doorFL: win.scenarios[win.idx].fl
        doorFR: win.scenarios[win.idx].fr
        doorRL: win.scenarios[win.idx].rl
        doorRR: win.scenarios[win.idx].rr
        hood:   win.scenarios[win.idx].h
        trunk:  win.scenarios[win.idx].t
    }
}

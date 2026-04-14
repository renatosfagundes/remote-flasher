import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    color: "#1e1e2e"

    // plotConfig is set as a context property from Python.
    // It exposes: plots (list of {channels, label, type, window})

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 4
        spacing: 4

        Repeater {
            id: chartRepeater
            model: plotConfig ? plotConfig.plots : []

            ScrollingChart {
                Layout.fillWidth: true
                Layout.fillHeight: true

                chartIndex: index
                channelList: modelData.channels || []
                chartLabel: modelData.label || ("Plot " + (index + 1))
                chartType: modelData.type || "line"
                windowSize: modelData.window || 500
            }
        }
    }

    // Refresh timer — pulls data for all charts at ~30 fps
    Timer {
        interval: 33
        running: true
        repeat: true
        onTriggered: {
            for (var i = 0; i < chartRepeater.count; i++) {
                var chart = chartRepeater.itemAt(i);
                if (chart) chart.refreshData();
            }
        }
    }
}

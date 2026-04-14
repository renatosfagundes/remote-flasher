import QtQuick 2.15
import QtCharts 2.15

ChartView {
    id: root

    // --- Public properties ---
    property int chartIndex: 0
    property var channelList: []       // list of channel indices to plot
    property string chartLabel: ""
    property string chartType: "line"  // "line" or "bar"
    property int windowSize: 500       // visible points

    // Per-channel colors
    readonly property var _colors: [
        "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
        "#9b59b6", "#1abc9c", "#e67e22", "#ecf0f1",
        "#e84393", "#00cec9", "#fdcb6e", "#6c5ce7",
        "#ff7675", "#74b9ff", "#55efc4", "#ffeaa7"
    ]

    antialiasing: true
    theme: ChartView.ChartThemeDark
    backgroundColor: "#1e1e2e"
    plotAreaColor: "#16162a"
    legend.visible: channelList.length > 1
    legend.labelColor: "#ccc"
    title: chartLabel
    titleColor: "#ccc"

    // X axis — sample index
    ValueAxis {
        id: xAxis
        min: 0
        max: windowSize
        labelsColor: "#999"
        gridLineColor: "#333"
        color: "#555"
        labelFormat: "%d"
        tickCount: 6
    }

    // Y axis — auto-scaled
    ValueAxis {
        id: yAxis
        min: 0
        max: 100
        labelsColor: "#999"
        gridLineColor: "#333"
        color: "#555"
        labelFormat: "%.1f"
        tickCount: 6
    }

    // Series are created dynamically based on channelList
    Component.onCompleted: rebuildSeries()

    onChannelListChanged: rebuildSeries()

    function rebuildSeries() {
        removeAllSeries();
        if (!channelList || channelList.length === 0) return;

        for (var i = 0; i < channelList.length; i++) {
            var ch = channelList[i];
            var s = createSeries(ChartView.SeriesTypeLine, "CH" + ch, xAxis, yAxis);
            s.color = _colors[ch % _colors.length];
            s.width = 2;
            s.useOpenGL = true;
        }
    }

    // Called by the refresh timer in Plots.qml
    function refreshData() {
        if (!backend || !channelList || channelList.length === 0) return;

        var globalMinY = Infinity, globalMaxY = -Infinity;

        for (var i = 0; i < channelList.length && i < count; i++) {
            var ch = channelList[i];
            var s = series(i);
            if (!s) continue;

            // Python-side replaces the series data and returns axis bounds
            var info = backend.updateSeriesFromChannel(ch, s);
            if (!info) continue;

            if (info.minY < globalMinY) globalMinY = info.minY;
            if (info.maxY > globalMaxY) globalMaxY = info.maxY;

            // Update X range to show the latest window
            xAxis.min = Math.max(info.minX, info.maxX - windowSize);
            xAxis.max = Math.max(info.maxX, xAxis.min + windowSize);
        }

        // Auto-scale Y with 10% margin
        if (globalMinY !== Infinity) {
            var range = globalMaxY - globalMinY;
            if (range < 1) range = 1;
            var margin = range * 0.1;
            yAxis.min = globalMinY - margin;
            yAxis.max = globalMaxY + margin;
        }
    }
}

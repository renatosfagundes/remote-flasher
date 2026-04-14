import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    color: "#0a0a18"
    radius: 14

    // Subtle border
    Rectangle {
        anchors.fill: parent
        radius: 14
        color: "transparent"
        border.color: "#1a3050"
        border.width: 1.5
    }

    function ch(index) {
        if (!backend) return 0;
        var vals = backend.channelValues;
        return (index >= 0 && index < vals.length) ? vals[index] : 0;
    }

    function gcfg(idx, prop, fallback) {
        if (!gaugeConfig || !gaugeConfig.gauges || idx >= gaugeConfig.gauges.length)
            return fallback;
        var v = gaugeConfig.gauges[idx][prop];
        return v !== undefined ? v : fallback;
    }

    function vcfg(idx, prop, fallback) {
        if (!gaugeConfig || !gaugeConfig.verticals || idx >= gaugeConfig.verticals.length)
            return fallback;
        var v = gaugeConfig.verticals[idx][prop];
        return v !== undefined ? v : fallback;
    }

    // ============================================================
    // MAIN GAUGE CLUSTER — overlapping circular gauges
    // ============================================================
    Item {
        id: clusterArea
        anchors.top: parent.top
        anchors.topMargin: 8
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: infoRow.top
        anchors.bottomMargin: 4

        // Tachometer (left, slightly behind speedometer)
        CircularGauge {
            id: tachGauge
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -10
            x: parent.width * 0.02
            width: clusterArea.height * 0.78
            height: width
            z: 1

            label:    gcfg(0, "label", "RPM")
            units:    gcfg(0, "units", "x1000")
            minValue: gcfg(0, "min", 0)
            maxValue: gcfg(0, "max", 8000)
            arcColor: gcfg(0, "color", "#00e5ff")
            warningThreshold: gcfg(0, "warning", 6500)
            value: ch(gcfg(0, "channel", 0))
        }

        // Speedometer (center, largest, on top)
        CircularGauge {
            id: speedGauge
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -10
            width: clusterArea.height * 0.95
            height: width
            large: true
            z: 2

            label:    gcfg(1, "label", "Speed")
            units:    gcfg(1, "units", "km/h")
            minValue: gcfg(1, "min", 0)
            maxValue: gcfg(1, "max", 200)
            arcColor: gcfg(1, "color", "#00e5ff")
            warningThreshold: gcfg(1, "warning", 180)
            value: ch(gcfg(1, "channel", 1))
        }

        // Temperature arc gauge (right top)
        ArcGauge {
            id: tempGauge
            anchors.right: parent.right
            anchors.rightMargin: parent.width * 0.02
            y: parent.height * 0.05
            width: clusterArea.height * 0.42
            height: clusterArea.height * 0.42
            z: 1

            label:    vcfg(0, "label", "Temp")
            units:    vcfg(0, "units", "\u00b0C")
            minValue: vcfg(0, "min", 0)
            maxValue: vcfg(0, "max", 120)
            arcColor: vcfg(0, "color", "#9b59b6")
            warningThreshold: vcfg(0, "warning", 95)
            value: ch(vcfg(0, "channel", 2))
        }

        // Fuel arc gauge (right bottom)
        ArcGauge {
            id: fuelGauge
            anchors.right: parent.right
            anchors.rightMargin: parent.width * 0.02
            y: parent.height * 0.52
            width: clusterArea.height * 0.42
            height: clusterArea.height * 0.42
            z: 1

            label:    vcfg(1, "label", "Fuel")
            units:    vcfg(1, "units", "%")
            minValue: vcfg(1, "min", 0)
            maxValue: vcfg(1, "max", 100)
            arcColor: vcfg(1, "color", "#f39c12")
            warningThreshold: vcfg(1, "warning", 15)
            value: ch(vcfg(1, "channel", 3))
        }

        // Status lights scattered around the cluster
        Row {
            anchors.top: parent.top
            anchors.topMargin: 4
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 16
            z: 3
            visible: gaugeConfig && gaugeConfig.lights && gaugeConfig.lights.length > 0

            Repeater {
                model: gaugeConfig ? gaugeConfig.lights : []
                StatusLight {
                    label: modelData.label || ""
                    onColor: modelData.color || "#2ecc71"
                    active: {
                        var raw = ch(modelData.channel !== undefined ? modelData.channel : 0);
                        var thresh = modelData.threshold !== undefined ? modelData.threshold : 0.5;
                        return raw >= thresh;
                    }
                }
            }
        }
    }

    // ============================================================
    // INFO CARDS ROW (bottom)
    // ============================================================
    Row {
        id: infoRow
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 8
        height: 55
        spacing: 6
        visible: gaugeConfig && gaugeConfig.infoCards && gaugeConfig.infoCards.length > 0

        Repeater {
            model: gaugeConfig ? gaugeConfig.infoCards : []
            InfoCard {
                width: (infoRow.width - infoRow.spacing *
                       Math.max(0, (gaugeConfig ? gaugeConfig.infoCards.length : 1) - 1))
                       / Math.max(1, gaugeConfig ? gaugeConfig.infoCards.length : 1)
                height: infoRow.height
                label: modelData.label || ""
                units: modelData.units || ""
                accentColor: modelData.color || "#3498db"
                value: {
                    var raw = ch(modelData.channel !== undefined ? modelData.channel : 0);
                    var fmt = modelData.format !== undefined ? modelData.format : 0;
                    return fmt > 0 ? raw.toFixed(fmt) : Math.round(raw).toString();
                }
            }
        }
    }
}

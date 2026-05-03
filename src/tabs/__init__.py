"""Tab widgets for the Remote Flasher application."""
from tabs.vpn_tab import VPNTab
from tabs.flash_tab import FlashTab
from tabs.can_tab import CANTab
from tabs.serial_tab import SerialTab
from tabs.ssh_tab import SSHTerminalTab
from tabs.setup_tab import SetupTab

try:
    from tabs.gauges_tab import GaugesTab
except ImportError:
    GaugesTab = None

try:
    from tabs.hmi_tab import HMIDashboardTab
except ImportError:
    HMIDashboardTab = None

try:
    from tabs.plotter_tab import PlotterTab
except ImportError:
    PlotterTab = None

__all__ = [
    "VPNTab", "FlashTab", "CANTab", "SerialTab", "SSHTerminalTab", "SetupTab",
    "GaugesTab", "HMIDashboardTab", "PlotterTab",
]

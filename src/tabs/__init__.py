"""Tab widgets for the Remote Flasher application."""
from tabs.vpn_tab import VPNTab
from tabs.flash_tab import FlashTab
from tabs.can_tab import CANTab
from tabs.serial_tab import SerialTab
from tabs.ssh_tab import SSHTerminalTab
from tabs.setup_tab import SetupTab
from tabs.gauges_tab import GaugesTab
from tabs.plots_tab import PlotsTab
from tabs.hmi_tab import HMIDashboardTab

__all__ = [
    "VPNTab", "FlashTab", "CANTab", "SerialTab", "SSHTerminalTab", "SetupTab",
    "GaugesTab", "PlotsTab", "HMIDashboardTab",
]

"""Tab widgets for the Remote Flasher application."""
from tabs.vpn_tab import VPNTab
from tabs.flash_tab import FlashTab
from tabs.serial_tab import SerialTab
from tabs.ssh_tab import SSHTerminalTab
from tabs.setup_tab import SetupTab

__all__ = ["VPNTab", "FlashTab", "SerialTab", "SSHTerminalTab", "SetupTab"]

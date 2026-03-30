"""
Secrets template — copy this file to secrets.py and fill in your lab's values.
DO NOT commit secrets.py to version control.
"""

# VPN server address
VPN_ADDRESS = "vpn.example.com"

# SSH credentials for each lab PC
# Add one entry per PC. The key (e.g. "PC 217") must match lab_config.py.
SSH_HOSTS = {
    "PC 217": {
        "host": "192.168.1.100",
        "user": "your_ssh_user",
        "password": "your_ssh_password",
        "camera_url": "http://192.168.1.100:8080/video_feed",
    },
    # "PC 218": { ... },
}

import json
import os

CONFIG_FILE = "settings.json"

DEFAULT_CONFIG = {
    "cameras": [], # List of dicts: {"model": "VSR-20", "ip": "192.168.1.100"}
    "unit_id": "SABRE-1",
    "truenas_ip": "192.168.5.10",
    "truenas_user": "sabre_mounter",
    "truenas_password": ""
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Merge with default config to ensure all keys exist
            merged = DEFAULT_CONFIG.copy()
            merged.update(config)
            return merged
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

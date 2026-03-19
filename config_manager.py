import json
import os

CONFIG_FILE = 'config_rpa.json'

DEFAULT_CONFIG = {
    "PUNKT_HHMMSS": [2453, 496],
    "PUNKT_HH_MM": [2404, 527],
    "PUNKT_DRUKUJ": [2181, 95]
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

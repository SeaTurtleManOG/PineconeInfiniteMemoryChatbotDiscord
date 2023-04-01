import json
from dotenv import load_dotenv
import os

load_dotenv()

def load_config():
    with open("config.json", "r") as config_file:
        config_data = json.load(config_file)
    config_data["CUSTOM_SYSTEM_MESSAGES"] = config_data.get("CUSTOM_SYSTEM_MESSAGES", {})
    return config_data

config = load_config()

def save_custom_system_messages():
    with open("config.json", "w") as config_file:
        json.dump(config, config_file, indent=4)

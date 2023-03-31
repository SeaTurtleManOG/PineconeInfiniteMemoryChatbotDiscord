import json
from config import config
def load_custom_commands(user_id):
    try:
        with open(f"custom_commands_{user_id}.json", "r") as file:
            commands = json.load(file)
    except FileNotFoundError:
        commands = {}
    return commands

def save_custom_commands(user_id, commands):
    with open(f"custom_commands_{user_id}.json", "w") as file:
        json.dump(commands, file, indent=2, sort_keys=True)

def create_custom_command(user_id, command_name, command_action):
    commands = load_custom_commands(user_id)
    commands[command_name] = command_action
    save_custom_commands(user_id, commands)

def execute_custom_command(user_id, command_name):
    commands = load_custom_commands(user_id)
    command_action = commands.get(command_name)
    return command_action
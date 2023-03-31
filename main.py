import discord
from discord.ext import commands
import os
import json
import asyncio
from file_conversion import convert_video_to_audio, download_youtube_video, upload_to_azure
# Import functions from the separate files
from discord_commands import *
from gpt3_functions import *
from utility_functions import *
from config import config


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()

# Initialize the Discord bot with the command prefix and intents
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

# Register Discord bot commands from the discord_commands module
bot.add_command(set_system_message)
bot.add_command(set_convo_length)
bot.add_command(improve)
bot.add_command(convert)
bot.add_command(create_custom)
bot.add_command(custom)
bot.add_command(raven)

# Random messages, lul xD

async def random_messages():
    await bot.wait_until_ready()
    target_channel_id = config.get("TARGET_CHANNEL_ID", None)
    if not target_channel_id:
        print("Error: TARGET_CHANNEL_ID not found or incorrect in the configuration file.")
        return
    target_channel = bot.get_channel(int(target_channel_id))

    while not bot.is_closed():
        user_id = "random_message_generator"
        prompt = "Generate a random message and decide the time delay (in seconds) between messages:"
        
        # Generate a response and time delay using GPT-3
        response = await process_user_input(prompt, user_id, config.get("CONVO_LENGTH", 10)).strip()

        # Extract message and time delay
        response_lines = response.split("\n")
        message, time_delay = response_lines[0].strip(), float(response_lines[1].strip())

        # Send the message to the target channel
        await target_channel.send(f"RAVEN: {message}")

        # Sleep for the specified time delay
        await asyncio.sleep(time_delay)




# Event handler for the bot to display a message when it is connected to Discord
@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")
    bot.loop.create_task(random_messages())

@bot.event
async def on_message(message):
    # Ignore messages sent by the bot itself
    if message.author == bot.user:
        return

    # Process commands
    await bot.process_commands(message)

# Run the Discord bot using the token from the configuration
def main():
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("Error: Discord token not found or incorrect in the configuration file.")

if __name__ == "__main__":
    main()
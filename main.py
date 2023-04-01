import discord
from discord.ext import commands
import os
import json
from file_conversion import convert_video_to_audio, download_youtube_video, upload_to_azure
from pinecone_utils import load_vectors_from_pinecone_to_faiss, load_conversation
from faiss_utils import save_faiss_index, load_faiss_index, get_representative_vectors
from discord_commands import *
from gpt3_functions import *
from utility_functions import *
from config import config
import re

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()

bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

bot.add_command(set_system_message)
bot.add_command(set_convo_length)
bot.add_command(improve)
bot.add_command(convert)
bot.add_command(create_custom)
bot.add_command(custom)
bot.add_command(raven)

if os.path.exists("faiss_index.idx"):
    faiss_index = load_faiss_index("faiss_index.idx")
else:
    load_vectors_from_pinecone_to_faiss()

@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    user_id = str(message.author.id)
    user_input = message.content

    if not user_input.startswith('!'):
        response = await process_user_input(user_input, user_id, config.get("CONVO_LENGTH", 10))
        response = f"RAVEN: {response}"
        await send_large_message(message.channel, response)
    else:
        await bot.process_commands(message)

def main():
    try:
        if DISCORD_TOKEN:
            if os.path.exists("faiss_index.idx"):
                faiss_index = load_faiss_index("faiss_index.idx")
            else:
                load_vectors_from_pinecone_to_faiss()
            bot.run(DISCORD_TOKEN)
        else:
            print("Error: Discord token not found or incorrect in the configuration file.")
    finally:
        save_faiss_index("faiss_index.idx")

if __name__ == "__main__":
    main()

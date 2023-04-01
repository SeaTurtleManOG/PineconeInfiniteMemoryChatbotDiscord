import discord
from discord.ext import commands
import os
import asyncio
from gpt3_functions import process_user_input, summarize_website
from file_conversion import download_youtube_video, upload_to_azure
from file_conversion import convert_video_to_audio
import custom_commands
from time import time
from config import config, save_custom_system_messages
from functools import lru_cache
from datetime import datetime  # Added import statement for 'datetime'

# Cache
cache = {}

# New caching system
@lru_cache(maxsize=256)
async def process_user_input_cached(user_input, user_id, convo_length=10):
    return await process_user_input(user_input, user_id, convo_length)

# Function to send large messages by splitting them into smaller parts
async def send_large_message(channel, message, max_chars=2000):
    message_parts = [message[i:i+max_chars] for i in range(0, len(message), max_chars)]
    for part in message_parts:
        await channel.send(part)
        await asyncio.sleep(1)  # Add asyncio.sleep(1) to avoid hitting rate limits

# Command to set the bot's personality or directive
@commands.command(name="set_system_message")
async def set_system_message(ctx, *, system_message: str):
    user_id = str(ctx.author.id)
    config["CUSTOM_SYSTEM_MESSAGES"][user_id] = system_message
    save_custom_system_messages()
    await ctx.send(f"RAVEN: System message has been set to: '{system_message}'")

# Command to set the conversation length
@commands.command(name="set_convo_length")
async def set_convo_length(ctx, length: int):
    if length < 1 or length > 100:
        await ctx.send("RAVEN: Invalid conversation length. Please set a value between 1 and 100.")
        return
    config["CONVO_LENGTH"] = length
    await ctx.send(f"RAVEN: Conversation length has been set to {length} messages.")

# Command to get suggestions on how to improve the bot's code
@commands.command(name="improve")
async def improve(ctx):
    response = await suggest_improvements()
    response = f"RAVEN: {response}"
    await send_large_message(ctx.channel, response)

# Convert command (youtube link to mp3/wav/mp4)
@commands.command(name="convert")
async def convert(ctx, youtube_url: str, output_format: str):
    if output_format not in ["mp3", "wav", "mp4"]:
        await ctx.send("RAVEN: Invalid output format. Supported formats are 'mp3', 'wav', and 'mp4'.")
        return

    # Download and convert the YouTube video
    video_file = download_youtube_video(youtube_url, output_format)

    if video_file is None:  # Add this check to handle the error case
        await ctx.send("RAVEN: Error downloading and converting YouTube video.")
        return

    temp_file = convert_video_to_audio(video_file, output_format)

    # Check file size and handle uploading to Azure if needed
    file_size = os.path.getsize(temp_file)
    if file_size > 50 * 1024 * 1024:  # 50mb, change '50' to the upload limit of your discord server
        # Upload the file to Azure Blob Storage (use your connection string and container name)
        connection_string = "your_connection_string"
        container_name = "your_container_name"
        
        blob_name = f"{ctx.author.id}_{output_format}_{int(time.time())}.{output_format}"
        sas_url = upload_to_azure(temp_file, connection_string, container_name, blob_name)

        await ctx.send(f"RAVEN: Here's the converted file (link valid for 365 days): {sas_url}")
    else:
        with open(temp_file, "rb") as output_file:
            await ctx.send(f"RAVEN: Here's the converted file.", file=discord.File(output_file, filename=os.path.basename(temp_file)))

    os.remove(video_file)  # Remove the temporary video file
    os.remove(temp_file)   # Remove the temporary audio file

# Custom commands code
@commands.command(name="create_custom")
async def create_custom(ctx, command_name: str, *, command_action: str):
    user_id = str(ctx.author.id)
    custom_commands.create_custom_command(user_id, command_name, command_action)
    await ctx.send(f"RAVEN: Custom command '{command_name}' created.")

@commands.command(name="custom")
async def custom(ctx, command_name: str):
    user_id = str(ctx.author.id)
    command_action = custom_commands.execute_custom_command(user_id, command_name)
    if command_action:
        await ctx.send(f"RAVEN: {command_action}")
    else:
        await ctx.send(f"RAVEN: Custom command '{command_name}' not found.")

# Main command for the bot to process user input and generate responses
@commands.command(name="raven")
async def raven(ctx, *args):
    user_id = str(ctx.author.id)

    if user_id not in config["CUSTOM_SYSTEM_MESSAGES"]:
        response = "Please set a system message for your user by using the !set_system_message command followed by your desired message."
        await ctx.send(f"RAVEN: {response}")
        return

    file_text = None
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        if attachment.filename.endswith(".txt"):
            file_content = await attachment.read()
            file_text = file_content.decode("utf-8")

    user_input = " ".join(args)

    if file_text is not None:
        user_input = f"{user_input} {file_text}"

    if not user_input.strip():
        response = "Please provide a message or a text file attachment to process."
        await ctx.send(f"RAVEN: {response}")
        return

    if user_input.lower() == "what is the current date and time?":
        response = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif user_input.lower().startswith("can you summarize this website for me"):
        url = user_input.split()[-1]
        response = await summarize_website(url)
        cache[user_id] = {"url": url, "summary": response}  # Add this line to store the URL and summary in the cache
    elif "further explain" in user_input.lower() or "the article" in user_input.lower():
        if user_id in cache and "url" in cache[user_id]:  # Check if there is a cached URL and summary for the user
            response = f"I previously summarized an article from {cache[user_id]['url']}. Here is the summary again: {cache[user_id]['summary']} If you need more information, please visit the website or let me know which specific aspect you'd like me to explain further."
        else:
            response = "I'm sorry, but I don't have any recent article summaries to provide more information on. Please provide a URL or more context."
    else:
        convo_length = config.get("CONVO_LENGTH", 10)
        response = await process_user_input_cached(user_input, user_id, convo_length=10)

    response = f"RAVEN: {response}"
    await send_large_message(ctx.channel, response)

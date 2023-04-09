import os
import youtube_dl
import ffmpeg
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, generate_account_sas, AccountSasPermissions, generate_container_sas, ContainerSasPermissions
from datetime import datetime, timedelta
from config import config
from pytube import YouTube
import time
import yt_dlp

def download_youtube_video(youtube_url, output_format):
    try:
        temp_file = f"temp/%(title)s.%(ext)s"

        if output_format in ('mp3', 'wav', 'flac'):
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_file,
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': output_format,
                        'preferredquality': '192',
                    },
                    {'key': 'FFmpegMetadata'}
                ],
            }
        elif output_format == 'mp4':
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': temp_file,
            }
        else:
            return None

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

        # Find the correct output file by searching for files with the video title
        for file in os.listdir("temp"):
            if file.endswith(f".{output_format}"):
                return os.path.join("temp", file)

    except Exception as e:
        print(f"Error downloading YouTube video: {e}")
        return None



def generate_sas_url(blob_service_client, container_name, blob_name):
    container_client = blob_service_client.get_container_client(container_name)
    sas_token = generate_container_sas(
        container_client.account_name,
        container_name,
        blob_service_client.credential.account_key,
        permission=ContainerSasPermissions(read=True, write=True, list=True),
        expiry=datetime.utcnow() + timedelta(days=365)  # No timeout
    )

    return f"https://{container_client.account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"

def upload_to_azure(file_path, container_name, blob_name):
    blob_service_client = BlobServiceClient.from_connection_string(os.getenv("AZURE_CONNECTION_STRING"))
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    with open(file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

    return generate_sas_url(blob_service_client, container_name, blob_name)

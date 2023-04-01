import os
import youtube_dl
import ffmpeg
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, generate_account_sas, AccountSasPermissions, generate_container_sas, ContainerSasPermissions
from datetime import datetime, timedelta
from config import config
from pytube import YouTube
import time


def download_youtube_video(youtube_url, output_format):
    try:
        yt = YouTube(youtube_url)
        if output_format in ["mp3", "wav"]:
            stream = yt.streams.filter(only_audio=True).first()
        elif output_format == "mp4":
            stream = yt.streams.filter(progressive=True, file_extension="mp4").first()
        else:
            return None

        temp_file = f"temp/{stream.default_filename}"
        stream.download(output_path="temp")

        if output_format in ["mp3", "wav"]:
            converted_file = convert_video_to_audio(temp_file, output_format)
            os.remove(temp_file)
            return converted_file  # This line was changed to return the path of the converted audio file
        else:
            return temp_file

    except Exception as e:
        print(f"Error downloading YouTube video: {e}")
        return None

def convert_video_to_audio(input_path, output_format):
    unique_id = int(time.time())
    output_path = f'temp_{unique_id}.{output_format}'
    
    if output_format in ['mp3', 'wav']:
        stream = ffmpeg.input(input_path).output(output_path, format=output_format, acodec='libmp3lame' if output_format == 'mp3' else None)
        ffmpeg.run(stream)

    return output_path

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

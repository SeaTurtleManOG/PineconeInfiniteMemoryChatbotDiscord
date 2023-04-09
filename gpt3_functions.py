import openai
import os
import json
import re
from datetime import datetime
from time import time
import asyncio
import pinecone
from config import config
import numpy as np
import uuid
from uuid import uuid4
import requests
from bs4 import BeautifulSoup
from nltk.tokenize import word_tokenize
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import nltk
import faiss
from browser_automation import get_js_website_content, get_tweet_text
from pinecone_utils import load_vectors_from_pinecone_to_faiss, load_conversation

# Faiss index initialization
dimension = 1536  # GPT-3 embedding dimension for Faiss
faiss_index = faiss.IndexFlatL2(dimension)

def save_faiss_index(filename):
    faiss.write_index(faiss_index, filename)

def load_faiss_index(filename):
    global faiss_index
    faiss_index = faiss.read_index(filename)

index_to_filename_mapping = {}

from utility_functions import (
    open_file,
    save_file,
    load_json,
    save_json,
    truncate_text,
    generate_unique_id,
    get_current_timestamp
)
nltk.download('punkt')

def read_api_key(filename):
    with open(filename, 'r') as file:
        return file.read().strip()

default_vector = [0] * 1536
faiss_results = []

# Initialize openai
openai.api_key_path = "key_openai.txt"
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone.init(api_key=pinecone_api_key, environment="us-west4-gcp")
vdb = pinecone.Index(index_name="turtle-history")

# Function to load conversation history based on user_id and other parameters
def load_conversation(faiss_results, pinecone_results, user_id, max_tokens=2000, max_messages=None):
    result = list()
    fetched_vectors = vdb.fetch(ids=[m["id"] for m in pinecone_results['matches']])
    for m in pinecone_results['matches']:
        file_path = f'nexus/{m["id"]}.json'
        if os.path.exists(file_path):  # Add this check to see if the file exists
            info = load_json(file_path)
            if m["id"] in fetched_vectors:  # Add this check to see if the vector ID exists in fetched_vectors
                info["vector"] = fetched_vectors[m["id"]]  # Replace the loaded vector with the fetched vector
            if info.get('user_id') == user_id or info.get('speaker') == 'RAVEN':
                result.append(info)
    ordered = sorted(result, key=lambda d: d['time'], reverse=False)

    if max_messages:
        ordered = ordered[-max_messages:]

    messages = [i['message'] for i in ordered if i['message'] is not None]  # Filter out None values
    message_block = '\n'.join(messages).strip()

    if len(message_block.split()) > max_tokens:
        message_block = summarize_conversation(message_block, max_tokens)

    return message_block

# Summarize function
async def summarize_website(url):
    if "twitter.com" in url:
        # Use get_tweet_text for Twitter links
        tweet_text = await get_tweet_text(url)
        summary = await gpt3_completion(f"Please summarize the following content from the tweet at {url}:\n\n{tweet_text}")
        summary = summary.strip()

    else:
        # Use get_js_website_content for non-Twitter links
        content = await get_js_website_content(url)
        soup = BeautifulSoup(content, "html.parser")
        paragraphs = soup.find_all("p")
        text = "\n".join(p.get_text() for p in paragraphs)
        summary = await gpt3_completion(f"Please summarize the following content from the website {url}:\n\n{text}")
        summary = summary.strip()

    return summary

# Function to generate an embedding vector for a given text using GPT-3
def gpt3_embedding_1536(content, engine='text-embedding-ada-002'):
    if not content:
        # Handle the empty string case here, for example, return a default vector
        return default_vector
    content = content.encode(encoding='ASCII', errors='ignore').decode()
    response = openai.Embedding.create(input=content, engine=engine)
    vector = response['data'][0]['embedding']

    # Ensure the vector has the correct length (1536)
    if len(vector) != 1536:
        print(f"Warning: The vector length is {len(vector)}, expected 1536.")
        vector = vector[:1536] + [0] * (1536 - len(vector))

    return vector

def update_faiss_index(unique_id, vector_1536, gpt3_embedding_fn):
    global faiss_index, index_to_filename_mapping

    # Convert the list to a NumPy array and reshape
    vector_1536_np = np.array(vector_1536).reshape(1, -1)

    # Add the vector to the Faiss index
    faiss_index.add(vector_1536_np)

    # Update the index_to_filename_mapping dictionary
    index_to_filename_mapping[faiss_index.ntotal - 1] = unique_id
    
    
# Function to process user input and generate a response
async def process_user_input(user_input, user_id, convo_length=10, cache=None):
    response = None
    max_tokens = 4096  # Define the maximum tokens allowed for GPT-3

    # Truncate user_input if it's too long
    tokens = word_tokenize(user_input)
    if len(tokens) > max_tokens:
        user_input = ' '.join(tokens[:max_tokens])

    # Define metadata variables
    timestamp = time()
    message = user_input
    unique_id = str(uuid.uuid4())

    # Userid metadata
    metadata = {
        'speaker': 'USER',
        'time': timestamp,
        'message': message,
        'uuid': unique_id,
        'user_id': user_id,  # Add user ID here
    }

    # Get user input, save it, vectorize it, save to Pinecone
    payload = list()
    message = user_input
    timestamp = time()
    vector = gpt3_embedding_1536(message)
    unique_id = str(uuid4())
    metadata = {'speaker': 'USER', 'time': timestamp, 'message': message, 'uuid': unique_id}
    save_json(f'nexus/{unique_id}.json', metadata)
    payload.append((unique_id, vector))

    # Search for relevant messages in Pinecone and Faiss
    pinecone_results = vdb.query(vector=vector, top_k=convo_length)
    
    # Store the bot's response and user messages in Pinecone
    vector_response = gpt3_embedding_1536(response) if response is not None else vector
    unique_id_response = str(uuid.uuid4())
    metadata_response = {'speaker': 'RAVEN', 'time': time(), 'message': response, 'uuid': unique_id_response}

    # Save the metadata for the response
    save_json(f'nexus/{unique_id_response}.json', metadata_response)

    # Upsert the bot's response and user messages into Pinecone
    vdb.upsert([(unique_id_response, vector_response), (unique_id, vector)])

    # Update Faiss index
    update_faiss_index(unique_id, vector, gpt3_embedding_1536)
    

    
    # Check if the conversation is in the cache
    if user_id in cache:
        conversation = cache[user_id]
    else:
        conversation = load_conversation(faiss_results, pinecone_results, user_id)

    # Truncate conversation if it's too long
    tokens = word_tokenize(conversation)
    if len(tokens) > max_tokens:
        conversation = ' '.join(tokens[:max_tokens])

    system_message = config["CUSTOM_SYSTEM_MESSAGES"].get(str(user_id), config.get("SYSTEM_MESSAGE", ""))
    if not isinstance(system_message, str):
       system_message = ""
    prompt = f"System message: {system_message}\n\nPREVIOUS CONVERSATION:\n\n{conversation}\n\nUSER: {user_input}\n"
    # Generate a response using GPT-3
    response = (await gpt3_completion(prompt, user_id=user_id)).strip()
    
    # Generate response, vectorize, save, etc
    try:
        output = await gpt3_completion(prompt)
    except Exception as error:
        output = str(error)
        # Save error information to Pinecone
        error_metadata = {'speaker': 'RAVEN', 'time': time(), 'error': output, 'uuid': str(uuid4())}
        error_vector = gpt3_embedding_1536(output)
        vdb.upsert([(error_metadata['uuid'], error_vector)])
        save_json('nexus/%s.json' % error_metadata['uuid'], error_metadata)

    info = {'speaker': 'RAVEN', 'time': timestamp, 'vector': vector, 'message': message, 'uuid': str(uuid4())}
    payload.append((unique_id, vector))
    vdb.upsert(payload)
    
    # Save the vector to both Pinecone (1536-dimensional) and Faiss (768-dimensional)
    vector_1536 = gpt3_embedding_1536(message)
    vector_1536_np = np.array(vector_1536).reshape(1, -1)  # Convert the list to a NumPy array and reshape
    faiss_index.add(vector_1536_np)
    vdb.upsert([(unique_id, vector)])
    
    
    # Return the output
    return output
    
    # Clear the cache for the current user
    if user_id in cache:
        del cache[user_id]

# Function to generate a completion using GPT-3 with the given prompt and other parameters
async def gpt3_completion(prompt, user_id=None, model='gpt-4', temp=0.7, top_p=1.0, tokens=400, freq_pen=0.0, pres_pen=0.0, stop=['USER:', 'RAVEN:']):
    max_retry = 5
    retry = 0
    prompt = prompt.encode(encoding='ASCII', errors='ignore').decode()
    while True:
        try:
            system_message = config["CUSTOM_SYSTEM_MESSAGES"].get(str(user_id), config.get("SYSTEM_MESSAGE", ""))
            if not isinstance(system_message, str):
               system_message = ""
            messages = []
            if system_message:
               messages.append({"role": "system", "content": system_message})
               
            if prompt.startswith("USER:"):
               messages.append({"role": "user", "content": prompt[5:]})
            else:
               messages.append({"role": "user", "content": prompt})

            response = openai.ChatCompletion.create(
              model=model,
              messages=messages,
              temperature=temp,
              max_tokens=tokens,
              top_p=top_p,
              frequency_penalty=freq_pen,
              presence_penalty=pres_pen,
              stop=stop)
            text = response['choices'][0]['message']['content'].strip()
            text = re.sub('[\r\n]+', '\n', text)
            text = re.sub('[\t ]+', ' ', text)
            filename = '%s_gpt3.txt' % time()
            if not os.path.exists('gpt3_logs'):
                os.makedirs('gpt3_logs')
            save_file('gpt3_logs/%s' % filename, prompt + '\n\n==========\n\n' + text)
            return text
        except Exception as oops:
            retry += 1
            if retry >= max_retry:
                return "GPT3 error: %s" % oops
            print('Error communicating with OpenAI:', oops)
            await asyncio.sleep(1)

# Initialize openai
openai.api_key = os.environ.get('OPENAI_API_KEY')

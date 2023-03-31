import openai
import os
import json
import re
from time import time
import asyncio
from config import config
import pinecone
import uuid
from uuid import uuid4
import requests
from bs4 import BeautifulSoup
from nltk.tokenize import word_tokenize
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import nltk


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

# Initialize Pinecone and openai
openai.api_key_path = ".env"
openai_api_key = os.getenv("OPENAI_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone.init(api_key=pinecone_api_key, environment="us-west4-gcp")
vdb = pinecone.Index(index_name="yourindexname")


# Function to load conversation history based on user_id and other parameters
def load_conversation(results, user_id, max_tokens=2000, max_messages=None):
    result = list()
    for m in results['matches']:
        info = load_json('nexus/%s.json' % m['id'])
        if info.get('user_id') == user_id:  # Filter messages by user ID using the get() method
            result.append(info)
    ordered = sorted(result, key=lambda d: d['time'], reverse=False)

    if max_messages:
        ordered = ordered[-max_messages:]

    messages = [i['message'] for i in ordered]
    message_block = '\n'.join(messages).strip()

    if len(message_block.split()) > max_tokens:
        message_block = summarize_conversation(message_block, max_tokens)

    return message_block
# SUmmarize function
async def summarize_website(url):
    if "twitter.com" in url:
        # Use Selenium for Twitter links
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        browser = webdriver.Chrome(options=chrome_options)

        try:
            browser.get(url)
            tweet_element = browser.find_element_by_xpath('//div[contains(@data-testid, "tweet")]//div[contains(@class, "css-901oao") and contains(@class, "r-1qd0xha") and contains(@class, "r-a023e6")]')
            tweet_text = tweet_element.text
            summary = await gpt3_completion(f"Please summarize the following content from the tweet at {url}:\n\n{tweet_text}")
            summary = summary.strip()

        except Exception as e:
            summary = f"Error summarizing the website: {e}"

        finally:
            browser.quit()

    else:
        # Use BeautifulSoup for non-Twitter links
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = soup.find_all("p")
        text = "\n".join(p.get_text() for p in paragraphs)
        summary = await gpt3_completion(f"Please summarize the following content from the website {url}:\n\n{text}")
        summary = summary.strip()

    return summary


# Function to process user input and generate a response
async def process_user_input(user_input, user_id, convo_length=10):
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
    vector = gpt3_embedding(message)
    unique_id = str(uuid4())
    metadata = {'speaker': 'USER', 'time': timestamp, 'message': message, 'uuid': unique_id}
    save_json('nexus/%s.json' % unique_id, metadata)
    payload.append((unique_id, vector))

    # Search for relevant messages and generate a response
    results = vdb.query(vector=vector, top_k=convo_length)
    conversation = load_conversation(results, user_id)  # Add user_id parameter

    system_message = config["CUSTOM_SYSTEM_MESSAGES"].get(str(user_id), config.get("SYSTEM_MESSAGE"))
    prompt = f"System message: {system_message}\n\nPREVIOUS CONVERSATION:\n\n{conversation}\n\nUSER: {user_input}\n"

    # Generate response, vectorize, save, etc
    try:
        output = await gpt3_completion(prompt)
    except Exception as error:
        output = str(error)
        # Save error information to Pinecone
        error_metadata = {'speaker': 'RAVEN', 'time': time(), 'error': output, 'uuid': str(uuid4())}
        error_vector = gpt3_embedding(output)
        vdb.upsert([(error_metadata['uuid'], error_vector)])
        save_json('nexus/%s.json' % error_metadata['uuid'], error_metadata)

    info = {'speaker': 'RAVEN', 'time': timestamp, 'vector': vector, 'message': message, 'uuid': str(uuid4())}
    payload.append((unique_id, vector))
    vdb.upsert(payload)

    # Return the output
    return output
    
# Function to generate an embedding vector for a given text using GPT-3
def gpt3_embedding(content, engine='text-embedding-ada-002'):
    content = content.encode(encoding='ASCII', errors='ignore').decode()
    response = openai.Embedding.create(input=content, engine=engine)
    vector = response['data'][0]['embedding']
    return vector

# Function to generate a completion using GPT-3 with the given prompt and other parameters
async def gpt3_completion(prompt, user_id=None, model='gpt-3.5-turbo', temp=0.7, top_p=1.0, tokens=400, freq_pen=0.0, pres_pen=0.0, stop=['USER:', 'RAVEN:']):
    max_retry = 5
    retry = 0
    prompt = prompt.encode(encoding='ASCII', errors='ignore').decode()
    while True:
        try:
            system_message = config["CUSTOM_SYSTEM_MESSAGES"].get(str(user_id), config.get("SYSTEM_MESSAGE", "You are a helpful assistant."))
            messages = [{"role": "system", "content": system_message}]
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
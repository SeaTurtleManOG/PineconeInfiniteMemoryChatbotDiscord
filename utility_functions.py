import json
import os
from time import time
from nltk.tokenize import word_tokenize
import nltk
from config import config
nltk.download('punkt')

# Function to read the contents of a file
def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()

# Function to write the contents to a file
def save_file(filepath, content):
    with open(filepath, 'w', encoding='utf-8') as outfile:
        outfile.write(content)

# Function to load JSON data from a file
def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return json.load(infile)

# Function to save JSON data to a file
def save_json(filepath, payload):
    with open(filepath, 'w', encoding='utf-8') as outfile:
        json.dump(payload, outfile, ensure_ascii=False, sort_keys=True, indent=2)

# Function to truncate text to a specified maximum number of tokens
def truncate_text(text, max_tokens):
    tokens = word_tokenize(text)
    if len(tokens) <= max_tokens:
        return text
    return ' '.join(tokens[:max_tokens])

# Function to generate a unique ID
def generate_unique_id():
    return str(uuid.uuid4())

# Function to get current timestamp
def get_current_timestamp():
    return time()

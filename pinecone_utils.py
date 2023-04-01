import os
import json
import pinecone
from utility_functions import *
index_to_filename_mapping = {}
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone.init(api_key=pinecone_api_key, environment="us-west4-gcp")
vdb = pinecone.Index(index_name="turtle-history")

def load_vectors_from_pinecone_to_faiss():
    global index_to_filename_mapping
    for fname in os.listdir('nexus'):
        if fname.endswith('.json'):
            metadata = load_json(f'nexus/{fname}')
            if 'vector' in metadata:
                vector = np.array(metadata['vector'])
                vector_1536 = gpt3_embedding_1536(metadata['message'])
                faiss_index.add(vector_1536.reshape(1, -1))
                index_to_filename_mapping[faiss_index.ntotal - 1] = fname[:-5]  # Remove the '.json' extension from the filename
    save_json('index_to_filename_mapping.json', index_to_filename_mapping)

# Function to load conversation history based on user_id and other parameters
def load_conversation(faiss_results, pinecone_results, user_id, max_tokens=2000, max_messages=None):
    result = list()
    fetched_vectors = vdb.fetch(ids=[m["id"] for m in pinecone_results['matches']])
    for m in pinecone_results['matches']:
        file_path = f'nexus/{m["id"]}.json'
        if os.path.exists(file_path):  # Add this check to see if the file exists
            info = load_json(file_path)
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

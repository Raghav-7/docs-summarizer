import requests
import json
import time
import sys

URL_BASE = 'https://whatsapp-chat-analyzer-j921.onrender.com'
URL_STATS = f'{URL_BASE}/api/tool/summarize/stats'
URL_AI = f'{URL_BASE}/api/tool/summarize'

print(f"1. Testing Fast Stats Upload at {URL_STATS}...")
start_time = time.time()
try:
    with open('valid_dummy_chat.txt', 'rb') as f:
        resp1 = requests.post(URL_STATS, files={'file': ('valid_dummy_chat.txt', f)})
except Exception as e:
    print(f"Error connecting to {URL_STATS}: {e}")
    sys.exit(1)

stats_time = time.time() - start_time
print(f"Stats Response Code: {resp1.status_code}")
if resp1.status_code != 200:
    print(f"Failed! Response: {resp1.text}")
    sys.exit(1)

data1 = resp1.json()
file_id = data1.get('file_id')
print(f"Success! Stats returned instantly in {stats_time:.2f} seconds.")
print(f"Received file_id: {file_id}")
if not file_id:
    print("CRITICAL ERROR: file_id is missing from stats response!")
    sys.exit(1)

print(f"\n2. Testing AI Summary Endpoint at {URL_AI} with file_id...")
start_time = time.time()
try:
    resp2 = requests.post(URL_AI, data={'file_id': file_id, 'summary_type': 'casual'})
except Exception as e:
    print(f"Error connecting to {URL_AI}: {e}")
    sys.exit(1)
    
ai_time = time.time() - start_time
print(f"AI Response Code: {resp2.status_code}")
if resp2.status_code != 200:
    print(f"Failed! Response: {resp2.text}")
    sys.exit(1)

data2 = resp2.json()
print(f"Success! AI generated summary in {ai_time:.2f} seconds.")
print(f"Summary Length: {len(data2.get('response', ''))} characters.")
print(f"Extracted Chat ID: {data2.get('chat_id')}")

print("\nALL TESTS PASSED: The new Hybrid Fast-Stats Architecture is completely functional in production!")

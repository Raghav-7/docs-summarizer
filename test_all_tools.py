import requests
import os

url = 'http://localhost:5000/api/tool/statistics/stats'

# 1. Test empty file
with open('empty.txt', 'w') as f:
    f.write("")

with open('empty.txt', 'rb') as f:
    resp = requests.post(url, files={'file': f})
    print(f"Empty file: {resp.status_code}")

# 2. Test garbage file
with open('garbage.txt', 'w') as f:
    f.write("hello world this is not a whatsapp chat")

with open('garbage.txt', 'rb') as f:
    resp = requests.post(url, files={'file': f})
    print(f"Garbage file: {resp.status_code}")

# 3. Test valid file
with open('valid_dummy_chat.txt', 'rb') as f:
    resp = requests.post(url, files={'file': f})
    print(f"Valid file: {resp.status_code}")

import requests
import io

url = 'https://whatsapp-chat-analyzer-j921.onrender.com/api/tool/statistics/stats'

try:
    print(f"Testing live URL: {url}")
    with open('valid_dummy_chat.txt', 'rb') as f:
        resp = requests.post(url, files={'file': ('valid_dummy_chat.txt', f)})
    print(f"Live Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Response: {resp.text}")
except Exception as e:
    print(f"Error: {e}")

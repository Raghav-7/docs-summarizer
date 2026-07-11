import zipfile
import os
import io
from app import app

with zipfile.ZipFile('test_large.zip', 'w') as z:
    z.writestr('chat.txt', '12/12/23, 10:00 - Alice: hello\n' * 1000)
    for i in range(10):
        z.writestr(f'image{i}.jpg', '0' * 1024 * 1024)

print(f"Created zip file of size: {os.path.getsize('test_large.zip') / (1024*1024):.2f} MB")

app.config['TESTING'] = True
client = app.test_client()

url = '/api/tool/summarize/stats'
print("Uploading...")
with open('test_large.zip', 'rb') as f:
    resp = client.post(url, data={'file': (f, 'test_large.zip')})
    
print("Status:", resp.status_code)
if resp.status_code != 200:
    print(resp.get_json())

import zipfile
import os
import requests

# Create a dummy large zip file
with zipfile.ZipFile('test_large.zip', 'w') as z:
    z.writestr('chat.txt', '12/12/23, 10:00 - Alice: hello\n' * 1000)
    for i in range(100):
        # Write 1MB of garbage
        z.writestr(f'image{i}.jpg', '0' * 1024 * 1024)

print(f"Created zip file of size: {os.path.getsize('test_large.zip') / (1024*1024):.2f} MB")

url = 'http://localhost:5000/api/tool/summarize/stats'
print("Uploading...")
with open('test_large.zip', 'rb') as f:
    resp = requests.post(url, files={'file': ('test_large.zip', f)})
    
print("Status:", resp.status_code)
if resp.status_code != 200:
    print(resp.text)

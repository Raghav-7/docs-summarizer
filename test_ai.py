import io
from app import app
import json

def test_endpoints():
    app.config['TESTING'] = True
    client = app.test_client()

    url_stats = '/api/tool/summarize/stats'
    url_ai = '/api/tool/summarize'
    
    print("Testing Stats file...")
    with open('valid_dummy_chat.txt', 'rb') as f:
        data = {'file': (io.BytesIO(f.read()), 'valid_dummy_chat.txt')}
    resp = client.post(url_stats, data=data, content_type='multipart/form-data')
    print("Stats:", resp.status_code)
    
    file_id = resp.get_json().get('file_id')
    print("File ID:", file_id)
    
    print("Testing AI endpoint...")
    data2 = {'file_id': file_id}
    resp2 = client.post(url_ai, data=data2, content_type='multipart/form-data')
    print("AI:", resp2.status_code)
    if resp2.status_code != 200:
        print("Error:", resp2.get_json())

if __name__ == '__main__':
    test_endpoints()

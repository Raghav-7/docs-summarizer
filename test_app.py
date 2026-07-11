import io
from app import app

def test_endpoints():
    app.config['TESTING'] = True
    client = app.test_client()

    url = '/api/tool/statistics/stats'
    
    # 1. Empty file
    print("Testing Empty file...")
    data = {'file': (io.BytesIO(b""), 'empty.txt')}
    resp = client.post(url, data=data, content_type='multipart/form-data')
    print("Empty:", resp.status_code, resp.get_json())
    
    # 2. Garbage file
    print("Testing Garbage file...")
    data = {'file': (io.BytesIO(b"garbage not a chat\nand another line"), 'garbage.txt')}
    resp = client.post(url, data=data, content_type='multipart/form-data')
    print("Garbage:", resp.status_code, resp.get_json())
    
    # 3. Valid file
    print("Testing Valid file...")
    with open('valid_dummy_chat.txt', 'rb') as f:
        data = {'file': (io.BytesIO(f.read()), 'valid_dummy_chat.txt')}
    resp = client.post(url, data=data, content_type='multipart/form-data')
    print("Valid:", resp.status_code)

if __name__ == '__main__':
    test_endpoints()

import time

import requests

start = time.time()
resp = requests.post("http://localhost:8000/api/v1/chat", json={"message": "hello"})
end = time.time()
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")
print(f"Time taken: {end - start:.2f} seconds")

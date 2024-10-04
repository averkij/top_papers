#test workflow
print('Start stuff')

from datetime import datetime

with open('test.txt', 'w') as fout:
    fout.write(f'{datetime.now()} some logs...')


#test secret
import os

api_key = os.getenv('TEST_SECRET')
if api_key:
    print(f"The API key is: {api_key}")
else:
    print("API key not found")

with open('test.txt', 'a') as fout:
    fout.write(f'{datetime.now()} {api_key}')


#test LLM API call
import requests

mistral_key = os.getenv('MISTRAL_KEY')
model = "mistral-large-latest"

base_url = "https://api.mistral.ai/v1/chat/completions"
headers = {"Authorization": f"Bearer {mistral_key}", "Content-Type": "application/json"}
payload = {
    "model": model,
    "temperature": 0.7,
    "top_p": 0.95,
    "max_tokens": 128,
    "messages": [
        {"role": "user", "content": "Сочини афоризм про программиста и свинью"}
    ],
}

response = requests.post(base_url, headers=headers, json=payload)
text = response.json()["choices"][0]["message"]["content"]

with open('test.txt', 'a') as fout:
    fout.write(f'{datetime.now()} {text}')
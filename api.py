import json
import os

import anthropic
import requests

from helper import log


API_KEY = os.getenv("CLAUDE_KEY")
client = anthropic.Anthropic(
    api_key=API_KEY,
)
MISTRAL_KEY = os.getenv("MISTRAL_KEY")


def get_data(prompt, system_prompt=""):
    message = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=512,
        system=system_prompt,
        messages=[
            {"role": "user", "content": prompt},
        ],
    )
    resp = message.content[0].text.strip('"')
    log(f"Got response. {resp}")
    try:
        doc = json.loads(resp)
    except:
        log(f"Error. Failed to parse JSON from LLM. {resp}")
        doc = {"error": "Parsing error", "raw_data": resp}

    return doc


def get_text(prompt):
    log(f"Mistral request. {prompt}")
    base_url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "mistral-large-latest",
        "temperature": 0.6,
        "top_p": 0.95,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post(base_url, headers=headers, json=payload)
    log(f"Mistral response. {json.dumps(response.json())}")
    text = response.json()["choices"][0]["message"]["content"]
    return text

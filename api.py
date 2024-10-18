import json
import os
from pathlib import Path

import anthropic
import fal_client
import numpy as np
import openai
import requests

import constants as con
from helper import log

API_KEY = os.getenv("CLAUDE_KEY")
client = anthropic.Anthropic(
    api_key=API_KEY,
)
MISTRAL_KEY = os.getenv("MISTRAL_KEY")
openai.api_key = os.getenv("OPENAI_KEY")


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


def get_text(prompt, api="mistral", model="mistral-large-latest"):
    if api=="mistral":
        log(f"Mistral request. Model: {model}. Prompt: {prompt}")
        base_url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {MISTRAL_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "temperature": 0.2,
            "top_p": 0.95,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = requests.post(base_url, headers=headers, json=payload)
        log(f"Mistral response. {json.dumps(response.json())}")
        text = response.json()["choices"][0]["message"]["content"]
    elif api=="openai":
        log(f"OpenAI request. Model: {model}. Prompt: {prompt}")
        completion = openai.chat.completions.create(
            model=model,
            messages=[
                    # {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
            ])
        text = completion.choices[0].message.content
    else:
        log(f"Error. Unknown API: {api}.")
        text = ""

    return text


def get_embedding(text, size=256):
    try:
        response = openai.embeddings.create(
            input=text, model="text-embedding-3-small", encoding_format="float"
        )
        res = response.data[0].embedding[:256]
        res = normalize_l2(res)

        return res.tolist()
    except Exception as e:
        log(f"Error fetching embedding: {e}")
        return []


def normalize_l2(x):
    x = np.array(x)
    if x.ndim == 1:
        norm = np.linalg.norm(x)
        if norm == 0:
            return x
        return x / norm
    else:
        norm = np.linalg.norm(x, 2, axis=1, keepdims=True)
        return np.where(norm == 0, x, x / norm)


def on_queue_update(update):
    if isinstance(update, fal_client.InProgress):
        for log in update.logs:
           print(log["message"])


def generate_and_save_image(name, prompt):
    log(f'Generating image by prompt: {prompt}.')
    try:
        result = fal_client.subscribe(
            "fal-ai/flux/schnell",
            arguments={
                "prompt": prompt,
                "seed": 42,
                "image_size": "landscape_4_3",
                "num_images": 1
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )
        img = result['images'][0]
        log(f'Saving generated image from {img["url"]} to {name}.')
        Path(con.IMG_DIR).mkdir(exist_ok=True)
        image_path = os.path.join(con.IMG_DIR, name)
        headers = {
                "User-Agent": "Mozilla/5.0"
            }
        response = requests.get(img["url"], headers=headers)
        with open(image_path, 'wb') as fout:
            fout.write(response.content)
    except Exception as e:
        log(f"Error generating an image: {e}")
        result = ""

    return result


def generate_image_for_paper(paper, img_name):
    title = paper["title"]
    abstract = paper["abstract"]
    prompt = f"Write a text with image prompt in style of surrealism and modern art based on the following paper. Use key themes and elements from it. Add instruction to write a text that reads as brief paper title as a label on some object on an image. Return only prompt and nothing else. Title: '{title}' Text: '{abstract}'"
    img_prompt = get_text(prompt, api="openai", model="gpt-4o-mini")
    generate_and_save_image(name=img_name, prompt=img_prompt)
import io
import json
import os
import re
from pathlib import Path

import anthropic
import fal_client
import numpy as np
import openai
import requests
from PIL import Image

import constants as con
from helper import log

CLAUDE_KEY = os.getenv("CLAUDE_KEY")
claude_client = anthropic.Anthropic(
    api_key=CLAUDE_KEY,
)
MISTRAL_KEY = os.getenv("MISTRAL_KEY")
openai.api_key = os.getenv("OPENAI_KEY")


def get_json(prompt, api, model, temperature, system_prompt="You are a helpful assistant."):
    text = get_text(prompt=prompt, system_prompt=system_prompt, api=api, model=model, temperature=temperature)
    text = re.sub(r'```json|```', '', text).strip()
    try:
        doc = json.loads(text)
    except:
        log(f"Error. Failed to parse JSON from LLM. {text}")
        doc = {"error": "Parsing error", "raw_data": text}
    return doc


def get_text(prompt, api, model, temperature=0.5, system_prompt="You are a helpful assistant."):
    if api=="claude":
        log(f"Claude request. Model: {model}. Prompt: {prompt}")
        message = claude_client.messages.create(
            model=model,
            max_tokens=512,
            system=system_prompt,
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=temperature
        )
        text = message.content[0].text.strip('"')
    elif api=="mistral":
        log(f"Mistral request. Model: {model}. Prompt: {prompt}")
        base_url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {MISTRAL_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "temperature": temperature,
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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
            ],
            temperature=temperature)
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


def generate_and_save_image(name, img_dir, prompt):
    log(f'Generating image by prompt: {prompt}.')
    try:
        result = fal_client.subscribe(
            "fal-ai/flux/schnell",
            arguments={
                "prompt": prompt,
                "seed": 42,
                "image_size":  {
                    "width": 384,
                    "height": 720
                    },
                "num_images": 1
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )
        img = result['images'][0]
        log(f'Saving generated image from {img["url"]} to {name}.')
        Path(img_dir).mkdir(exist_ok=True)
        image_path = os.path.join(img_dir, name)
        headers = {
                "User-Agent": "Mozilla/5.0"
            }
        response = requests.get(img["url"], headers=headers)
        image = Image.open(io.BytesIO(response.content))
        output_io = io.BytesIO()
        image.save(output_io, format="JPEG", quality=60)
        output_io.seek(0)        

        with open(image_path, 'wb') as fout:
            fout.write(output_io.read())
    except Exception as e:
        log(f"Error generating an image: {e}")
        result = ""

    return result


def generate_image_for_paper(paper, img_name):
    title = paper["title"]
    abstract = paper["abstract"]
    prompt = f"Write a text with image prompt in style of surrealism and modern art based on the following paper. Use key themes and elements from it. Add instruction to write a text that reads as brief paper title as a label on some object on an image. Return only prompt and nothing else. Title: '{title}' Text: '{abstract}'"
    img_prompt = get_text(prompt, api="openai", model="gpt-4o-mini", temperature=0.8)
    img_dir = os.path.join(con.IMG_DIR, paper["pub_date"].replace('-', ''))
    generate_and_save_image(name=img_name, img_dir=img_dir, prompt=img_prompt)
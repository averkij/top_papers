import io
import json
import os
import re
from pathlib import Path
from typing import Type

import anthropic
import fal_client
import numpy as np
import openai
import requests
from PIL import Image
from pydantic import BaseModel

import constants as con
from helper import log

CLAUDE_KEY = os.getenv("CLAUDE_KEY")
claude_client = anthropic.Anthropic(
    api_key=CLAUDE_KEY,
)
MISTRAL_KEY = os.getenv("MISTRAL_KEY")
openai.api_key = os.getenv("OPENAI_KEY")


class Article(BaseModel):
    desc: str
    title: str

class ArticleFull(BaseModel):
    desc: str
    emoji: str
    title: str


def get_json(prompt, api, model, temperature, system_prompt="You are a helpful assistant."):
    text = get_text(prompt=prompt, system_prompt=system_prompt, api=api, model=model, temperature=temperature)
    text = re.sub(r'```json|```', '', text).strip()
    try:
        doc = json.loads(text)
    except:
        log(f"Error. Failed to parse JSON from LLM. {text}")
        doc = {"error": "Parsing error", "raw_data": text}
    return doc


def get_structured(prompt, cls, model, temperature, system_prompt="You are a helpful assistant."):
    doc = {"error": "Parsing error"}
    resp = ''
    try:
        completion = openai.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_format=cls,
            max_tokens=1024,
            temperature=temperature
        )
        resp = completion.choices[0].message
        if resp.parsed:
            log(f"Response: {resp}")
            doc = resp.parsed.dict()
        elif resp.refusal:
            log(f"Error. Refused. Failed to parse JSON. Response: {resp}")
    except Exception as e:
        log(f"Error. Failed to parse JSON. Details: {e}. Response: {resp}")
        doc["raw_data"] = resp

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
            "top_p": 1 if temperature==0 else 0.95,
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

    log(f"Response: {text}")
    if any([x in text for x in con.RENAME_TERMS.keys()]):
        log('Renaming some terms.')
        for k,v in con.RENAME_TERMS.items():
            text = text.replace(k,v)        

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
    prompt = f"Write a text with image prompt in style of surrealism and modern art based on the following paper. Use key themes and elements from it. Add instruction to write a text that reads as brief paper title as a label on some object on an image. Style: linear art on white background. Return only prompt and nothing else. Title: '{title}' Text: '{abstract}'"
    img_prompt = get_text(prompt, api="openai", model="gpt-4o-mini", temperature=0.8)
    img_dir = os.path.join(con.IMG_DIR, paper["pub_date"].replace('-', ''))
    generate_and_save_image(name=img_name, img_dir=img_dir, prompt=img_prompt)


def get_categories(text):
    prompt_cls = (
            f"""You are an expert classifier of machine learning research papers. Analyze the following research paper text and classify it into one or more relevant categories from the list below. Consider the paper's main contributions, methodologies, and applications.

Categories:
1. DATASET: Papers that introduce new datasets or make significant modifications to existing ones
2. DATA: Papers focusing on data processing, cleaning, collection, or curation methodologies
3. BENCHMARK: Papers proposing or analyzing model evaluation frameworks and benchmarks
4. AGENTS: Papers exploring autonomous agents, web agents, or agent-based architectures
5. CV: Papers developing computer vision methods or visual processing systems
6. RL: Papers investigating reinforcement learning theory or applications
7. RLHF: Papers specifically about human feedback in RL (PPO, DPO, etc.)
8. RAG: Papers advancing retrieval-augmented generation techniques
9. PLP: Papers about Programming Language Processing models or programming benchmarks
10. INFERENCE: Papers optimizing model deployment (quantization, pruning, etc.)
11. 3D: Papers on 3D content generation, processing, or understanding
12. AUDIO: Papers advancing speech/audio processing or generation
13. VIDEO: Papers on video analysis, generation, or understanding
14. MULTIMODAL: Papers combining multiple input/output modalities
15. MATH: Papers focused on mathematical theory and algorithms
16. MULTILINGUAL: Papers addressing multiple languages or cross-lingual capabilities
17. ARCHITECTURE: Papers proposing novel neural architectures or components
18. MEDICINE: Papers applying ML to medical/healthcare domains
19. TRAINING: Papers improving model training or fine-tuning methods
20. ROBOTICS: Papers on robotic systems and embodied AI
21. AGI: Papers discussing artificial general intelligence concepts
22. GAMES: Papers applying ML to games or game development
23. INTERPRETABILITY: Papers analyzing model behavior and explanations
24. REASONING: Papers enhancing logical reasoning capabilities
25. TRANSFER_LEARNING: Papers on knowledge transfer between models/domains
26. GRAPHS: Papers advancing graph neural networks and applications
27. ETHICS: Papers addressing AI ethics, fairness, and bias
28. SECURITY: Papers on model security and adversarial robustness
29. EDGE_COMPUTING: Papers on ML deployment for resource-constrained devices
30. OPTIMIZATION: Papers advancing training optimization methods
31. SURVEY: Papers comprehensively reviewing research areas
32. DIFFUSION: Papers on diffusion-based generative models
33. ALIGNMENT: Papers about aligning language models with human values, preferences, and intended behavior
34. STORY_GENERATION: Papers on story generation, including plot generation and author style adaptation
35. HALLUCINATIONS: Papers about the hallucinations, hallucinations analysis and mitigation
36. LONG_CONTEXT: Papers about long context handling, including techniques to extend context length and process long sequences.
37. SYNTHETIC: Papers about using synthetic data for training, including methods for generating and leveraging artificial data.

Return only JSON with flat array of categories that match the given text.

Paper text to classify:\n\n"{text}"
"""
        )    
    categories = get_json(prompt_cls, api="openai", model="gpt-4o-mini", temperature=0.0)

    return categories
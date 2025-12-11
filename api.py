import io
import json
import os
import re
from pathlib import Path

import anthropic
import fal_client
import numpy as np
import openai
from openai import OpenAI
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

XAI_API_KEY = os.getenv("XAIAPI_KEY")
# client_xai = OpenAI(
#     api_key=XAI_API_KEY,
#     base_url="https://api.x.ai/v1",
# )


class Article(BaseModel):
    desc: str
    title: str

class List(BaseModel):
    items: list[str]

class ArticleFull(BaseModel):
    desc: str
    emoji: str
    title: str


def get_json(
    prompt, api, model, temperature, system_prompt="You are a helpful assistant."
):
    text = get_text(
        prompt=prompt,
        system_prompt=system_prompt,
        api=api,
        model=model,
        temperature=temperature,
    )
    text = re.sub(r"```json|```python|```", "", text).strip()
    try:
        doc = json.loads(text)
    except:
        try:
            text = text.replace("'", '"')
            doc = json.loads(text)
        except:
            log(f"Error. Failed to parse JSON from LLM. {text}")
            doc = {"error": "Parsing error", "raw_data": text}
    return doc


def get_structured(
    prompt, cls, model, temperature, system_prompt="You are a helpful assistant."
):
    doc = {"error": "Parsing error"}
    resp = ""
    try:
        completion = openai.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format=cls,
            max_tokens=1024,
            temperature=temperature,
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


def get_text(
    prompt, api, model, temperature=0.5, system_prompt="You are a helpful assistant."
):
    if api == "claude":
        log(f"Claude request. Model: {model}. Prompt: {prompt}")
        message = claude_client.messages.create(
            model=model,
            max_tokens=512,
            system=system_prompt,
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        text = message.content[0].text.strip('"')
    elif api == "mistral":
        log(f"Mistral request. Model: {model}. Prompt: {prompt}")
        base_url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {MISTRAL_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "temperature": temperature,
            "top_p": 1 if temperature == 0 else 0.95,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = requests.post(base_url, headers=headers, json=payload)
        log(f"Mistral response. {json.dumps(response.json())}")
        text = response.json()["choices"][0]["message"]["content"]
    elif api == "openai":
        log(f"OpenAI request. Model: {model}. Prompt: {prompt}")
        completion = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        text = completion.choices[0].message.content
    elif api == "xai":
        log(f"XAI request. Model: {model}. Prompt: {prompt}")
        completion = client_xai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        text = completion.choices[0].message.content
    else:
        log(f"Error. Unknown API: {api}.")
        text = ""

    log(f"Response: {text}")
    if any([x in text for x in con.RENAME_TERMS.keys()]):
        log("Renaming some terms.")
        for k, v in con.RENAME_TERMS.items():
            text = text.replace(k, v)

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
    log(f"Generating image by prompt: {prompt}.")
    try:
        result = fal_client.subscribe(
            "fal-ai/flux/schnell",
            arguments={
                "prompt": prompt,
                "seed": 42,
                "image_size": {"width": 384, "height": 720},
                "num_images": 1,
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )
        img = result["images"][0]
        log(f'Saving generated image from {img["url"]} to {name}.')
        Path(img_dir).mkdir(exist_ok=True)
        image_path = os.path.join(img_dir, name)
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(img["url"], headers=headers)
        image = Image.open(io.BytesIO(response.content))
        output_io = io.BytesIO()
        image.save(output_io, format="JPEG", quality=60)
        output_io.seek(0)

        with open(image_path, "wb") as fout:
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
    img_dir = os.path.join(con.IMG_DIR, paper["pub_date"].replace("-", ""))
    generate_and_save_image(name=img_name, img_dir=img_dir, prompt=img_prompt)


def get_categories(text, api="claude", model="claude-haiku-4-5"):
    prompt_cls_1 = f"""Analyze the following research paper text and classify it into one or more relevant topics from the list below. Consider only information from the provided text. Don't add a tag if the topic is not directly related to the article.

Topics:

DATASET: Papers that introduce new datasets or make significant modifications to existing ones
DATA: Papers focusing on data processing, cleaning, collection, or curation methodologies
BENCHMARK: Papers proposing or analyzing model evaluation frameworks and benchmarks
AGENTS: Papers exploring autonomous agents, web agents, or agent-based architectures
CV: Papers developing computer vision methods or visual processing systems
RL: Papers investigating reinforcement learning theory or applications
RLHF: Papers specifically about human feedback in RL (PPO, DPO, etc.)
RAG: Papers advancing retrieval-augmented generation techniques
PLP: Papers about Programming Language Processing models or programming benchmarks
INFERENCE: Papers optimizing model deployment (quantization, pruning, etc.)
3D: Papers on 3D content generation, processing, or understanding
AUDIO: Papers advancing speech/audio processing or generation
VIDEO: Papers on video analysis, generation, or understanding
MULTIMODAL: Papers combining multiple input/output modalities
MATH: Papers focused on mathematical theory and algorithms
MULTILINGUAL: Papers addressing multiple languages or cross-lingual capabilities, including all non English models
ARCHITECTURE: Papers proposing novel neural architectures or components
HEALTHCARE: Papers applying ML to medical/healthcare domains
TRAINING: Papers improving model training or fine-tuning methods
ROBOTICS: Papers on robotic systems and embodied AI
SMALL_MODELS: Papers that describe models considering small, below 1 billion parameters or similar 

Return only a Python flat list of topics that match the given text.

Paper text to classify:\n\n"{text}"
"""
    
    prompt_cls_2 = f"""Analyze the following research paper text and classify it into one or more relevant topics from the list below. Consider only information from the provided text. Don't add a tag if the topic is not directly related to the article.

Topics:

AGI: Papers discussing artificial general intelligence concepts
GAMES: Papers applying ML to games or game development
INTERPRETABILITY: Papers analyzing model behavior and explanations
REASONING: Papers enhancing logical reasoning capabilities
TRANSFER_LEARNING: Papers on knowledge transfer between models/domains
GRAPHS: Papers advancing graph neural networks and applications
ETHICS: Papers addressing AI ethics, fairness, and bias
SECURITY: Papers on model security and adversarial robustness
OPTIMIZATION: Papers advancing training optimization methods
SURVEY: Papers comprehensively reviewing research areas
DIFFUSION: Papers on diffusion-based generative models
ALIGNMENT: Papers about aligning language models with human values, preferences, and intended behavior
STORY_GENERATION: Papers on story generation, including plot generation and author style adaptation
HALLUCINATIONS: Papers about the hallucinations, hallucinations analysis and mitigation
LONG_CONTEXT: Papers about long context handling, including techniques to extend context length
SYNTHETIC: Papers about using synthetic data for training, including methods for generating and leveraging artificial data
TRANSLATION: Papers on machine translation, including techniques, data and applications for translating between languages
LEAKAGE: Papers about data leakage, including issues of unintended data exposure and methods to detect or prevent it
OPEN_SOURCE: Papers that contribute to open-source projects by releasing models, datasets, or frameworks to the public
SCIENCE: Papers on scientific applications of LM including understanding of science articles and research automatization
LOW_RESOURCE: Papers that mention low-resource languages

Return only a Python flat list of topics that match the given text.

Paper text to classify:\n\n"{text}"
"""

#     prompt_cls = f"""{{
#   "task": "Classify the following machine learning research paper into one or more relevant categories.",
#   "instructions": "Analyze the provided research paper text and classify it into one or more of the categories listed below. Focus on the paper's main contributions, methodologies, and applications.",
#   "categories": [
#     {{
#       "name": "DATASET",
#       "description": "Papers that introduce new datasets or significantly modify existing ones for research purposes."
#     }},
#     {{
#       "name": "DATA",
#       "description": "Papers focusing on methodologies for data processing, cleaning, collection, or curation."
#     }},
#     {{
#       "name": "BENCHMARK",
#       "description": "Papers proposing or analyzing frameworks for evaluating models or benchmarks."
#     }},
#     {{
#       "name": "AGENTS",
#       "description": "Papers exploring autonomous agents, web agents, or agent-based architectures."
#     }},
#     {{
#       "name": "CV",
#       "description": "Papers developing methods in computer vision or visual processing systems."
#     }},
#     {{
#       "name": "RL",
#       "description": "Papers investigating reinforcement learning theory or its applications."
#     }},
#     {{
#       "name": "RLHF",
#       "description": "Papers specifically about incorporating human feedback into reinforcement learning (e.g., PPO, DPO)."
#     }},
#     {{
#       "name": "RAG",
#       "description": "Papers advancing techniques for retrieval-augmented generation."
#     }},
#     {{
#       "name": "PLP",
#       "description": "Papers about programming language processing models or programming benchmarks."
#     }},
#     {{
#       "name": "INFERENCE",
#       "description": "Papers optimizing model deployment, including techniques like quantization or pruning."
#     }},
#     {{
#       "name": "3D",
#       "description": "Papers on 3D content generation, processing, or understanding."
#     }},
#     {{
#       "name": "AUDIO",
#       "description": "Papers advancing speech or audio processing or generation."
#     }},
#     {{
#       "name": "VIDEO",
#       "description": "Papers on video analysis, generation, or understanding."
#     }},
#     {{
#       "name": "MULTIMODAL",
#       "description": "Papers combining multiple input/output modalities."
#     }},
#     {{
#       "name": "MATH",
#       "description": "Papers focused on mathematical theory and algorithms in machine learning."
#     }},
#     {{
#       "name": "MULTILINGUAL",
#       "description": "Papers addressing multiple languages or cross-lingual capabilities, including non-English models."
#     }},
#     {{
#       "name": "ARCHITECTURE",
#       "description": "Papers proposing novel neural architectures or components."
#     }},
#     {{
#       "name": "MEDICINE",
#       "description": "Papers applying machine learning to medical or healthcare domains."
#     }},
#     {{
#       "name": "TRAINING",
#       "description": "Papers improving model training or fine-tuning methods."
#     }},
#     {{
#       "name": "ROBOTICS",
#       "description": "Papers on robotic systems and embodied AI."
#     }},
#     {{
#       "name": "AGI",
#       "description": "Papers discussing concepts related to artificial general intelligence."
#     }},
#     {{
#       "name": "GAMES",
#       "description": "Papers applying machine learning to games or game development."
#     }},
#     {{
#       "name": "INTERPRETABILITY",
#       "description": "Papers analyzing model behavior and providing explanations."
#     }},
#     {{
#       "name": "REASONING",
#       "description": "Papers enhancing logical reasoning capabilities in AI systems."
#     }},
#     {{
#       "name": "TRANSFER_LEARNING",
#       "description": "Papers on knowledge transfer between models or domains."
#     }},
#     {{
#       "name": "GRAPHS",
#       "description": "Papers advancing graph neural networks and their applications."
#     }},
#     {{
#       "name": "ETHICS",
#       "description": "Papers addressing AI ethics, fairness, and bias."
#     }},
#     {{
#       "name": "SECURITY",
#       "description": "Papers on model security and adversarial robustness."
#     }},
#     {{
#       "name": "EDGE_COMPUTING",
#       "description": "Papers on deploying machine learning models on resource-constrained devices."
#     }},
#     {{
#       "name": "OPTIMIZATION",
#       "description": "Papers advancing training optimization methods."
#     }},
#     {{
#       "name": "SURVEY",
#       "description": "Papers comprehensively reviewing research areas."
#     }},
#     {{
#       "name": "DIFFUSION",
#       "description": "Papers on diffusion-based generative models."
#     }},
#     {{
#       "name": "ALIGNMENT",
#       "description": "Papers about aligning language models with human values, preferences, and intended behavior."
#     }},
#     {{
#       "name": "STORY_GENERATION",
#       "description": "Papers on story generation, including plot generation and author style adaptation."
#     }},
#     {{
#       "name": "HALLUCINATIONS",
#       "description": "Papers about model hallucinations, their analysis, and mitigation strategies."
#     }},
#     {{
#       "name": "LONG_CONTEXT",
#       "description": "Papers about handling long contexts, including techniques to extend context length."
#     }},
#     {{
#       "name": "SYNTHETIC",
#       "description": "Papers about using synthetic data for training, including methods for generating and leveraging artificial data."
#     }},
#     {{
#       "name": "TRANSLATION",
#       "description": "Papers about machine translation, including techniques, data, and applications for translating between languages."
#     }},
#     {{
#       "name": "LEAKAGE",
#       "description": "Papers about data leakage, including issues of unintended data exposure and methods to detect or prevent it."
#     }},
#     {{
#       "name": "OPEN_SOURCE",
#       "description": "Papers that contribute to open-source projects by releasing models, datasets, or frameworks to the public."
#     }},
#     {{
#       "name": "MODELS",
#       "description": "Papers that describe machine learning models, whether they are open-source or proprietary."
#     }}
#   ],
#   "paper_text": "{text}",
#   "output_format": "Return only a Python flat list of categories that match the given text."
# }}"""
    categories_1 = get_json(
        prompt_cls_1, api=api, model=model, temperature=0.0
    )
    categories_2 = get_json(
        prompt_cls_2, api=api, model=model, temperature=0.0
    )

    # res = []
    # for c in categories:
    #     if c in CAT_MAPPING:
    #         res.append(CAT_MAPPING[c])

    categories = list(set(categories_1 + categories_2))

    return categories


def get_categories_additional(text, api="claude", model="claude-haiku-4-5"):
    prompt_cls = f"""You are an expert classifier of machine learning research papers. Analyze the following research paper text and classify it into one or more relevant categories from the list below.

Categories:
1. MULTILINGUAL: Papers addressing multiple languages or cross-lingual capabilities, including all non English models
2. LONG_CONTEXT: Papers about long context handling, including techniques to extend context length
3. SYNTHETIC: Papers about using synthetic data for training, including methods for generating and leveraging artificial data
4. TRANSLATION: Papers about machine translation, including techniques, data and applications for translating between languages
5. TRAINING: Papers about machine translation, including techniques, data and applications for translating between languages

Return only JSON with flat array of categories that match the given text. If no category fit return empty list.

Paper text to classify:\n\n"{text}"
"""
    categories = get_json(
        prompt_cls, api=api, model=model, temperature=0.0
    )
    categories = [x for x in categories if x not in con.EXCLUDE_CATS]
    categories = [
        x if x not in con.RENAME_CATS else con.RENAME_CATS[x] for x in categories
    ]
    categories = [f"#{x.replace('#','')}".lower() for x in categories]

    return categories

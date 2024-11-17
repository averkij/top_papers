
import os

TITLE_LIGHT = "hf daily"
TITLE_LIGHT_MONTHLY = "hf monthly"
TITLE_DARK = "hf nightly"
TITLE_DARK_MONTHLY = "hf moonly"

DATA_FILE = "hf_papers.json"
PAGE_FILE = "index.html"
LOG_FILE = "log.txt"

LOG_DIR = "./logs"
IMG_DIR = "./img"
DATA_DIR = "./d"

ASSETS_DIR = "./assets"
PAPER_PDF_DIR = os.path.join(ASSETS_DIR, "pdf")
PAPER_PDF_TITLE_IMG = os.path.join(PAPER_PDF_DIR, "title_img")
PAPER_TEXT_DIR = os.path.join(ASSETS_DIR, "texts")
PAPER_JSON_DIR = os.path.join(ASSETS_DIR, "json")
PAPER_IMG_DATA_DIR = os.path.join(ASSETS_DIR, "img_data")

PAPER_PDF_IMAGE_STUB = "img/title_stub.png"

EXCLUDE_CATS = [
    "#ai",
    "#ml",
    "#machinelearning",
    "#machine-learning",
    "#generative",
    "#llm",
    "#autoregressive",
    "#classification",
    "#generative_models",
    "#human_computer_interaction",
    "#nlp",
    "#planning",
    "#editing",
]
RENAME_CATS = {
    "#multi-modal": "#multimodal",
    "#transformer": "#transformers",
    "#efficiency": "#optimization",
    "#deployment": "#inference",
    "#deploy": "#inference",
    "#motion": "#3d",
    "#mathematics": "#math",
    "#humancomputerinteraction": "#interaction",
    "#algorithm": "#algo",
    "#algorithms": "#algo",
    "#cnn": "#architecture",
    "#prompt": "#prompts",
    "#graph": "#graphs",
    "#translation": "#machine_translation",
}
RENAME_TERMS = {
    'БЯМ': 'LLM'
}
CATEGORIES = {
    '#dataset': 0,
    '#data': 0,
    '#benchmark': 0,
    '#agents': 0,
    '#cv': 0,
    '#rl': 0,
    '#rlhf': 0,
    '#rag': 0,
    '#plp': 0,
    '#inference': 0,
    '#3d': 0,
    '#audio': 0,
    '#video': 0,
    '#multimodal': 0,
    '#math': 0,
    '#multilingual': 0,
    '#architecture': 0,
    '#healthcare': 0,
    '#training': 0,
    '#robotics': 0,
    '#agi': 0,
    '#games': 0,
    '#interpretability': 0,
    '#reasoning': 0,
    '#transfer_learning': 0,
    '#graphs': 0,
    '#ethics': 0,
    '#security': 0,
    '#optimization': 0,
    '#survey': 0,
    '#diffusion': 0,
    '#alignment': 0,
    '#story_generation': 0,
    '#hallucinations': 0,
    '#long_context': 0,
    '#synthetic': 0,
    '#machine_translation': 0,
    '#leakage': 0,
    '#open_source': 0,
    '#small_models': 0,
    '#science': 0,
    '#low_resource': 0
}

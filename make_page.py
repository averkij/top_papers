# %%
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
import requests
from babel.dates import format_date
from bs4 import BeautifulSoup
from tqdm import tqdm

TITLE_LIGHT = "хф дэйли"
TITLE_DARK = "хф найтли"

LOG_FILE = "log.txt"
DATA_FILE = "hf_papers.json"
PAGE_FILE = "index.html"

LOG_DIR = "./logs"
DATA_DIR = "./prev_papers"

Path(LOG_DIR).mkdir(exist_ok=True)
Path(DATA_DIR).mkdir(exist_ok=True)

CURRENT_YEAR = datetime.now().year
CURRENT_DATE = datetime.now()

EXCLUDE_CATS = [
    "#ai",
    "#ml",
    "#machinelearning",
    "#machine-learning",
    "#generative",
    "#llm",
    "#autoregressive",
    "#training",
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
}


def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as fout:
        date = datetime.now().strftime("%d.%m.%Y %H:%M")
        fout.write(f"[{date}] {msg}\n")


def try_rename_file(fpath, dir, new_name=None):
    if not new_name:
        new_name = fpath
    if os.path.isfile(fpath):
        date = datetime.now() - timedelta(1)
        date = date.strftime("%Y-%m-%d")
        new_fpath = f"{date}_{new_name}"
        log(f"Renaming previous data. {fpath} to {new_fpath}")
        try:
            os.remove(new_fpath)
        except OSError:
            pass
        os.replace(fpath, os.path.join(dir, new_fpath))
    else:
        log(f"No file to rename. {fpath}")


def try_get_score(text):
    score_pat = re.compile(r'<div class="leading-none">(\d+)<\/div>')
    score = score_pat.findall(str(text))
    score = int(score[0]) if score else 0
    return score


def parse_and_format_date(date_str, year=CURRENT_YEAR):
    try:
        date_obj = datetime.strptime(date_str, "%b %d").replace(year=year)
        date_sort = date_obj.strftime("%Y-%m-%d")
        date_ru = format_date(date_obj, format="d MMMM", locale="ru_RU")
    except:
        date_sort = "2024-01-01"
        date_ru = format_date(CURRENT_DATE, format="d MMMM", locale="ru_RU")
        log(f"Error. Unable to format date {date_str}")
    return date_sort, date_ru


if os.path.isfile(DATA_FILE):
    # log('Read previous papers.')
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        PREV_PAPERS = json.load(f)
else:
    log("No previous papers found.")
    PREV_PAPERS = {}

if "issue_id" in PREV_PAPERS:
    ISSUE_ID = PREV_PAPERS["issue_id"]
else:
    ISSUE_ID = 0


def try_get_prev_paper(paper):
    prev_data = None
    if "papers" in PREV_PAPERS:
        prev_ids = [x["id"] for x in PREV_PAPERS["papers"]]
        if paper["id"] in prev_ids:
            prev_data = [x for x in PREV_PAPERS["papers"] if x["id"] == paper["id"]][0]
    return prev_data, bool(prev_data)


log("Get feed.")

# modified version of https://github.com/capjamesg/hugging-face-papers-rss/blob/main/app.py
BASE_URL = "https://huggingface.co/papers"

page = requests.get(BASE_URL)
soup = BeautifulSoup(page.content, "html.parser")
articles = soup.find_all("article")
papers = []


def try_parse_pub_date(soup):
    pat = r"Published on (\w+ \d{1,2})"
    for s in soup:
        m = re.search(pat, s.text)
        if m:
            return m.group(1)
    return None


def extract_page_data(url):
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "html.parser")
    abstract = soup.find("div", {"class": "pb-8 pr-4 md:pr-16"}).text
    if abstract.startswith("Abstract\n"):
        abstract = abstract[len("Abstract\n") :]
    abstract = abstract.replace("\n", " ")

    main = soup.find("main")
    main_divs = main.find_all("div")
    pub_date_str = try_parse_pub_date(main_divs)
    pub_date, pub_date_ru = parse_and_format_date(pub_date_str)

    res = {
        "abstract": abstract.strip(),
        "pub_date": pub_date,
        "pub_date_ru": pub_date_ru,
    }

    return res


for article in tqdm(articles):
    h3 = article.find("h3")
    a = h3.find("a")
    title = a.text
    link = a["href"]
    url = f"https://huggingface.co{link}"
    prev_data, ok = try_get_prev_paper({"id": url})
    issue_id = ISSUE_ID + 1
    try:
        if ok:
            log(f"Get page data from previous paper. URL: {url}")
            abstract = prev_data["abstract"]
            issue_id = prev_data["issue_id"] if "issue_id" in prev_data else ISSUE_ID
            pub_date = (
                prev_data["pub_date"] if "pub_date" in prev_data else "1963-01-17"
            )
            pub_date_ru = (
                prev_data["pub_date_ru"]
                if "pub_date_ru" in prev_data
                else "надцатого мартобря"
            )
        else:
            log(f"Extract page data from URL. URL: {url}")
            page_data = extract_page_data(url)
            abstract = page_data["abstract"]
            pub_date = page_data["pub_date"]
            pub_date_ru = page_data["pub_date_ru"]

    except Exception as e:
        log(f"Failed to extract page data for {url}: {e}")
        abstract = ""

    papers.append(
        {
            "id": url,
            "title": title,
            "url": url,
            "abstract": abstract,
            "score": try_get_score(article),
            "issue_id": issue_id,
            "pub_date": pub_date,
            "pub_date_ru": pub_date_ru,
        }
    )

# %%
formatted_date = format_date(CURRENT_DATE, format="d MMMM", locale="ru_RU")
formatted_time_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

feed = {
    "date": formatted_date,
    "time_utc": formatted_time_utc,
    "issue_id": ISSUE_ID + 1,
    "home_page_url": BASE_URL,
    "papers": papers,
}

for i, paper in enumerate(feed["papers"]):
    log("*" * 80)
    log(f'Abstract {i}. {paper["abstract"][:300]}...')

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
    base_url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "mistral-large-latest",
        "temperature": 0.6,
        "top_p": 0.95,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post(base_url, headers=headers, json=payload)
    text = response.json()["choices"][0]["message"]["content"]
    return text


if os.path.isfile(DATA_FILE):
    log("Read previous papers.")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        PREV_PAPERS = json.load(f)
else:
    log("No previous papers found.")
    PREV_PAPERS = {}

log("Generating reviews via LLM API.")
for paper in tqdm(feed["papers"]):
    prev_data, ok = try_get_prev_paper(paper)

    if ok:
        log(
            f'Using data from previous issue: {json.dumps(prev_data["data"], ensure_ascii=False)[:300]}'
        )
        paper["data"] = prev_data["data"]
    else:
        log("Querying the API.")
        abs = paper["abstract"][:3000]

        system_prompt = "You are explaining concepts in simple words in good and native Russian. But you are using English terms like LLM and AI instead of Russian when appropriate."

        prompt = f"Read an abstract of the ML paper and return a JSON with fields: 'desc': explanation of the paper in Russian (4 sentences), use correct machine learning terms. 'tags': array of tags related to article, 3 tags, but specific, not general like #ml or #ai. 'categories': array of tags related to article, up to 5 tags, but the most general like #nlp, #cv, #rlhf, #dataset (if authors contributing a dataset), #benchmark (if article is about benchmarking), #rag (if article is about retrieval augmented generation), #code (if article about code models), #video, #multimodal, etc. All tags must be relative to article. Do not add irrelevant tags. 'emoji': emoji that will reflect the theme of an article somehow, only one emoji. 'title': a slogan of a main idea of the article in Russian. Return only JSON and nothing else.\n\n{abs}"

        paper["data"] = get_data(prompt, system_prompt=system_prompt)

    # fix categories
    if "categories" in paper["data"]:
        paper["data"]["categories"] = [
            x for x in paper["data"]["categories"] if x not in EXCLUDE_CATS
        ]
        paper["data"]["categories"] = [
            x if x not in RENAME_CATS else RENAME_CATS[x]
            for x in paper["data"]["categories"]
        ]
        paper["data"]["categories"] = [
            f"#{x.replace('#','')}" for x in paper["data"]["categories"]
        ]

# all_abstracts = "\n\n".join([x["abstract"] for x in feed["papers"]])
# intro_prompt = f"You are the editor of a machine learning journal. You have a set of abstract articles. Write an introduction to the journal about what awaits the reader in this issue. Write in Russian. Abstracts:\n\n{all_abstracts}"
# log(intro_prompt)
# intro = get_text(intro_prompt)
# feed["intro"] = intro
# log(intro)

log("Renaming data file.")
try_rename_file(DATA_FILE, DATA_DIR)

log("Saving new data file.")
json.dump(
    feed,
    open(DATA_FILE, "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=4,
)


# %%
def format_subtitle(number):
    if 11 <= number % 100 <= 14:
        word = "статей"
    else:
        last_digit = number % 10
        if last_digit == 1:
            word = "статья"
        elif 2 <= last_digit <= 4:
            word = "статьи"
        else:
            word = "статей"

    return f"{number} {word}"


def make_html(data):
    html = """
<!DOCTYPE html>
<html>
<head>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-C1CRWDNJ1J"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', 'G-C1CRWDNJ1J');
    </script>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">"""

    html += f"<title>HF ({format_subtitle(len(data['papers']))})</title>"

    html += """
    <link rel="icon" href="favicon.svg" sizes="any" type="image/svg+xml">
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@100..900&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #0989eacf;
            --secondary-color: #03dac6;
            --background-color: #f5f5f5;
            --text-color: #333333;
            --header-color: #0989eacf;
            --body-color: #f5f5f5;
        }
        body {
            font-family: 'Roboto Slab', sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }
        header {
            padding: 1.6em 0;
            text-align: center;
        }
        h1 {
            font-size: 2.4em;
            margin: 0;
            font-weight: 700;
        }
        h2 {
            # color: var(--primary-color);
            font-size: 1.2em;
            margin-top: 0;
            margin-bottom: 0.5em;
        }
        header p {
            font-size: 1.2em;
            margin-top: 0.5em;
            font-weight: 300;
        }
        main {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2em;
            padding: 10px 0 20px 0;
        }
        body.dark-tmeme>header {
            background-color: background-color: #333333;
            color: white;
        }
        body.dark-theme>div>main>article>div.article-content>p.meta {
            color: #fff;
        }
        body.light-theme>div>main>article>div.article-content>p.meta {
            color: #555;
        }
        body.dark-theme>div>main>article>div.article-content>p.pub-date {
            color: #ccc;
        }
        body.light-theme>div>main>article>div.article-content>p.pub-date {
            color: #555;
        }
        body.dark-theme>div>main>article>div.article-content>p.tags {
            color: #ccc;
        }
        body.light-theme>div>main>article>div.article-content>p.tags {
            color: #555;
        }
        body.light-theme>header {
            background-color: var(--header-color);
            color: white;
        }
        body.dark-theme>div>main>article {
            background-color: #444;
        }
        body.light-theme>div>main>article {
            background-color: #fff;
        }
        body.dark-theme>div>main>article:hover {
            background-color: #414141;
        }
        body.light-theme>div>main>article:hover {
            background-color: #fafafa;
        }
        article {
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 3px 6px rgba(0,0,0,0.16), 0 3px 6px rgba(0,0,0,0.23);
            transition: background-color 0.2s ease;
            display: flex;
            flex-direction: column;
            position: relative;
        }
        .article-content {
            padding: 1.5em;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            position: relative;
            z-index: 1;
            cursor: pointer;
        }
        .meta {
            font-size: 0.9em;
            margin-bottom: 0em;
        }
        .pub-date {
            font-size: 0.9em;
            margin-bottom: 0.8em;
            font-weight: 300;
        }
        .tags {
            font-size: 0.9em;
            margin-bottom: 1em;
            position: absolute;
            bottom: 10px;
            font-weight: 300;
            font-family: 'Roboto Slab';
        }
        .background-digit {
            position: absolute;
            bottom: -20px;
            right: -10px;
            font-size: 12em;
            font-weight: bold;
            color: rgba(0, 0, 0, 0.03);
            z-index: 0;
            line-height: 1;
        }
        .abstract {
            position: relative;
            max-height: 173px;
            overflow: hidden;
            transition: max-height 0.3s ease;
            cursor: pointer;
        }
        .abstract.expanded {
            max-height: 1000px;
        }
        .abstract-toggle {
            position: absolute;
            bottom: 4px;
            right: 0;
            cursor: pointer;
            color: var(--primary-color);
            float: right;
            font-weight: 400;
        }
        .explanation {
            background-color: #e8f5e9;
            border-left: 4px solid var(--secondary-color);
            padding: 1em;
            margin-top: 1.5em;
        }
        .links {
            margin-top: 1.5em;
            margin-bottom: 80px;
        }
        a {
            color: var(--primary-color);
            text-decoration: none;
            font-weight: 500;
            transition: color 0.3s ease;
        }
        a:hover {
            color: var(--secondary-color);
        }
        footer {
            background-color: var(--primary-color);
            color: white;
            text-align: center;
            padding: 1em 0;
            margin-top: 2em;
        }
        .light-theme {
            background-color: var(--body-color);
            color: #333333;
        }
        .dark-theme {
            background-color: #333333;
            color: #ffffff;
        }
        .theme-switch {
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            align-items: center;
        }
        .switch {
            position: relative;
            display: inline-block;
            width: 50px;
            height: 30px;
        }
        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 30px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 24px;
            width: 24px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: var(--primary-color);
        }
        input:checked + .slider:before {
            transform: translateX(20px);
        }
        .switch-label {
            margin-right: 10px;
        }
        .update-info-container {
            margin-top: 15px;
            margin-bottom: 0px;
            text-align: left;
        }
        .sort-container {
            margin-top: 15px;
            margin-bottom: 0px;
            text-align: right;
        }
        .sub-header-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        .update-info-container {
            flex: 1;
        }
        .sort-container {
            flex: 2;
        }
        .sort-dropdown {
            padding: 5px 10px;
            font-size: 16px;
            border-radius: 5px;
            border: 1px solid #ccc;
            background-color: white;
            color: var(--text-color);
            font-family: 'Roboto Slab', sans-serif;
        }
        .sort-label {
            margin-right: 10px;
        }        
        .dark-theme .sort-dropdown {
            background-color: #444;
            color: white;
            border-color: var(--text-color);
        }
        .title-sign {
            display: inline-block;
            transition: all 0.5s ease;            
        }
        .rotate {
            transform: rotate(45deg) translateY(-6px);
            transform-origin: center;
        }
        .title-text {
            display: inline;
            padding-left: 10px;
        }
        .category-filters {
            margin-top: 20px;
            margin-bottom: 20px;
            text-align: center;
        }
        .category-button {
            display: inline-block;
            margin: 5px;
            padding: 5px 10px;
            border-radius: 15px;
            background-color: #f0f0f0;
            color: #333;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }
        .category-button.active {
            background-color: var(--primary-color);
            color: white;
        }
        .dark-theme .category-button {
            background-color: #555;
            color: #fff;
        }
        .dark-theme .category-button.active {
            background-color: var(--primary-color);
        }
        .category-toggle {
            display: none;
            margin-bottom: 10px;
            margin-top: 15px;
            cursor: pointer;
        }
        .clear-categories {
            display: inline-block;
            margin: 5px;
            padding: 5px 10px;
            border-radius: 15px;
            background-color: #f0f0f0;
            color: #333;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }
        .clear-categories:hover {
            background-color: #bbb;
        }
        .svg-container {
            display: inline-block;
            position: relative;
            overflow: hidden;
        }

        .svg-container span {
            position: relative;
            z-index: 1;
        }

        .svg-container svg {
            position: absolute;
            bottom: 0;
            left: 0;
            z-index: 0;
        }
        @media (max-width: 768px) {
            .category-filters {
                display: none;
            }
            .category-toggle {
                display: inline-block;
                width: 100%;
                text-align: left;
            }
            .category-filters.expanded {
                display: block;
                margin-top: 10px;
            }
        }
        @media (max-width: 600px) {
            .sub-header-container {
                flex-direction: column;
                align-items: flex-start;
            }
            .update-info-container {
                text-align: left;
                width: 100%;
                margin-bottom: 0px;
            }
            .sort-container {
                margin-top: 0px;
                width: 100%;
            .sort-dropdown {
                float: right;
            }
            .sort-label {
                margin-top: 5px;
                float: left;
                font-size: 1.0em !important;
            }
        }
    </style>
    <script>
    function toggleAbstract(id) {
        var abstract = document.getElementById('abstract-' + id);
        var toggle = document.getElementById('toggle-' + id);
        if (abstract.classList.contains('expanded')) {
            abstract.classList.remove('expanded');
            toggle.textContent = '...';
        } else {
            abstract.classList.add('expanded');
            toggle.textContent = '';
        }
    }
    function getTimeDiffRu(dateString) {
        const timeUnits = {
            minute: ["минуту", "минуты", "минут"],
            hour: ["час", "часа", "часов"],
            day: ["день", "дня", "дней"]
        };

        function getRussianPlural(number, words) {
            if (number % 10 === 1 && number % 100 !== 11) {
                return words[0];
            } else if (number % 10 >= 2 && number % 10 <= 4 && (number % 100 < 10 || number % 100 >= 20)) {
                return words[1];
            } else {
                return words[2];
            }
        }

        const pastDate = new Date(dateString.replace(" ", "T") + ":00Z");
        const currentDate = new Date();
        const diffInSeconds = Math.floor((currentDate - pastDate) / 1000);

        const minutes = Math.floor(diffInSeconds / 60);
        const hours = Math.floor(diffInSeconds / 3600);
        const days = Math.floor(diffInSeconds / 86400);

        if (minutes == 0) {
            return 'только что';
        }
        else if (minutes < 60) {
            return `${minutes} ${getRussianPlural(minutes, timeUnits.minute)} назад`;
        } else if (hours < 24) {
            return `${hours} ${getRussianPlural(hours, timeUnits.hour)} назад`;
        } else {
            return `${days} ${getRussianPlural(days, timeUnits.day)} назад`;
        }
    }
    function formatArticlesTitle(number) {
        const lastDigit = number % 10;
        const lastTwoDigits = number % 100;

        let word;

        if (lastTwoDigits >= 11 && lastTwoDigits <= 14) {
            word = "статей";
        } else if (lastDigit === 1) {
            word = "статья";
        } else if (lastDigit >= 2 && lastDigit <= 4) {
            word = "статьи";
        } else {
            word = "статей";
        }

        return `${number} ${word}`;
    }
    </script>
</head>"""

    html += f"""
<body class="light-theme">
    <header>
        <div class="container">
            <h1 class="title-sign" id="doomgrad-icon">🔺</h1><h1 class="title-text" id="doomgrad">{TITLE_LIGHT}</h1>
            <p>{data['date']} | {format_subtitle(len(data['papers']))}</p>
        </div>
        <div class="theme-switch">
            <label class="switch">
                <input type="checkbox" id="theme-toggle">
                <span class="slider"></span>
            </label>
        </div>
    </header>
    <div class="container">
        <div class="sub-header-container">
            <div class="update-info-container">
                <label class="update-info-label" id="timeDiff"></label>
            </div>
            <div class="sort-container">
                <div class="sort-label">🔀 Сортировка по</div>
                <select id="sort-dropdown" class="sort-dropdown">
                    <option value="default">рейтингу</option>
                    <option value="pub_date">дате публикации</option>
                    <option value="issue_id">добавлению на HF</option>
                </select>
            </div>
        </div>
        <div class="category-toggle">
            <div class="svg-container">
                <span id="category-toggle">🔍 Фильтр</span>
                <svg height="3" width="200">
                    <line x1="0" y1="0" x2="200" y2="0" 
                        stroke="black" 
                        stroke-width="2" 
                        stroke-dasharray="3, 3" />
                </svg>
            </div>
        </div>
        <div class="category-filters" id="category-filters">
            <span class="clear-categories" id="clear-categories">🧹</span>
            <!-- Categories -->
        </div>
        <main id="articles-container">
            <!-- Articles -->
        </main>
    </div>
    <footer>
        <div class="container">
            <p><a style="color:white;" href="https://t.me/doomgrad">градиент обреченный</a> ✖️ <a style="color:white;" href="https://huggingface.co/papers">hugging face</a></p>
        </div>
    </footer>
    <script>    
        function toggleTheme() {{
            const body = document.body;
            body.classList.toggle('light-theme');
            body.classList.toggle('dark-theme');

            const isDarkMode = body.classList.contains('dark-theme');
            localStorage.setItem('darkMode', isDarkMode);
            
            if (isDarkMode) {{
                const title = document.getElementById('doomgrad');
                title.innerHTML = "{TITLE_DARK}";
                const titleSign = document.getElementById('doomgrad-icon');
                titleSign.classList.add('rotate');
            }}  else {{
                const title = document.getElementById('doomgrad');
                title.innerHTML = "{TITLE_LIGHT}";
                const titleSign = document.getElementById('doomgrad-icon');
                titleSign.classList.remove('rotate');
            }}
        }}

        const articlesData = {data["papers"]};
        const articlesContainer = document.getElementById('articles-container');
        const sortDropdown = document.getElementById('sort-dropdown');
        const categoryFiltersContainer = document.getElementById('category-filters');
        const categoryToggle = document.getElementById('category-toggle');
        const clearCategoriesButton = document.getElementById('clear-categories');
        let selectedCategories = [];
        let selectedArticles = [];
        let sortBy = 'default';        

        function loadSettings() {{
            const isDarkMode = localStorage.getItem('darkMode') === 'true';
            const themeToggle = document.getElementById('theme-toggle');
            let settingSortBy = localStorage.getItem('sort_by');
            const sortDropdown = document.getElementById('sort-dropdown');
            
            if (isDarkMode) {{
                document.body.classList.remove('light-theme');
                document.body.classList.add('dark-theme');
                themeToggle.checked = true;
                const title = document.getElementById('doomgrad');
                title.innerHTML = "{TITLE_DARK}";
                const titleSign = document.getElementById('doomgrad-icon');
                titleSign.classList.add('rotate');
            }}

            if ((!settingSortBy) || (settingSortBy === 'null')) {{
                settingSortBy = 'default';
            }}
            
            sortDropdown.value = settingSortBy;
            sortBy = settingSortBy;
        }}

        document.getElementById('theme-toggle').addEventListener('change', toggleTheme);

        function getUniqueCategories(articles) {{
            const categories = new Set();
            articles.forEach(article => {{
                if (article.data && article.data.categories) {{
                    article.data.categories.forEach(cat => categories.add(cat));
                }}
            }});
            return Array.from(categories);
        }}
        
        function createCategoryButtons() {{
            const categories = getUniqueCategories(articlesData);
            categories.forEach(category => {{
                const button = document.createElement('span');
                button.textContent = category;
                button.className = 'category-button';
                button.onclick = () => toggleCategory(category, button);
                categoryFiltersContainer.appendChild(button);
            }});
        }}

        function toggleCategory(category, button) {{
            const index = selectedCategories.indexOf(category);
            if (index === -1) {{
                selectedCategories.push(category);
                button.classList.add('active');
            }} else {{
                selectedCategories.splice(index, 1);
                button.classList.remove('active');
            }}         
            filterAndRenderArticles();
            saveCategorySelection();
            updateSelectedArticlesTitle();
        }}

        function saveCategorySelection() {{
            localStorage.setItem('selectedCategories', JSON.stringify(selectedCategories));
        }}

        function updateSelectedArticlesTitle() {{
            if (selectedArticles.length === articlesData.length) {{
                categoryToggle.textContent = '🏷️ Фильтр';
            }} else {{
                categoryToggle.textContent = `🏷️ Фильтр (${{formatArticlesTitle(selectedArticles.length)}})`;
            }}
        }}

        function cleanCategorySelection() {{
            localStorage.setItem('selectedCategories', JSON.stringify('[]'));
        }}

        function loadCategorySelection() {{
            const savedCategories = localStorage.getItem('selectedCategories');
            if (savedCategories) {{
                if (savedCategories != '"[]"') {{
                    selectedCategories = JSON.parse(savedCategories);
                    updateCategoryButtonStates();
                }}
            }}
        }}

        function updateCategoryButtonStates() {{
            const buttons = categoryFiltersContainer.getElementsByClassName('category-button');
            Array.from(buttons).forEach(button => {{
                if (selectedCategories.includes(button.textContent)) {{
                    button.classList.add('active');
                }} else {{
                    button.classList.remove('active');
                }}
            }});
        }}

        function filterAndRenderArticles() {{
            console.log(selectedCategories);
            let filteredArticles = selectedCategories.length === 0
                ? articlesData
                : articlesData.filter(article => 
                    article.data && article.data.categories && 
                    article.data.categories.some(cat => selectedCategories.includes(cat))
                );

            console.log('filteredArticles', filteredArticles)

            if (filteredArticles.length === 0) {{
                selectedArticles = articlesData;
                selectedCategories = [];
                cleanCategorySelection();
            }} else {{
                selectedArticles = filteredArticles;
            }}

            console.log('selectedArticles', selectedArticles)

            sortArticles(selectedArticles);
        }}

        function clearAllCategories() {{
            selectedCategories = [];
            updateCategoryButtonStates();
            filterAndRenderArticles();
            saveCategorySelection();
            updateSelectedArticlesTitle();
        }}

        function renderArticles(articles) {{
            console.log(articles);
            articlesContainer.innerHTML = '';
            articles.forEach((item, index) => {{
                if ("error" in item) {{
                    console.log(`Omitting JSON. ${{item["raw_data"]}}`);
                    return;
                }}
                const explanation = item["data"]["desc"];
                const tags = item["data"]["tags"].join(" ");
                const articleHTML = `
                    <article>
                        <div class="background-digit">${{index + 1}}</div>
                        <div class="article-content" onclick="toggleAbstract(${{index}})">
                            <h2>${{item['data']['emoji']}} ${{item['title']}}</h2>
                            <p class="meta"><svg class="text-sm peer-checked:text-gray-500 group-hover:text-gray-500" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" aria-hidden="true" role="img" width="1em" height="1em" preserveAspectRatio="xMidYMid meet" viewBox="0 0 12 12"><path transform="translate(0, 2)" fill="currentColor" d="M5.19 2.67a.94.94 0 0 1 1.62 0l3.31 5.72a.94.94 0 0 1-.82 1.4H2.7a.94.94 0 0 1-.82-1.4l3.31-5.7v-.02Z"></path></svg> ${{item['score']}}. ${{item['data']['title']}}</p>
                            <p class="pub-date">📅 Статья от ${{item['pub_date_ru']}}</p>
                            <div id="abstract-${{index}}" class="abstract">
                                <p>${{explanation}}</p>
                                <div id="toggle-${{index}}" class="abstract-toggle">...</div>
                            </div>
                            <div class="links">
                                <a href="${{item['url']}}" target="_blank">Статья</a>
                            </div>
                            <p class="tags">${{tags}}</p>
                        </div>
                    </article>
                `;
                articlesContainer.innerHTML += articleHTML;
            }});
        }}
        
        function sortArticles() {{
            let sortedArticles = [...selectedArticles];
            if (sortBy === 'issue_id') {{
                sortedArticles.sort((a, b) => b.issue_id - a.issue_id);
            }}
            if (sortBy === 'pub_date') {{
                sortedArticles.sort((a, b) => b.pub_date.localeCompare(a.pub_date));
            }}
            renderArticles(sortedArticles);
            localStorage.setItem('sort_by', sortBy);
        }}
        
        sortDropdown.addEventListener('change', (event) => {{
            sortBy = event.target.value;
            sortArticles(event.target.value);
        }});

        categoryToggle.addEventListener('click', () => {{
            categoryFiltersContainer.classList.toggle('expanded');
        }});

        clearCategoriesButton.addEventListener('click', clearAllCategories);
        
        function updateTimeDiffs() {{
            const timeDiff = document.getElementById('timeDiff');
            timeDiff.innerHTML = '🔄 ' + getTimeDiffRu('{data["time_utc"]}');
        }} 

        loadSettings();
        createCategoryButtons();
        loadCategorySelection();
        filterAndRenderArticles();
        updateSelectedArticlesTitle();
        updateTimeDiffs();  
    </script>
</body>
</html>
    """
    return html


# debug
# with open(DATA_FILE, "r", encoding="utf-8") as f:
#     feed = json.load(f)

log("Generating page.")
html = make_html(feed)

log("Renaming previous page.")
try_rename_file(PAGE_FILE, DATA_DIR, "hf_papers.html")

log("Writing result.")
with open(PAGE_FILE, "w", encoding="utf-8") as f:
    f.write(html)

log("Renaming log file.")
try_rename_file(LOG_FILE, LOG_DIR, "last_log.txt")

# %%

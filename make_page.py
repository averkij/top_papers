# %%
import html
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
import requests
from babel.dates import format_date
from bs4 import BeautifulSoup
from tqdm import tqdm

TITLE_LIGHT = "🔺 хф дэйли"
TITLE_DARK = "🔺 хф найтли"

LOG_FILE = "log.txt"
DATA_FILE = "hf_papers.json"
PAGE_FILE = "index.html"

LOG_DIR = "./logs"
DATA_DIR = "./prev_papers"

Path(LOG_DIR).mkdir(exist_ok=True)
Path(DATA_DIR).mkdir(exist_ok=True)


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


def extract_abstract(url):
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "html.parser")
    abstract = soup.find("div", {"class": "pb-8 pr-4 md:pr-16"}).text
    if abstract.startswith("Abstract\n"):
        abstract = abstract[len("Abstract\n") :]
    abstract = abstract.replace("\n", " ")
    return abstract


for article in tqdm(articles):
    h3 = article.find("h3")
    a = h3.find("a")
    title = a.text
    link = a["href"]
    url = f"https://huggingface.co{link}"
    prev_data, ok = try_get_prev_paper({"id": url})
    try:
        if ok:
            log(f"Get abstract from previous paper. URL: {url}")
            abstract = prev_data["abstract"]
            issue_id = prev_data["issue_id"] if "issue_id" in prev_data else ISSUE_ID
        else:
            abstract = extract_abstract(url)
            issue_id = ISSUE_ID + 1
    except Exception as e:
        log(f"Failed to extract abstract for {url}: {e}")
        abstract = ""

    papers.append(
        {
            "title": title,
            "url": url,
            "abstract": abstract,
            "score": try_get_score(article),
            "issue_id": issue_id,
        }
    )

current_date = datetime.now()
formatted_date = format_date(current_date, format="d MMMM", locale="ru_RU")

feed = {
    "date": formatted_date,
    "issue_id": ISSUE_ID + 1,
    "home_page_url": BASE_URL,
    "papers": [
        {
            "id": p["url"],
            "title": p["title"].strip(),
            "abstract": p["abstract"].strip(),
            "url": p["url"],
            "score": p["score"],
            "issue_id": p["issue_id"],
        }
        for p in papers
    ],
}

for i, paper in enumerate(feed["papers"]):
    log("*" * 80)
    log(f'Abstract {i}. {paper["abstract"][:300]}...')

API_KEY = os.getenv("CLAUDE_KEY")
client = anthropic.Anthropic(
    api_key=API_KEY,
)


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
        prompt = f"Read an abstract of the ML paper and return a JSON with fields: 'desc': explanation of the paper in Russian (4 sentences), use correct machine learning terms. 'tags': array of tags related to article, 3 tags, but specific, not general like #ml or #ai. 'emoji': emoji that will reflect the theme of an article somehow, only one emoji. 'title': a slogan of a main idea of the article in Russian. Return only JSON and nothing else.\n\n{abs}"
        paper["data"] = get_data(prompt, system_prompt=system_prompt)

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
def make_html(data):
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Обзор статей с HF</title>
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
            padding: 2em 0;
            text-align: center;
        }
        h1 {
            font-size: 3.0em;
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
            padding: 20px 0;
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
            color: #666;
            font-size: 0.9em;
            margin-bottom: 1em;
        }
        .tags {
            color: #9e9e9e;
            font-size: 0.9em;
            margin-bottom: 1em;
            position: absolute;
            bottom: 10px;
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
            max-height: 175px;
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
            width: 60px;
            height: 34px;
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
            border-radius: 34px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 26px;
            width: 26px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: var(--primary-color);
        }
        input:checked + .slider:before {
            transform: translateX(26px);
        }
        .switch-label {
            margin-right: 10px;
        }
        .sort-container {
            margin-top: 15px;
            margin-bottom: 0px;
            text-align: right;
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
    </script>
</head>"""

    html += f"""
<body class="light-theme">
    <header>
        <div class="container">
            <h1 id="doomgrad">{TITLE_LIGHT}</h1>
            <p>{feed['date']} | {len(data["papers"])} статей</p>
        </div>
        <div class="theme-switch">
            <label class="switch">
                <input type="checkbox" id="theme-toggle">
                <span class="slider"></span>
            </label>
        </div>
    </header>
    <div class="container">
        <div class="sort-container">
            <label class="sort-label">Сортировка</label>
            <select id="sort-dropdown" class="sort-dropdown">
                <option value="default">по рейтингу</option>
                <option value="issue_id">новые вверху</option>
            </select>
        </div>
        <main id="articles-container">
            <!-- Articles is here -->
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
            }}  else {{
                const title = document.getElementById('doomgrad');
                title.innerHTML = "{TITLE_LIGHT}";
            }}
        }}

        function loadSettings() {{
            const isDarkMode = localStorage.getItem('darkMode') === 'true';
            const themeToggle = document.getElementById('theme-toggle');

            const sortBy = localStorage.getItem('sort_by');
            const sortByIssueId = sortBy === 'issue_id';
            const sortDropdown = document.getElementById('sort-dropdown');
            
            if (isDarkMode) {{
                document.body.classList.remove('light-theme');
                document.body.classList.add('dark-theme');
                themeToggle.checked = true;
                const title = document.getElementById('doomgrad');
                title.innerHTML = "{TITLE_DARK}";
            }}

            console.log(sortBy);

            if (sortByIssueId) {{
                sortDropdown.value = sortBy;
                sortArticles(sortBy);
            }}
        }}
        document.getElementById('theme-toggle').addEventListener('change', toggleTheme);
        window.addEventListener('load', () => {{
            loadSettings();
        }});

        const articlesData = {data["papers"]};
        const articlesContainer = document.getElementById('articles-container');
        const sortDropdown = document.getElementById('sort-dropdown');
        
        function renderArticles(articles) {{
            console.log(articles)
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
        
        function sortArticles(sortBy) {{
            let sortedArticles = [...articlesData];
            if (sortBy === 'issue_id') {{
                sortedArticles.sort((a, b) => b.issue_id - a.issue_id);
            }}
            renderArticles(sortedArticles);
            localStorage.setItem('sort_by', sortBy);
        }}
        
        sortDropdown.addEventListener('change', (event) => {{
            sortArticles(event.target.value);
        }});
        
        // Initial render
        renderArticles(articlesData);
    </script>
</body>
</html>
    """
    return html

#debug
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

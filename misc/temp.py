# %%
import json
import os
from datetime import datetime, timezone, timedelta

import requests
from babel.dates import format_date
from bs4 import BeautifulSoup
from tqdm import tqdm

import constants as con
import helper
from helper import log

import api

_prev_papers, _issue_id = helper.init()


log("Get feed.")

# modified version of https://github.com/capjamesg/hugging-face-papers-rss/blob/main/app.py
BASE_URL = "https://huggingface.co/papers"

page = requests.get(BASE_URL)
soup = BeautifulSoup(page.content, "html.parser")
articles = soup.find_all("article")
papers = []


for article in tqdm(articles):
    h3 = article.find("h3")
    a = h3.find("a")
    title = a.text
    link = a["href"]
    url = f"https://huggingface.co{link}"
    prev_data, ok = helper.try_get_prev_paper({"id": url}, _prev_papers)
    issue_id = _issue_id + 1
    try:
        if ok:
            log(f"Get page data from previous paper. URL: {url}")
            abstract = prev_data["abstract"]
            issue_id = prev_data["issue_id"] if "issue_id" in prev_data else _issue_id
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
            page_data = helper.extract_page_data(url)
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
            "score": helper.try_get_score(article),
            "issue_id": issue_id,
            "pub_date": pub_date,
            "pub_date_ru": pub_date_ru,
            "hash": helper.get_hash(url),
        }
    )


# %%
def get_week_info(date):
    weekday = date.weekday()
    feed_date = date
    prev_feed_date = feed_date - timedelta(1)
    next_feed_date = feed_date + timedelta(1)

    # HF Daily don't have updates on weekend
    if weekday == 0:  # Monday
        prev_feed_date = prev_feed_date - timedelta(2)
    if weekday == 4:  # Friday
        next_feed_date = next_feed_date + timedelta(2)
    if weekday == 5:  # Saturday
        weekday = 4
        feed_date = feed_date - timedelta(1)
        prev_feed_date = prev_feed_date - timedelta(1)
        next_feed_date = next_feed_date + timedelta(1)
    elif weekday == 6:  # Sunday
        weekday = 4
        feed_date = feed_date - timedelta(2)
        prev_feed_date = prev_feed_date - timedelta(2)
    return weekday, feed_date, prev_feed_date, next_feed_date


weekday, feed_date, prev_feed_date, next_feed_date = get_week_info(helper.CURRENT_DATE)

formatted_date = format_date(feed_date, format="d MMMM", locale="ru_RU")
formatted_date_en = format_date(feed_date, format="d MMMM", locale="en_US")
formatted_date_prev = format_date(prev_feed_date, format="d MMMM", locale="ru_RU")
formatted_date_next = format_date(next_feed_date, format="d MMMM", locale="ru_RU")
short_date_prev = prev_feed_date.strftime("%d.%m")
short_date_next = next_feed_date.strftime("%d.%m")

formatted_time_utc = helper.CURRENT_DATE.strftime("%Y-%m-%d %H:%M")

link_prev = f"{prev_feed_date.strftime('%Y-%m-%d')}.html"
link_next = f"{next_feed_date.strftime('%Y-%m-%d')}.html"

feed = {
    "date": formatted_date,
    "date_en": formatted_date_en,
    "time_utc": formatted_time_utc,
    "weekday": weekday,
    "issue_id": _issue_id + 1,
    "home_page_url": BASE_URL,
    "papers": papers,
    "link_prev": link_prev,
    "link_next": link_next,
    "date_prev": formatted_date_prev,
    "date_next": formatted_date_next,
    "short_date_prev": short_date_prev,
    "short_date_next": short_date_next,
}

for i, paper in enumerate(feed["papers"]):
    log("*" * 80)
    log(f'Abstract {i}. {paper["abstract"][:300]}...')


if os.path.isfile(con.DATA_FILE):
    log("Read previous papers.")
    with open(con.DATA_FILE, "r", encoding="utf-8") as f:
        PREV_PAPERS = json.load(f)
else:
    log("No previous papers found.")
    PREV_PAPERS = {}

log("Generating reviews via LLM API.")

for paper in tqdm(feed["papers"]):
    prev_data, ok = helper.try_get_prev_paper(paper, _prev_papers)

    if ok:
        log(
            f'Using data from previous issue: {json.dumps(prev_data["data"], ensure_ascii=False)[:300]}'
        )
        paper["data"] = prev_data["data"]
    else:
        log("Querying the API.")
        abs = paper["abstract"][:3000]

        system_prompt = "You are explaining concepts in simple words in good and native Russian. But you are using English terms like LLM and AI instead of Russian when appropriate."

        prompt = f"Read an abstract of the ML paper and return a JSON with fields: 'desc': explanation of the paper in Russian (4 sentences), use correct machine learning terms. 'emoji': emoji that will reflect the theme of an article somehow, only one emoji. 'title': a slogan of a main idea of the article in Russian. Return only JSON and nothing else.\n\n{abs}"

        prompt_cls = (
            f"""You are an expert classifier of machine learning research papers. Analyze the following research paper text and classify it into one or more relevant categories from the list below. Consider the paper's main contributions, methodologies, and applications.

Categories:
1. DATASET: Papers that introduce new datasets or make significant modifications to existing ones
2. DATA: Papers focusing on data processing, cleaning, collection, or curation methodologies
3. BENCHMARK: Papers proposing or analyzing model evaluation frameworks and benchmarks
4. AGENTS: Papers exploring autonomous agents, web agents, or agent-based architectures 
5. NLP: Papers advancing natural language processing techniques or applications
6. CV: Papers developing computer vision methods or visual processing systems
7. RL: Papers investigating reinforcement learning theory or applications
8. RLHF: Papers specifically about human feedback in RL (PPO, DPO, etc.)
9. RAG: Papers advancing retrieval-augmented generation techniques
10. CODE: Papers about code-related models or programming benchmarks
11. INFERENCE: Papers optimizing model deployment (quantization, pruning, etc.)
12. 3D: Papers on 3D content generation, processing, or understanding
13. AUDIO: Papers advancing speech/audio processing or generation
14. VIDEO: Papers on video analysis, generation, or understanding
15. MULTIMODAL: Papers combining multiple input/output modalities
16. MATH: Papers focused on mathematical theory and algorithms
17. MULTILINGUAL: Papers addressing multiple languages or cross-lingual capabilities
18. ARCHITECTURE: Papers proposing novel neural architectures or components
19. MEDICINE: Papers applying ML to medical/healthcare domains
20. TRAINING: Papers improving model training or fine-tuning methods
21. ROBOTICS: Papers on robotic systems and embodied AI
22. AGI: Papers discussing artificial general intelligence concepts
23. GAMES: Papers applying ML to games or game development
24. INTERPRETABILITY: Papers analyzing model behavior and explanations
25. REASONING: Papers enhancing logical reasoning capabilities
26. TRANSFER_LEARNING: Papers on knowledge transfer between models/domains
27. GRAPHS: Papers advancing graph neural networks and applications
28. ETHICS: Papers addressing AI ethics, fairness, and bias
29. SECURITY: Papers on model security and adversarial robustness
30. QUANTUM: Papers combining quantum computing and ML
31. EDGE_COMPUTING: Papers on ML deployment for resource-constrained devices
32. OPTIMIZATION: Papers advancing training optimization methods
33. SURVEY: Papers comprehensively reviewing research areas
34. DIFFUSION: Papers on diffusion-based generative models
35. ALIGNMENT: Papers about aligning language models with human values, preferences, and intended behavior

Return only JSON with flat array of categories that match the given text.

Paper text to classify:\n\n""{abs}"""
            ""
        )

        try:
            paper["data"] = api.get_json(
                prompt,
                system_prompt=system_prompt,
                api="claude",
                model="claude-sonnet-4-5-20250929",
                temperature=1.0,
            )
            paper["data"]["categories"] = api.get_json(
                prompt_cls, api="openai", model="gpt-4o-mini", temperature=0.0
            )
        except Exception as e:
            paper["data"] = {"error": str(e)}
            log(f"Error getting data: {e}")

        # add embedding
        log("Get embedding for a paper via LLM API.")
        paper["data"]["embedding"] = api.get_embedding(paper["abstract"][:6000])

    # fix categories
    if "categories" in paper["data"]:
        paper["data"]["categories"] = [
            x for x in paper["data"]["categories"] if x not in con.EXCLUDE_CATS
        ]
        paper["data"]["categories"] = [
            x if x not in con.RENAME_CATS else con.RENAME_CATS[x]
            for x in paper["data"]["categories"]
        ]
        paper["data"]["categories"] = [
            f"#{x.replace('#','')}".lower() for x in paper["data"]["categories"]
        ]


# all_abstracts = "\n\n".join([x["abstract"] for x in feed["papers"]])
# intro_prompt = f"You are the editor of a machine learning journal. You have a set of abstract articles. Write an introduction to the journal about what awaits the reader in this issue. Write in Russian. Abstracts:\n\n{all_abstracts}"
# log(intro_prompt)
# intro = get_text(intro_prompt)
# feed["intro"] = intro
# log(intro)


def renew_zh(dt_str):
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    dt_now = datetime.now(timezone.utc)
    if (dt.day != dt_now.day) and dt_now.hour > 8:
        return True
    return False


try:
    if "zh" not in _prev_papers or renew_zh(_prev_papers["zh"]["update_ts"]):
        log("Trying to get texts in Chinese.")
        first_abstract = feed["papers"][0]["abstract"]
        zh_prompt = f"Write simple and brief explanation (4-5 sentences) of an article in Chinese. Use short sentences. Text:\n\n{first_abstract}"
        zh_text = api.get_text(
            zh_prompt, api="mistral", model="mistral-large-latest", temperature=0.5
        )
        feed["zh"] = {"text": zh_text}
        feed["zh"]["title"] = feed["papers"][0]["title"]

        zh_prompt = (
            f"Write pinyin transcription for text. Text:\n\n{feed['zh']['text']}"
        )
        zh_text = api.get_text(
            zh_prompt, api="mistral", model="mistral-large-latest", temperature=0.0
        )
        feed["zh"]["pinyin"] = zh_text

        zh_prompt = f"Write vocab of difficult words for this text as an array of objects with fields 'word', 'pinyin', 'trans'. Return as python list without formatting. Return list and nothing else. Text:\n\n{feed['zh']['text']}"
        zh_text = api.get_text(
            zh_prompt, api="mistral", model="mistral-large-latest", temperature=0.0
        )
        feed["zh"]["vocab"] = zh_text

        zh_prompt = f"Translate this text in English. Text:\n\n{feed['zh']['text']}"
        zh_text = api.get_text(
            zh_prompt, api="mistral", model="mistral-large-latest", temperature=0.5
        )
        feed["zh"]["trans"] = zh_text
        feed["zh"]["update_ts"] = formatted_time_utc
    else:
        log("Loading Chinese text from previous data.")
        feed["zh"] = _prev_papers["zh"]

except Exception as e:
    log(f"Failed to get Chinese text: {e}")

log("Renaming data file.")
helper.try_rename_file(
    con.DATA_FILE, con.DATA_DIR, helper.add_date_to_name(name=".json", date=feed_date)
)

log("Saving new data file.")
json.dump(
    feed,
    open(con.DATA_FILE, "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=4,
)


# %%
def make_html(data):
    data["papers"] = [x for x in data["papers"] if "error" not in x]
    article_classes = ""
    for paper in data["papers"]:
        if paper["score"] >= 20:
            article_classes += f'body.light-theme>div>main>article.x{paper["hash"]} {{ background: url("https://hfday.ru/img/{paper["pub_date"].replace("-","")}/{paper["hash"]}.jpg") !important; background-size: cover !important; background-position: center !important; background-blend-mode: lighten !important; background-color: rgba(255,255,255,0.91) !important;}}\n'

            article_classes += f'body.light-theme>div>main>article.x{paper["hash"]}:hover {{ background-color: rgba(255,255,255,0.95) !important;}}\n'

            article_classes += f'body.dark-theme>div>main>article.x{paper["hash"]} {{ background: url("https://hfday.ru/img/{paper["pub_date"].replace("-","")}/{paper["hash"]}.jpg") !important; background-size: cover !important; background-position: center !important; background-blend-mode: hue !important; background-color: rgba(60,60,60,0.9) !important; }}\n'

            article_classes += f'body.dark-theme>div>main>article.x{paper["hash"]}:hover {{ background-color: rgba(60,60,60,0.92) !important;}}\n'

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

    html += f"<title>HF ({helper.format_subtitle(len(data['papers']))})</title>"

    html += (
        """
    <link rel="icon" href="favicon.svg" sizes="any" type="image/svg+xml">
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@100..900&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #0989eacf;
            --secondary-color: #fff;
            --background-color: #f5f5f5;
            --text-color: #333333;
            --header-color: #0989eacf;
            --body-color: #f5f5f5;
            --menu-color: #002370;
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
            padding: 3em 0;
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
            max-height: 170px;
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
            font-size: 1.0em !important;
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

        .nav-menu {
            background-color: var(--menu-color);
            padding: 2px 0 2px 0;
            display: inline-block;
            position: relative;
            overflow: hidden;
            width: 100%;
        }        
        .nav-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 10px;
            display: flex;
            justify-content: center;
            gap: 2em;
        }
        .nav-container span a {
            color: white;
        }
        
        .nav-item {
            color: white;
            padding: 3px 10px;
            cursor: pointer;
            font-weight: 400;
        }
        
        .nav-item:hover {
            background-color: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.3);
        }
        
        .dark-theme .nav-menu {
            background-color: #333;
        }
        .dark-theme .nav-item {
            color: white;
        }
        
        .dark-theme .nav-item:hover {
            background-color: rgba(255, 255, 255, 0.05);
        }
        
        @media (max-width: 600px) {
            .nav-container {
                flex-direction: row;
                gap: 1em;
            }
            
            .nav-item {
                padding: 3px 3px;
            }
        }
        """
        + article_classes
        + """
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
                text-align: left;
                width: 100%;
            .sort-dropdown {
                float: right;
            }
            .sort-label {
                margin-top: 5px;
                float: left;
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
    )

    html += f"""
<body class="light-theme">
    <header>
        <div class="container">
            <h1 class="title-sign" id="doomgrad-icon">🔺</h1><h1 class="title-text" id="doomgrad">{con.TITLE_LIGHT}</h1>
            <p>{data['date']} | {helper.format_subtitle(len(data['papers']))}</p>
        </div>
        <div class="theme-switch">
            <label class="switch">
                <input type="checkbox" id="theme-toggle">
                <span class="slider"></span>
            </label>
        </div>
    </header>
    <div class="nav-menu">
        <div class="nav-container">
            <span class="nav-item" id="nav-prev"><a href="d/{feed['link_prev']}">⬅️ {feed['short_date_prev']}</a></span>
            <span class="nav-item" id="nav-next"><a href="d/{feed['link_next']}">➡️ {feed['short_date_next']}</a></span>
            <!--<span class="nav-item" id="nav-weekly">Топ за неделю</span>
            <span class="nav-item" id="nav-weekly">Топ за месяц</span>-->
        </div>
    </div>
    <div class="container">
        <div class="sub-header-container">
            <div class="update-info-container">
                <label class="update-info-label" id="timeDiff"></label>
            </div>
            <div class="sort-container">
                <label class="sort-label">🔀 Сортировка по</label>
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
                title.innerHTML = "{con.TITLE_DARK}";
                const titleSign = document.getElementById('doomgrad-icon');
                titleSign.classList.add('rotate');
            }}  else {{
                const title = document.getElementById('doomgrad');
                title.innerHTML = "{con.TITLE_LIGHT}";
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
        let sortBy = 'issue_id';     

        function getUrlParameters() {{
            const urlParams = new URLSearchParams(window.location.search);
            const categoriesParam = urlParams.get('cat');
            let categories = categoriesParam ? categoriesParam.split(',') : [];
            categories = categories.map(element => `#${{element}}`);
            return categories
        }}

        function updateUrlWithCategories() {{
            let cleanedCategories = selectedCategories.map(element => element.replace(/^#/, ''));
            const newUrl = cleanedCategories.length > 0 
                ? `${{window.location.pathname}}?cat=${{cleanedCategories.join(',')}}`
                : window.location.pathname;
            console.log("cleanedCategories", cleanedCategories)
            window.history.pushState({{}}, '', newUrl);
        }}

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
                title.innerHTML = "{con.TITLE_DARK}";
                const titleSign = document.getElementById('doomgrad-icon');
                titleSign.classList.add('rotate');
            }}

            if ((!settingSortBy) || (settingSortBy === 'null')) {{
                settingSortBy = 'issue_id';
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
            let res = Array.from(categories);
            res.sort();
            return res;
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
            updateUrlWithCategories();
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
            const urlCategories = getUrlParameters();
            if (urlCategories.length > 0) {{
                selectedCategories = urlCategories;
                saveCategorySelection();
            }} else {{
                const savedCategories = localStorage.getItem('selectedCategories');
                if (savedCategories && savedCategories !== '"[]"') {{
                    selectedCategories = JSON.parse(savedCategories);                    
                }}
            }}
            updateCategoryButtonStates();
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
            updateUrlWithCategories();
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
                const cats = item["data"]["categories"].join(" ");
                const articleHTML = `
                    <article class='x${{item["hash"]}}'>
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
                            <p class="tags">${{cats}}</p>
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


def make_html_zh(data):
    data_zh = data["zh"]
    title = data["zh"]["title"] if "title" in data["zh"] else "Title"
    pinyin = "\n".join(
        [
            f"<p>{i+1}. {x}</p>"
            for i, x in enumerate(data_zh["pinyin"].strip(".").split("."))
        ]
    )
    text_zh = "\n".join(
        [
            f"<p class='zh-text'>{i+1}. {x}。</p>"
            for i, x in enumerate(data_zh["text"].strip("。").split("。"))
        ]
    )
    text_en = "\n".join(
        [
            f"<p>{i+1}. {x}.</p>"
            for i, x in enumerate(data_zh["trans"].strip(".").split("."))
        ]
    )
    try:
        if isinstance(data_zh["vocab"], str):
            data_zh["vocab"] = data_zh["vocab"].replace("'", '"')
            data_zh["vocab"] = json.loads(data_zh["vocab"])
    except Exception as e:
        data_zh["vocab"] = []
        log(f"Can't parse vocab. {e}")

    log(f"Chinese vocab {data_zh['vocab']}")
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-C1CRWDNJ1J"></script>
        <script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){{dataLayer.push(arguments);}}
            gtag('js', new Date());
            gtag('config', 'G-C1CRWDNJ1J');
        </script>
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@100..900&display=swap" rel="stylesheet">
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Chinese reading task about ML</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f9;
                color: #333;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background-color: #fff;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }}
            h1 {{
                color: #0056b3;
                text-align: center;
            }}
            p {{
                line-height: 1.6;
            }}
            .zh-text {{
                font-size: 1.3em;
                font-family: 'Noto Sans SC';
                font-weight: 300;
                margin: 0 0 5px 0;
            }}
            .pinyin {{
                padding-top: 5px;
                padding-bottom: 5px;
                font-style: italic;
                color: #888;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th, td {{
                padding: 12px;
                border: 1px solid #ddd;
                text-align: left;
            }}
            th {{
                background-color: #0056b3;
                color: #fff;
            }}
            td {{
                background-color: #f9f9f9;
            }}
            td.zh {{
                font-family: 'Noto Sans SC';
                font-size: 1.2em;
                font-weight: 400;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{title}</h1>
            <div>{text_zh}</div>
            <div class="pinyin">
                {pinyin}
            </div>
            <div>{text_en}</div>
            <h2>Vocabulary</h2>
            <table>
                <thead>
                    <tr>
                        <th>Word</th>
                        <th>Pinyin</th>
                        <th>Translation</th>
                    </tr>
                </thead>
                <tbody>
    """

    for vocab_item in data_zh["vocab"]:
        html_content += f"""
                    <tr>
                        <td class="zh">{vocab_item['word']}</td>
                        <td>{vocab_item['pinyin']}</td>
                        <td>{vocab_item['trans']}</td>
                    </tr>
        """

    html_content += """
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """

    return html_content


# debug
# with open(con.DATA_FILE, "r", encoding="utf-8") as f:
#     feed = json.load(f)

log("Generating page.")
html_index = make_html(feed)

# log("Renaming previous page.")
# helper.try_rename_file(con.PAGE_FILE, con.DATA_DIR, helper.add_date_to_name(name=".html", date=feed_date))

log("[Experimental] Generating Chinese page for reading.")
html_zh = make_html_zh(feed)
log("Renaming previous Chinese page.")
helper.try_rename_file(
    "zh.html", con.DATA_DIR, helper.add_date_to_name("_zh_reading_task.html")
)

# debug
log("Writing result.")
with open("temp.html", "w", encoding="utf-8") as f:
    f.write(html_index)

log("Writing Chinese reading task.")
with open("zh.html", "w", encoding="utf-8") as f:
    f.write(html_zh)

log("Renaming log file.")
helper.try_rename_file(
    con.LOG_FILE,
    con.LOG_DIR,
    helper.add_date_to_name("_last_log.txt", helper.CURRENT_DATE),
)

for paper in feed["papers"]:
    if paper["score"] >= 20:
        log(f"[Experimental] Generating an image for paper {paper['title']}.")
        img_name = f"{paper['hash']}.jpg"
        if not helper.if_paper_image_exists(paper):
            api.generate_image_for_paper(paper, img_name)
        else:
            log(f"[Experimental] Image for paper {paper['title']} already exists.")


# %%

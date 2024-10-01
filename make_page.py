
#%%
import html
import json
import os
import random
import re
from collections import defaultdict
from datetime import datetime

import feedparser
import pymupdf
import requests
# import trafilatura
from boilerpy3 import extractors
from bs4 import BeautifulSoup
from openai import OpenAI
from tqdm import tqdm

#get feed
rss_url = 'https://nlp.elvissaravia.com/feed'
feed = feedparser.parse(rss_url)

if feed.status == 200:
    for entry in feed.entries:
        print(entry.title)
        print(entry.link)
else:
    print("Failed to get RSS feed. Status code:", feed.status)


#parse feed
months = {
    "January": "января",
    "February": "февраля",
    "March": "марта",
    "April": "апреля",
    "May": "мая",
    "June": "июня",
    "July": "июля",
    "August": "августа",
    "September": "сентября",
    "October": "октября",
    "November": "ноября",
    "December": "декабря",
}

def extract_ps(text):
    pattern = re.compile(r'<p>(.*?)<\/p>', re.DOTALL)
    matches = pattern.findall(text)
    return matches

def parse_p(text):
    pattern = re.compile(r'<strong>(.*?)<\/strong>', re.DOTALL)
    title = pattern.findall(text)[0]
    title = ' '.join(title.split()[1:])
    title = html.unescape(title)

    soup = BeautifulSoup(text, 'html.parser')
    href_dict = {}
    links = soup.find_all('a')
    for link in links:
        href_dict[link.get_text()] = link.get('href')

    return {'title': title, 'links': href_dict}

def format_date_ru(date):
    date = datetime.strptime(f"{date.strip()} {datetime.now().year}", "%B %d %Y")
    date = date.strftime("%d %B")
    for en_month, ru_month in months.items():
        date = date.replace(en_month, ru_month)
    return date

def get_dates(text):
    pat = re.compile(r"\((.*?)\)")
    dates = pat.findall(text)[0]
    start, end = dates.split("-")
    start = format_date_ru(start)
    end = format_date_ru(end)
    return start, end

xml = feed['entries'][0]['content'][0]['value']

start_date, end_date = get_dates(feed['entries'][0]['summary'])
ps = extract_ps(xml)
papers = []
for p in ps:
    parsed = parse_p(p)
    papers.append(parsed)

res = {
        "date": f"{start_date} — {end_date}",
        "papers": papers,
    }

print(res)

#%%
#get abstracts
def extract_content(html):
    # return trafilatura.extract(html)
    extractor = extractors.ArticleExtractor()
    return extractor.get_content(html)

def get_arxiv_abstract(url):
    response = requests.get(url)
    if response.status_code != 200:
        return "Failed to retrieve the page."
    soup = BeautifulSoup(response.content, "html.parser")
    abstract_tag = soup.find("blockquote", class_="abstract")
    if not abstract_tag:
        return "Abstract not found."
    abstract = abstract_tag.text.replace("Abstract:", "").strip()
    return abstract

def download_pdf(pdf_url, save_path):
    response = requests.get(pdf_url)
    if response.status_code == 200:
        with open(save_path, "wb") as file:
            file.write(response.content)
    else:
        print(f"Failed to download PDF. Status: {response.status_code}")

def extract_abstract_from_pdf(pdf_path):
    abstract_text = ""
    doc = pymupdf.open(pdf_path)

    for page in doc:
        text = page.get_text()
        if "Abstract" in text:
            start_index = text.find("Abstract")
            end_index = text.find("Introduction")
            if end_index == -1:
                end_index = len(text)
            abstract_text = text[start_index:end_index].strip()
            break

    return abstract_text.replace("Abstract", "").strip(":").strip()


for paper in tqdm(res['papers']):
    url = paper["links"]['paper']
    print(url)
    if url.endswith(".pdf"):
        _temp = "./_temp.pdf"
        download_pdf(url, _temp)
        text = extract_abstract_from_pdf(_temp)
        os.remove(_temp)
    elif 'arxiv.org' in url:
        text = get_arxiv_abstract(url)
    else:
        resp = requests.get(url)
        text = extract_content(resp.text)
    paper["abstract"] = text

#%%
#check abstracts
for paper in res['papers']:
    print('*' * 80)
    print(paper['abstract'][:3000])


#%%
#add reviews via LLM

OPENAI_API_KEY = "YOU_KEY"
client = OpenAI(
    api_key=OPENAI_API_KEY,
)

def get_data(prompt):
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="gpt-4o",
        response_format={"type": "json_object"},
    )
    return json.loads(chat_completion.choices[0].message.content)


# %%
for style_id, paper in tqdm(enumerate(res['papers'])):
    abs = paper["abstract"][:3000]
    # style_id = random.randint(0,9)
    styles = {
        0: 'Magister Yoda',
        1: 'Donald Trump',
        2: 'Sherlock Holmes',
        3: 'Gandalf',
        4: 'Homer Simpson',
        5: 'Tyler Durden',
        6: 'Hannibal Lecter',
        7: 'Forrest Gump',
        8: 'Gregory House from TV series',
        9: 'Groot from Guardians of the Galaxy',}
        
    prompt = f"I will give you the abstract of a paper. Read it and return a JSON with fields: 'desc': explanation of a paper in style of {styles[style_id]}. In Russian 'tags': array of tags related to article (like #cv, #nlp, etc.) 3-4 tags, but specific, not general like #ml or #ai. 'emoji': emoji that will reflect the theme of an article somehow, only one emoji. 'title': a slogan of a main idea of the article in Russian. Return only JSON and nothing else.\n\n{abs}"

    paper["data"] = get_data(prompt)
    paper["style_id"] = style_id


json.dump(
    res,
    open("dg_papers.json", "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=4,
)

#%%
def generate_html(data):
    html = (
        """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DoomGrad ML News</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@100..900&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary-color: #6200ea;
            --secondary-color: #03dac6;
            --background-color: #f5f5f5;
            --text-color: #333333;
            --card-color: #ffffff;
        }
        body {
            font-family: 'Roboto Slab', sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background-color: var(--background-color);
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }
        header {
            background-color: var(--primary-color);
            color: white;
            padding: 2em 0;
            text-align: center;
        }
        h1 {
            font-size: 3.5em;
            margin: 0;
            font-weight: 700;
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
            padding: 2em 0;
        }
        article {
            background-color: var(--card-color);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: background-color 0.2s ease;
            display: flex;
            flex-direction: column;
            position: relative;
        }
        article:hover {
            background: #ffffee;
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
        h2 {
            # color: var(--primary-color);
            font-size: 1.6em;
            margin-top: 0;
            margin-bottom: 0.5em;
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
            max-height: 140px;
            overflow: hidden;
            transition: max-height 0.3s ease;
            cursor: pointer;
        }
        .abstract.expanded {
            max-height: 1000px;
        }
        .abstract-toggle {
            position: absolute;
            bottom: 0px;
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
        + f"""
<body>
    <header>
        <div class="container">
            <h1>🔺 это статьи</h1>
            <p>за {res['date']}</p>
        </div>
    </header>
    <div class="container">
        <main>
    """
    )

    for index, item in enumerate(data['papers']):
        print(item["data"])
        explanation = item["data"]["desc"]
        tags = " ".join(item["data"]["tags"])
        html += f"""
        <article>
            <div class="background-digit">{index + 1}</div>
            <div class="article-content" onclick="toggleAbstract({index})">
                <h2>{item['title']}</h2>
                <p class="meta">{item['data']['emoji']} {item['data']['title']}</p>
                <p class="tags">{tags}</p>
                <div id="abstract-{index}" class="abstract">
                    <p>{explanation}</p>
                    <div id="toggle-{index}" class="abstract-toggle">...</div>
                </div>
                <div class="links">
                    <a href="{item['links']['paper']}" target="_blank">Статья</a> | 
                    <a href="{item['links']['tweet']}" target="_blank">Твит</a>
                </div>
            </div>
        </article>
        """

    html += """
        </main>
    </div>
    <footer>
        <div class="container">
            <p>&copy; 2024 <a style="color:white;" href="https://t.me/doomgrad">градиент обреченный</a></p>
        </div>
    </footer>
</body>
</html>
    """
    return html


with open("dg_papers.json", "r", encoding="utf-8") as f:
    data = json.load(f)

html = generate_html(data)

with open("dg_news.html", "w", encoding="utf-8") as f:
    f.write(html)

# %%

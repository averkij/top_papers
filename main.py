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
        else:
            log(f"Extract page data from URL. URL: {url}")
            page_data = helper.extract_page_data(url)
            abstract = page_data["abstract"]
            pub_date = page_data["pub_date"]

    except Exception as e:
        log(f"Failed to extract page data for {url}: {e}")
        abstract = ""

    published_date = datetime.strptime(pub_date, "%Y-%m-%d")
    papers.append(
        {
            "id": url,
            "title": title,
            "url": url,
            "abstract": abstract,
            "score": helper.try_get_score(article),
            "issue_id": issue_id,
            "pub_date": pub_date,
            "pub_date_card": {'ru': format_date(published_date, format="d MMMM", locale="ru_RU"),
                              'en': format_date(published_date, format="MMMM d", locale="en_US"),
                              'zh': helper.format_date_zh(published_date)},
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
formatted_date_en = format_date(feed_date, format="MMMM d", locale="en_US")
formatted_date_zh = helper.format_date_zh(feed_date)
short_date_prev = prev_feed_date.strftime("%d.%m")
short_date_next = next_feed_date.strftime("%d.%m")
short_date_prev_en = prev_feed_date.strftime("%m/%d")
short_date_next_en = next_feed_date.strftime("%m/%d")
short_date_prev_zh = helper.format_date_zh(prev_feed_date)
short_date_next_zh = helper.format_date_zh(next_feed_date)

formatted_time_utc = helper.CURRENT_DATE.strftime("%Y-%m-%d %H:%M")

link_prev = f"{prev_feed_date.strftime('%Y-%m-%d')}.html"
link_next = f"{next_feed_date.strftime('%Y-%m-%d')}.html"

feed = {
    "date": {'ru': formatted_date, 'en': formatted_date_en, 'zh': formatted_date_zh},
    "time_utc": formatted_time_utc,
    "weekday": weekday,
    "issue_id": _issue_id + 1,
    "home_page_url": BASE_URL,
    "papers": papers,
    "link_prev": link_prev,
    "link_next": link_next,
    "short_date_prev": {'ru': short_date_prev, 'en': short_date_prev_en, 'zh': short_date_prev_zh},
    "short_date_next": {'ru': short_date_next, 'en': short_date_next_en, 'zh': short_date_next_zh},

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

        # DEBUG
        # abs = paper["abstract"][:3000]
        # system_prompt_en = "You are explaining concepts in simple words."
        # prompt_en = f"Read an abstract of the ML paper and return a JSON with fields: 'desc': explanation of the paper (4 sentences), use correct machine learning terms. 'title': a slogan of a main idea of the article. Return only JSON and nothing else.\n\n{abs}"
        # system_prompt_zh = "You are explaining concepts in simple words in Chinese."
        # prompt_zh = f"Read an abstract of the ML paper and return a JSON with fields: 'desc': explanation of the paper in Chinese (4 sentences), use correct machine learning terms. 'title': a slogan of a main idea of the article in Chinese. Return only JSON and nothing else.\n\n{abs}"
        # data_en = api.get_structured(
        #     prompt=prompt_en,
        #     system_prompt=system_prompt_en,
        #     cls=api.Article,
        #     temperature=0,
        #     model="gpt-4o-mini",
        # )
        # data_zh = api.get_structured(
        #     prompt=prompt_zh,
        #     system_prompt=system_prompt_zh,
        #     cls=api.Article,
        #     temperature=0,
        #     model="gpt-4o-mini",
        # )
        # paper["data"]["en"]["title"] = data_en["title"]
        # paper["data"]["en"]["desc"] = data_en["desc"]
        # paper["data"]["zh"]["title"] = data_zh["title"]
        # paper["data"]["zh"]["desc"] = data_zh["desc"]
    else:
        log("Querying the API.")
        abs = paper["abstract"][:3000]

        system_prompt = "You are explaining concepts in simple words in good and native Russian. But you are using English terms like LLM and AI instead of Russian when appropriate."
        prompt = f"Read an abstract of the ML paper and return a JSON with fields: 'desc': explanation of the paper in Russian (4 sentences), use correct machine learning terms. 'emoji': emoji that will reflect the theme of an article somehow, only one emoji. 'title': a slogan of a main idea of the article in Russian. Return only JSON and nothing else.\n\n{abs}"

        system_prompt_en = "You are explaining concepts in simple words."
        prompt_en = f"Read an abstract of the ML paper and return a JSON with fields: 'desc': explanation of the paper (4 sentences), use correct machine learning terms. 'title': a slogan of a main idea of the article. Return only JSON and nothing else.\n\n{abs}"

        system_prompt_zh = "You are explaining concepts in simple words in Chinese."
        prompt_zh = f"Read an abstract of the ML paper and return a JSON with fields: 'desc': explanation of the paper in Chinese (4 sentences), use correct machine learning terms. 'title': a slogan of a main idea of the article in Chinese. Return only JSON and nothing else.\n\n{abs}"

        try:
            paper["data"] = api.get_json(
                prompt,
                system_prompt=system_prompt,
                api="claude",
                model="claude-3-5-sonnet-20240620",
                temperature=1.0,
            )
            if not "error" in paper["data"]:
                # classification
                paper["data"]["categories"] = api.get_categories(text=abs)

                # add English desc
                paper["data_en"] = api.get_structured(
                    prompt=prompt_en,
                    system_prompt=system_prompt_en,
                    cls=api.Article,
                    temperature=0,
                    model="gpt-4o-mini",
                )
                # add Chinese desc
                paper["data_zh"] = api.get_structured(
                    prompt=prompt_zh,
                    system_prompt=system_prompt_zh,
                    cls=api.Article,
                    temperature=0,
                    model="gpt-4o-mini",
                )

                # TODO: add fallback

                # rearrange localized data
                paper["data"] = helper.rearrange_data(paper)
                paper.pop("data_en", None)
                paper.pop("data_zh", None)
        except Exception as e:
            paper["data"] = {"error": str(e)}
            log(f"Error getting data: {e}")

        # add embedding
        # log("Get embedding for a paper via LLM API.")
        # paper["data"]["embedding"] = api.get_embedding(paper["abstract"][:6000])

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

# count presented categories
feed["categories"] = helper.counted_cats(feed["papers"])

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
    data["papers"] = [x for x in data["papers"] if "error" not in x["data"]]
    article_classes = ""
    for paper in data["papers"]:
        if paper["score"] >= 20:
            article_classes += f'body.light-theme>div>main>article.x{paper["hash"]} {{ background: url("https://hfday.ru/img/{paper["pub_date"].replace("-","")}/{paper["hash"]}.jpg") !important; background-size: cover !important; background-position: center !important; background-blend-mode: lighten !important; background-color: rgba(255,255,255,0.91) !important;}}\n'
            article_classes += f'body.light-theme>div>main>article.x{paper["hash"]}:hover {{ background-color: rgba(255,255,255,0.95) !important;}}\n'
            article_classes += f'body.dark-theme>div>main>article.x{paper["hash"]} {{ background: url("https://hfday.ru/img/{paper["pub_date"].replace("-","")}/{paper["hash"]}.jpg") !important; background-size: cover !important; background-position: center !important; background-blend-mode: hue !important; background-color: rgba(60,60,60,0.9) !important; }}\n'
            article_classes += f'body.dark-theme>div>main>article.x{paper["hash"]}:hover {{ background-color: rgba(60,60,60,0.92) !important;}}\n'

    cats_html = sorted(
        [f"{k} ({v})" if v else k for k, v in data["categories"].items()]
    )

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
        .a-clean {
            color: var(--secondary-color);
            text-decoration: none;
        }
        .a-clean:hover {
            color: #fff;
        }
        header {
            padding: 3.6em 0 2.4em 0;
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
            color: #e73838;
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
            display: none;
        }
        .category-filters.expanded {
                display: block;
                margin-top: 10px;
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
        .category-button.inactive:not(.active) {
            color: #ccc;
        }
        .dark-theme .category-button {
            background-color: #555;
            color: #fff;
        }
        .dark-theme .category-button.active {
            background-color: var(--primary-color);
        }
        .category-toggle {
            display: inline-block;
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
            padding: 0 20px;
            display: flex;
            justify-content: left;
            gap: 3em;
        }
        .nav-container span a {
            color: white;
        }        
        .nav-item {
            color: white;
            padding: 3px 0px;
            cursor: pointer;
            font-weight: 400;
        }        
        .nav-item:hover {
            background-color: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.3);
        }        
        .language-flags {
            display: flex;
            gap: 7px;
            padding: 5px 0px;
            margin-left: auto;
        }
        .flag-svg {
            width: 22px;
            height: 22px;
            cursor: pointer;
            opacity: 0.4;
            transition: opacity 0.3s ease;
            border-radius: 2px;
        }
        .flag-svg.active {
            opacity: 1;
        }
        .flag-svg:hover {
            opacity: 0.8;
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
                gap: 1.5em;
            }            
            .nav-item {
                padding: 3px 0px;
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
    function getTimeDiff(dateString, lang='ru') {
        const timeUnits = {
            ru: {
                minute: ["минуту", "минуты", "минут"],
                hour: ["час", "часа", "часов"],
                day: ["день", "дня", "дней"],
                justNow: "только что",
                ago: "назад"
            },
            en: {
                minute: ["minute", "minutes", "minutes"],
                hour: ["hour", "hours", "hours"],
                day: ["day", "days", "days"],
                justNow: "just now",
                ago: "ago"
            },
            zh: {
                minute: ["分钟", "分钟", "分钟"],
                hour: ["小时", "小时", "小时"],
                day: ["天", "天", "天"],
                justNow: "刚刚",
                ago: "前"
            }
        };

        function getPlural(number, words, lang) {
            if (lang === 'ru') {
                if (number % 10 === 1 && number % 100 !== 11) {
                    return words[0];
                } else if (number % 10 >= 2 && number % 10 <= 4 && (number % 100 < 10 || number % 100 >= 20)) {
                    return words[1];
                } else {
                    return words[2];
                }
            } else if (lang === 'en') {
                return number === 1 ? words[0] : words[1];
            } else {
                // Chinese doesn't need plural forms
                return words[0];
            }
        }

        function formatTimeDiff(number, unit, lang) {
            const unitWord = getPlural(number, timeUnits[lang][unit], lang);
            
            if (lang === 'zh') {
                return `${number}${unitWord}${timeUnits[lang].ago}`;
            } else {
                return `${number} ${unitWord} ${timeUnits[lang].ago}`;
            }
        }

        if (!['ru', 'en', 'zh'].includes(lang)) {
            throw new Error('Unsupported language. Supported languages are: ru, en, zh');
        }

        const pastDate = new Date(dateString.replace(" ", "T") + ":00Z");
        const currentDate = new Date();
        const diffInSeconds = Math.floor((currentDate - pastDate) / 1000);
        
        const minutes = Math.floor(diffInSeconds / 60);
        const hours = Math.floor(diffInSeconds / 3600);
        const days = Math.floor(diffInSeconds / 86400);

        if (minutes === 0) {
            return timeUnits[lang].justNow;
        } else if (minutes < 60) {
            return formatTimeDiff(minutes, 'minute', lang);
        } else if (hours < 24) {
            return formatTimeDiff(hours, 'hour', lang);
        } else {
            return formatTimeDiff(days, 'day', lang);
        }
    }
    function isToday(dateString) {
        const inputDate = new Date(dateString);
        const today = new Date();
        return (
            inputDate.getFullYear() === today.getFullYear() &&
            inputDate.getMonth() === today.getMonth() &&
            inputDate.getDate() === today.getDate()
        );
    }
    function formatArticlesTitle(number, lang='ru') {
        const lastDigit = number % 10;
        const lastTwoDigits = number % 100;
        let word;

        if (!['ru', 'en', 'zh'].includes(lang)) {
            throw new Error('Unsupported language. Supported languages are: ru, en, zh');
        }

        if (lang === 'ru') {
            if (lastTwoDigits >= 11 && lastTwoDigits <= 14) {
                word = "статей";
            } else if (lastDigit === 1) {
                word = "статья";
            } else if (lastDigit >= 2 && lastDigit <= 4) {
                word = "статьи";
            } else {
                word = "статей";
            }
        } else if (lang === 'en') {
            if (number === 1) {
                word = 'paper'
            } else {
                word = 'papers'
            }
        } else if (lang === 'zh') {
            word = "篇论文"
        }

        if (lang === 'zh') {
            return `${number}${word}`;
        } else {
            return `${number} ${word}`;
        }
    }
    </script>
</head>"""
    )

    html += f"""
<body class="light-theme">
    <header>
        <div class="container">            
            <a href="https://hfday.ru" class="a-clean"><h1 class="title-sign" id="doomgrad-icon">🔺</h1><h1 class="title-text" id="doomgrad">{con.TITLE_LIGHT}</h1></a>
            <p><span id="title-date">{data['date']['ru']}</span> | <span id="title-articles-count">{helper.format_subtitle(len(data['papers']))}</span></p>
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
            <span class="nav-item" id="nav-prev"><a href="/d/{feed['link_prev']}">⬅️ <span id="prev-date">{feed['short_date_prev']['ru']}</span></a></span>
            <span class="nav-item" id="nav-next"><a href="/d/{feed['link_next']}">➡️ <span id="next-date">{feed['short_date_next']['ru']}</span></a></span>
            <!--<span class="nav-item" id="nav-weekly">Топ за неделю</span>
            <span class="nav-item" id="nav-weekly">Топ за месяц</span>-->
            <div class="language-flags">
                <svg class="flag-svg" data-lang="ru" xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><path fill="#1435a1" d="M1 11H31V21H1z"></path><path d="M5,4H27c2.208,0,4,1.792,4,4v4H1v-4c0-2.208,1.792-4,4-4Z" fill="#fff"></path><path d="M5,20H27c2.208,0,4,1.792,4,4v4H1v-4c0-2.208,1.792-4,4-4Z" transform="rotate(180 16 24)" fill="#c53a28"></path><path d="M27,4H5c-2.209,0-4,1.791-4,4V24c0,2.209,1.791,4,4,4H27c2.209,0,4-1.791,4-4V8c0-2.209-1.791-4-4-4Zm3,20c0,1.654-1.346,3-3,3H5c-1.654,0-3-1.346-3-3V8c0-1.654,1.346-3,3-3H27c1.654,0,3,1.346,3,3V24Z" opacity=".15"></path><path d="M27,5H5c-1.657,0-3,1.343-3,3v1c0-1.657,1.343-3,3-3H27c1.657,0,3,1.343,3,3v-1c0-1.657-1.343-3-3-3Z" fill="#fff" opacity=".2"></path></svg>
                <svg class="flag-svg" data-lang="zh" xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><rect x="1" y="4" width="30" height="24" rx="4" ry="4" fill="#db362f"></rect><path d="M27,4H5c-2.209,0-4,1.791-4,4V24c0,2.209,1.791,4,4,4H27c2.209,0,4-1.791,4-4V8c0-2.209-1.791-4-4-4Zm3,20c0,1.654-1.346,3-3,3H5c-1.654,0-3-1.346-3-3V8c0-1.654,1.346-3,3-3H27c1.654,0,3,1.346,3,3V24Z" opacity=".15"></path><path fill="#ff0" d="M7.958 10.152L7.19 7.786 6.421 10.152 3.934 10.152 5.946 11.614 5.177 13.979 7.19 12.517 9.202 13.979 8.433 11.614 10.446 10.152 7.958 10.152z"></path><path fill="#ff0" d="M12.725 8.187L13.152 8.898 13.224 8.072 14.032 7.886 13.269 7.562 13.342 6.736 12.798 7.361 12.035 7.037 12.461 7.748 11.917 8.373 12.725 8.187z"></path><path fill="#ff0" d="M14.865 10.372L14.982 11.193 15.37 10.46 16.187 10.602 15.61 10.007 15.997 9.274 15.253 9.639 14.675 9.044 14.793 9.865 14.048 10.23 14.865 10.372z"></path><path fill="#ff0" d="M15.597 13.612L16.25 13.101 15.421 13.13 15.137 12.352 14.909 13.149 14.081 13.179 14.769 13.642 14.541 14.439 15.194 13.928 15.881 14.391 15.597 13.612z"></path><path fill="#ff0" d="M13.26 15.535L13.298 14.707 12.78 15.354 12.005 15.062 12.46 15.754 11.942 16.402 12.742 16.182 13.198 16.875 13.236 16.047 14.036 15.827 13.26 15.535z"></path><path d="M27,5H5c-1.657,0-3,1.343-3,3v1c0-1.657,1.343-3,3-3H27c1.657,0,3,1.343,3,3v-1c0-1.657-1.343-3-3-3Z" fill="#fff" opacity=".2"></path></svg>
                <svg class="flag-svg" data-lang="en" xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><rect x="1" y="4" width="30" height="24" rx="4" ry="4" fill="#fff"></rect><path d="M1.638,5.846H30.362c-.711-1.108-1.947-1.846-3.362-1.846H5c-1.414,0-2.65,.738-3.362,1.846Z" fill="#a62842"></path><path d="M2.03,7.692c-.008,.103-.03,.202-.03,.308v1.539H31v-1.539c0-.105-.022-.204-.03-.308H2.03Z" fill="#a62842"></path><path fill="#a62842" d="M2 11.385H31V13.231H2z"></path><path fill="#a62842" d="M2 15.077H31V16.923000000000002H2z"></path><path fill="#a62842" d="M1 18.769H31V20.615H1z"></path><path d="M1,24c0,.105,.023,.204,.031,.308H30.969c.008-.103,.031-.202,.031-.308v-1.539H1v1.539Z" fill="#a62842"></path><path d="M30.362,26.154H1.638c.711,1.108,1.947,1.846,3.362,1.846H27c1.414,0,2.65-.738,3.362-1.846Z" fill="#a62842"></path><path d="M5,4h11v12.923H1V8c0-2.208,1.792-4,4-4Z" fill="#102d5e"></path><path d="M27,4H5c-2.209,0-4,1.791-4,4V24c0,2.209,1.791,4,4,4H27c2.209,0,4-1.791,4-4V8c0-2.209-1.791-4-4-4Zm3,20c0,1.654-1.346,3-3,3H5c-1.654,0-3-1.346-3-3V8c0-1.654,1.346-3,3-3H27c1.654,0,3,1.346,3,3V24Z" opacity=".15"></path><path d="M27,5H5c-1.657,0-3,1.343-3,3v1c0-1.657,1.343-3,3-3H27c1.657,0,3,1.343,3,3v-1c0-1.657-1.343-3-3-3Z" fill="#fff" opacity=".2"></path><path fill="#fff" d="M4.601 7.463L5.193 7.033 4.462 7.033 4.236 6.338 4.01 7.033 3.279 7.033 3.87 7.463 3.644 8.158 4.236 7.729 4.827 8.158 4.601 7.463z"></path><path fill="#fff" d="M7.58 7.463L8.172 7.033 7.441 7.033 7.215 6.338 6.989 7.033 6.258 7.033 6.849 7.463 6.623 8.158 7.215 7.729 7.806 8.158 7.58 7.463z"></path><path fill="#fff" d="M10.56 7.463L11.151 7.033 10.42 7.033 10.194 6.338 9.968 7.033 9.237 7.033 9.828 7.463 9.603 8.158 10.194 7.729 10.785 8.158 10.56 7.463z"></path><path fill="#fff" d="M6.066 9.283L6.658 8.854 5.927 8.854 5.701 8.158 5.475 8.854 4.744 8.854 5.335 9.283 5.109 9.979 5.701 9.549 6.292 9.979 6.066 9.283z"></path><path fill="#fff" d="M9.046 9.283L9.637 8.854 8.906 8.854 8.68 8.158 8.454 8.854 7.723 8.854 8.314 9.283 8.089 9.979 8.68 9.549 9.271 9.979 9.046 9.283z"></path><path fill="#fff" d="M12.025 9.283L12.616 8.854 11.885 8.854 11.659 8.158 11.433 8.854 10.702 8.854 11.294 9.283 11.068 9.979 11.659 9.549 12.251 9.979 12.025 9.283z"></path><path fill="#fff" d="M6.066 12.924L6.658 12.494 5.927 12.494 5.701 11.799 5.475 12.494 4.744 12.494 5.335 12.924 5.109 13.619 5.701 13.19 6.292 13.619 6.066 12.924z"></path><path fill="#fff" d="M9.046 12.924L9.637 12.494 8.906 12.494 8.68 11.799 8.454 12.494 7.723 12.494 8.314 12.924 8.089 13.619 8.68 13.19 9.271 13.619 9.046 12.924z"></path><path fill="#fff" d="M12.025 12.924L12.616 12.494 11.885 12.494 11.659 11.799 11.433 12.494 10.702 12.494 11.294 12.924 11.068 13.619 11.659 13.19 12.251 13.619 12.025 12.924z"></path><path fill="#fff" d="M13.539 7.463L14.13 7.033 13.399 7.033 13.173 6.338 12.947 7.033 12.216 7.033 12.808 7.463 12.582 8.158 13.173 7.729 13.765 8.158 13.539 7.463z"></path><path fill="#fff" d="M4.601 11.104L5.193 10.674 4.462 10.674 4.236 9.979 4.01 10.674 3.279 10.674 3.87 11.104 3.644 11.799 4.236 11.369 4.827 11.799 4.601 11.104z"></path><path fill="#fff" d="M7.58 11.104L8.172 10.674 7.441 10.674 7.215 9.979 6.989 10.674 6.258 10.674 6.849 11.104 6.623 11.799 7.215 11.369 7.806 11.799 7.58 11.104z"></path><path fill="#fff" d="M10.56 11.104L11.151 10.674 10.42 10.674 10.194 9.979 9.968 10.674 9.237 10.674 9.828 11.104 9.603 11.799 10.194 11.369 10.785 11.799 10.56 11.104z"></path><path fill="#fff" d="M13.539 11.104L14.13 10.674 13.399 10.674 13.173 9.979 12.947 10.674 12.216 10.674 12.808 11.104 12.582 11.799 13.173 11.369 13.765 11.799 13.539 11.104z"></path><path fill="#fff" d="M4.601 14.744L5.193 14.315 4.462 14.315 4.236 13.619 4.01 14.315 3.279 14.315 3.87 14.744 3.644 15.44 4.236 15.01 4.827 15.44 4.601 14.744z"></path><path fill="#fff" d="M7.58 14.744L8.172 14.315 7.441 14.315 7.215 13.619 6.989 14.315 6.258 14.315 6.849 14.744 6.623 15.44 7.215 15.01 7.806 15.44 7.58 14.744z"></path><path fill="#fff" d="M10.56 14.744L11.151 14.315 10.42 14.315 10.194 13.619 9.968 14.315 9.237 14.315 9.828 14.744 9.603 15.44 10.194 15.01 10.785 15.44 10.56 14.744z"></path><path fill="#fff" d="M13.539 14.744L14.13 14.315 13.399 14.315 13.173 13.619 12.947 14.315 12.216 14.315 12.808 14.744 12.582 15.44 13.173 15.01 13.765 15.44 13.539 14.744z"></path></svg>
            </div>
        </div>
    </div>
    <div class="container">
        <div class="sub-header-container">
            <div class="update-info-container">
                <label class="update-info-label" id="timeDiff"></label>
            </div>
            <div class="sort-container">
                <label class="sort-label">🔀 <span id="sort-label-text">Сортировка по</span></label>
                <select id="sort-dropdown" class="sort-dropdown">
                    <option value="default">рейтингу</option>
                    <option value="pub_date">дате публикации</option>
                    <option value="issue_id">добавлению на HF</option>
                </select>
            </div>
        </div>
        <div class="category-toggle">
            <div class="svg-container">
                <span id="category-toggle">🏷️ Фильтр</span>
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
        // Language handling
        let currentLang = localStorage.getItem('selectedLang') || 'ru';
        let feedDate = {data['date']};
        let feedDateNext = {data['short_date_next']};
        let feedDatePrev = {data['short_date_prev']};
        let filterLabel = {{'ru': 'Фильтр', 'en': 'Topics', 'zh': '主题筛选'}}
        let publishedLabel = {{'ru': 'Статья от ', 'en': 'Published on ', 'zh': '发表于'}}
        let sortLabel = {{'ru': 'Сортировка по', 'en': 'Sort by', 'zh': '排序方式'}}
        let paperLabel = {{'ru': 'Статья', 'en': 'Paper', 'zh': '论文'}}
        
        function initializeLanguageFlags() {{
            const flags = document.querySelectorAll('.flag-svg');
            flags.forEach(flag => {{
                if (flag.dataset.lang === currentLang) {{
                    flag.classList.add('active');
                }}
                flag.addEventListener('click', () => {{
                    flags.forEach(f => f.classList.remove('active'));
                    flag.classList.add('active');
                    currentLang = flag.dataset.lang;
                    localStorage.setItem('selectedLang', currentLang);
                    updateTimeDiffs();
                    updateLocalization();
                    filterAndRenderArticles();
                }});
            }});
        }}
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
            //const categories = getUniqueCategories(articlesData);
            const categories = {cats_html};

            categories.forEach(category => {{
                let catNameSplitted = category.split(/(\s+)/);
                let catName = catNameSplitted[0];
                const button = document.createElement('span');
                button.textContent = catName;
                button.className = 'category-button';
                if (catNameSplitted.length < 2) {{
                    button.classList.add('inactive');
                }};
                button.onclick = () => toggleCategory(catName, button);
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
            if ((selectedArticles.length === articlesData.length) & (selectedCategories.length === 0)) {{
                categoryToggle.textContent = `🏷️ ${{filterLabel[currentLang]}}`;
            }} else {{
                categoryToggle.textContent = `🏷️ ${{filterLabel[currentLang]}} (${{formatArticlesTitle(selectedArticles.length, currentLang)}})`;
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

            //if (filteredArticles.length === 0) {{
            //    selectedArticles = articlesData;
            //    selectedCategories = [];
            //    cleanCategorySelection();
            //}} else {{
            //    selectedArticles = filteredArticles;
            //}}

            selectedArticles = filteredArticles;

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
                
                let explanation = item["data"][currentLang]["desc"];
                let title = item["data"][currentLang]["title"];

                const cats = item["data"]["categories"].join(" ");
                const articleHTML = `
                    <article class='x${{item["hash"]}}'>
                        <div class="background-digit">${{index + 1}}</div>
                        <div class="article-content" onclick="toggleAbstract(${{index}})">
                            <h2>${{item['data']['emoji']}} ${{item['title']}}</h2>
                            <p class="meta"><svg class="text-sm peer-checked:text-gray-500 group-hover:text-gray-500" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" aria-hidden="true" role="img" width="1em" height="1em" preserveAspectRatio="xMidYMid meet" viewBox="0 0 12 12"><path transform="translate(0, 2)" fill="currentColor" d="M5.19 2.67a.94.94 0 0 1 1.62 0l3.31 5.72a.94.94 0 0 1-.82 1.4H2.7a.94.94 0 0 1-.82-1.4l3.31-5.7v-.02Z"></path></svg> ${{item['score']}}. ${{title}}</p>
                            <p class="pub-date">📝 ${{publishedLabel[currentLang]}}${{item['pub_date_card'][currentLang]}}</p>
                            <div id="abstract-${{index}}" class="abstract">
                                <p>${{explanation}}</p>
                                <div id="toggle-${{index}}" class="abstract-toggle">...</div>
                            </div>
                            <div class="links">
                                <a href="${{item['url']}}" target="_blank">${{paperLabel[currentLang]}}</a>
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
            timeDiff.innerHTML = '🔄 ' + getTimeDiff('{data["time_utc"]}',lang=currentLang);
        }}
        function updateSortingOptions() {{
            const sortingLabels = {{
                ru: {{
                    default: "рейтингу",
                    pub_date: "дате публикации",
                    issue_id: "добавлению на HF"
                }},
                en: {{
                    default: "rating",
                    pub_date: "publication date",
                    issue_id: "HF addition date"
                }},
                zh: {{
                    default: "评分",
                    pub_date: "发布日期",
                    issue_id: "HF上传日期"
                }}
            }};

            const dropdown = document.getElementById('sort-dropdown');
            const options = dropdown.options;

            for (let i = 0; i < options.length; i++) {{
                const optionValue = options[i].value;
                console.log(sortingLabels)
                options[i].text = sortingLabels[currentLang][optionValue];
            }}
        }}
        function updateLocalization() {{
            const titleDate = document.getElementById('title-date');
            const prevDate = document.getElementById('prev-date');
            const nextDate = document.getElementById('next-date');
            const papersCount = document.getElementById('title-articles-count');
            const sortLabelText = document.getElementById('sort-label-text');
            titleDate.innerHTML = feedDate[currentLang];
            prevDate.innerHTML = feedDatePrev[currentLang];
            nextDate.innerHTML = feedDateNext[currentLang];
            papersCount.innerHTML = formatArticlesTitle(articlesData.length, currentLang);
            sortLabelText.innerHTML = sortLabel[currentLang];       
            updateSelectedArticlesTitle();
            updateSortingOptions();
        }} 
        function hideNextLink() {{
            if (isToday('{data["time_utc"]}')) {{
                const element = document.getElementById('nav-next');
                if (element) {{    
                    element.style.display = 'none';
                }}
            }}
        }}

        loadSettings();
        createCategoryButtons();
        loadCategorySelection();
        filterAndRenderArticles();
        updateSelectedArticlesTitle();
        updateTimeDiffs();
        hideNextLink(); 
        initializeLanguageFlags();
        updateLocalization();
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

log("Renaming previous page.")
helper.try_rename_file(
    con.PAGE_FILE, con.DATA_DIR, helper.add_date_to_name(name=".html", date=feed_date)
)

log("[Experimental] Generating Chinese page for reading.")
html_zh = make_html_zh(feed)
log("Renaming previous Chinese page.")
helper.try_rename_file(
    "zh.html", con.DATA_DIR, helper.add_date_to_name("_zh_reading_task.html")
)

log("Writing result.")
with open(con.PAGE_FILE, "w", encoding="utf-8") as f:
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

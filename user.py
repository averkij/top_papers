# %%
import json
import os
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

from arxiv import Client, Search
from babel.dates import format_date
from tqdm import tqdm

import api
import constants as con
import helper
from extra import ArxivParser, get_arxiv_id
from helper import log

urls, papers = [], []
if os.path.exists(con.USER_FILE):
    log('Get user file.')
    with open(con.USER_FILE) as fin:
        urls = fin.read().splitlines()
else:
    log("No user file. Exit.")


if urls:
    log(f"Found {len(urls)} URLs")
    for url in urls:
        #check if url is arxiv or huggingface
        if not "arxiv.org" in url and not "huggingface.co" in url:
            log(f"URL {url} is not arxiv or huggingface. Skip.")
            continue
        arxiv_id = get_arxiv_id(url)
        client = Client()
        search = Search(id_list=[arxiv_id])
        paper = next(client.results(search))

        papers.append({
            "id": arxiv_id,
            "title": paper.title,
            "url": url,
            "abstract": paper.summary,
            "score": 1,
            "issue_id": 1,
            "pub_date": datetime.strftime(paper.published, "%Y-%m-%d"),
            "pub_date_card": {
                "ru": format_date(paper.published, format="d MMMM", locale="ru_RU"),
                "en": format_date(paper.published, format="MMMM d", locale="en_US"),
                "zh": helper.format_date_zh(paper.published),
            },
            "hash": helper.get_hash(url),
        })

if len(papers) == 0:
    log("No papers found. Exiting.")
    exit()

#%%

log(f"Downloading and parsing papers (pdf, html). Total: {len(papers)}.")
def do_extra_parsing(url, delete_pdf=True, recalculate_pdf=False, recalculate_html=False):
    parser = ArxivParser(url, delete_pdf=delete_pdf, recalculate_pdf=recalculate_pdf, recalculate_html=recalculate_html)
    _ = parser.download_and_parse_pdf()
    _ = parser.parse_html()

for paper in tqdm(papers):
    url = paper["url"]
    log(f"Downloading and parsing paper {url}.")
    try:
        result = helper.process_with_timeout(
            do_extra_parsing,
            timeout_seconds=con.PDF_PARSING_TIMEOUT,
            url = url,
            delete_pdf=True,
            recalculate_pdf=False,
            recalculate_html=False,
        )
        log("Success.")
    except TimeoutError as e:
        log(f"Extra parsing timeout. ({url}): {e}")    
    except Exception as e:
        log(f"Failed to download and parse paper {url}: {e}")

log("Enriching papers with extra data.")
for paper in tqdm(papers):
    arxiv_id = get_arxiv_id(paper["url"])
    extra_path = os.path.join(con.PAPER_JSON_DIR, f"{arxiv_id}.json")
    if os.path.isfile(extra_path):
        with open(extra_path, "r", encoding="utf-8") as f:
            extra_data = json.load(f)
            paper["authors"] = extra_data["authors"] if "authors" in extra_data else []
            paper["affiliations"] = extra_data["affiliations"] if "affiliations" in extra_data else []

    pdf_title_img_path = os.path.join(con.PAPER_PDF_TITLE_IMG, f"{arxiv_id}.jpg")
    paper["pdf_title_img"] = con.PAPER_PDF_IMAGE_STUB
    if os.path.isfile(pdf_title_img_path):
        pdf_title_img_path = pdf_title_img_path.replace('./','')
        paper["pdf_title_img"] = pdf_title_img_path


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
top_current_month_link = f"{feed_date.strftime('%Y-%m')}.html"

feed = {
    "date": {"ru": formatted_date, "en": formatted_date_en, "zh": formatted_date_zh},
    "time_utc": formatted_time_utc,
    "weekday": weekday,
    "issue_id": 1,
    "papers": papers,
    "link_prev": link_prev,
    "link_next": link_next,
    "link_month": top_current_month_link,
    "short_date_prev": {
        "ru": short_date_prev,
        "en": short_date_prev_en,
        "zh": short_date_prev_zh,
    },
    "short_date_next": {
        "ru": short_date_next,
        "en": short_date_next_en,
        "zh": short_date_next_zh,
    },
}

for i, paper in enumerate(feed["papers"]):
    log("*" * 80)
    log(f'Abstract {i}. {paper["abstract"][:300]}...')


log("Generating reviews via LLM API.")

for paper in tqdm(feed["papers"]):
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
            prompt=prompt,
            system_prompt=system_prompt,
            api="claude",
            model="claude-3-5-sonnet-20240620",
            temperature=1.0,
        )
        # fallback
        if "error" in paper["data"]:
            log("Fallback to OpenAI.")
            paper["data"] = api.get_structured(
                prompt=prompt,
                system_prompt=system_prompt,
                cls=api.ArticleFull,
                temperature=0,
                model="gpt-4o",
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


log("Saving user requested file.")
user_requested_data = []
if os.path.exists(con.USER_REQUESTED_DATA):
    try:
        user_requested_data = json.load(open(con.USER_REQUESTED_DATA, "r", encoding="utf-8"))
    except:
        pass
user_requested_data.extend(feed["papers"])
json.dump(
    user_requested_data,
    open(con.USER_REQUESTED_DATA, "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=4,
)

# %%
# import importlib

# importlib.reload(helper)

log("Generating page.")
for feed_paper in feed["papers"]:
    simple_feed = deepcopy(feed)
    simple_feed["papers"] = [feed_paper]
    simple_feed["categories"] = helper.counted_cats(simple_feed["papers"])
    html_index = helper.make_html(simple_feed, bg_images=False)

    log("Writing result.")
    fname = f"{feed_paper['id']}.html"
    paper_page = f"{con.USER_DIR}/{fname}"
    Path(con.USER_DIR).mkdir(parents=True, exist_ok=True)
    with open(paper_page, "w", encoding="utf-8") as f:
        f.write(html_index)

#%%
name_dict = {}
for d in user_requested_data:
    name_dict[d["id"]] = d["title"]
    
#%%
# import constants as con
# from helper import log
# from arxiv import Client, Search
# name_dict = {}

log(f"Making index file for {con.USER_DIR} folder.")
try:
    files = [f for f in os.listdir(con.USER_DIR) if f.endswith(".html")]
    files = [f for f in files if f != "index.html"][:1]
    log(f"Found {len(files)} files.")

    # Add CSS styles and make it a table
    html = """
    <html>
    <head>
        <title>Doomgrad user papers</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            tr:hover { background-color: #f5f5f5; }
            a { color: #2196F3; text-decoration: none; }
            a:hover { text-decoration: underline; }
            th { background-color: #2196F3; color: white; }
        </style>
    </head>
    <body>
        <h1>User Papers</h1>
        <table>
            <tr><th>Title</th><th>Link</th></tr>
    """
    
    for file in files:
        id = file.replace('.html','')
        if id in name_dict:
            title = name_dict[id]
        else:
            client = Client()
            search = Search(id_list=[id])
            paper = next(client.results(search))
            title = paper.title
            
        html += f'<tr><td>{title}</td><td><a href="{file}">{file}</a></td></tr>'
    
    html += "</table></body></html>"

    log("Writing index file.")
    with open(os.path.join(con.USER_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
except Exception as e:
    log(f"Error making index file: {e}")

log("Clean user file.")
with open(con.USER_FILE, "w") as f:
    f.write("")

log("Done.")

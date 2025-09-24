# %%
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from babel.dates import format_date
from bs4 import BeautifulSoup
from tqdm import tqdm

import api
import constants as con
import helper
from extra import ArxivParser
from helper import log, get_arxiv_id

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
    prev_data, ok = helper.try_get_prev_paper({"id": url, "url": url}, _prev_papers)
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
            "pub_date_card": {
                "ru": format_date(published_date, format="d MMMM", locale="ru_RU"),
                "en": format_date(published_date, format="MMMM d", locale="en_US"),
                "zh": helper.format_date_zh(published_date),
            },
            "hash": helper.get_hash(url),
        }
    )

if len(papers) == 0:
    log("No papers found. Exiting.")
    exit()

log("Obtaining deleted papers (sometimes HF Daily Papers move some articles from today to past days).")
today_paper_ids = [x["id"] for x in papers]
deleted_papers, acc = [], []
try:
    deleted_papers = json.load(open(con.DELETED_DATA_FILE, 'r', encoding='utf8'))
except:
    pass
if _prev_papers and "papers" in _prev_papers:
    for x in _prev_papers["papers"]:
        if x["id"] not in today_paper_ids:
            acc.append(x)
    if acc and not len(acc) == len(_prev_papers["papers"]):
        log(f'Detected {len(acc)} deleted papers. Writing to {con.DELETED_DATA_FILE}')
        deleted_papers.extend(acc)
        json.dump(deleted_papers, open(con.DELETED_DATA_FILE, 'w', encoding='utf8'), ensure_ascii=False, indent=4)
if not acc:
    log("No deleted papers detected.")

log(f"Downloading and parsing papers (pdf, html). Total: {len(papers)}.")
def do_extra_parsing(url, delete_pdf=True, recalculate_pdf=False, recalculate_html=False):
    parser = ArxivParser(url, delete_pdf=delete_pdf, recalculate_pdf=recalculate_pdf, recalculate_html=recalculate_html)
    _ = parser.download_and_parse_pdf()
    _ = parser.parse_html()

for paper in tqdm(papers):
    url = paper["url"]
    log(f"Downloading and parsing paper {url}.")
    try:
        #debug
        # result = helper.process_with_timeout(
        #     do_extra_parsing,
        #     timeout_seconds=con.PDF_PARSING_TIMEOUT,
        #     url = url,
        #     delete_pdf=False,
        #     recalculate_pdf=True,
        #     recalculate_html=False,
        # )
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
    "issue_id": _issue_id + 1,
    "home_page_url": BASE_URL,
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
                prompt=prompt,
                system_prompt=system_prompt,
                api="claude",
                model="claude-sonnet-4-20250514",
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

# Chinese
# def renew_zh(dt_str):
#     dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
#     dt_now = datetime.now(timezone.utc)
#     if (dt.day != dt_now.day) and dt_now.hour > 8:
#         return True
#     return False


# try:
#     if "zh" not in _prev_papers or renew_zh(_prev_papers["zh"]["update_ts"]):
#         log("Trying to get texts in Chinese.")
#         first_abstract = feed["papers"][0]["abstract"]
#         zh_prompt = f"Write simple and brief explanation (4-5 sentences) of an article in Chinese. Use short sentences. Text:\n\n{first_abstract}"
#         zh_text = api.get_text(
#             zh_prompt, api="mistral", model="mistral-large-latest", temperature=0.5
#         )
#         feed["zh"] = {"text": zh_text}
#         feed["zh"]["title"] = feed["papers"][0]["title"]

#         zh_prompt = (
#             f"Write pinyin transcription for text. Text:\n\n{feed['zh']['text']}"
#         )
#         zh_text = api.get_text(
#             zh_prompt, api="mistral", model="mistral-large-latest", temperature=0.0
#         )
#         feed["zh"]["pinyin"] = zh_text

#         zh_prompt = f"Write vocab of difficult words for this text as an array of objects with fields 'word', 'pinyin', 'trans'. Return as python list without formatting. Return list and nothing else. Text:\n\n{feed['zh']['text']}"
#         zh_text = api.get_text(
#             zh_prompt, api="mistral", model="mistral-large-latest", temperature=0.0
#         )
#         feed["zh"]["vocab"] = zh_text

#         zh_prompt = f"Translate this text in English. Text:\n\n{feed['zh']['text']}"
#         zh_text = api.get_text(
#             zh_prompt, api="mistral", model="mistral-large-latest", temperature=0.5
#         )
#         feed["zh"]["trans"] = zh_text
#         feed["zh"]["update_ts"] = formatted_time_utc
#     else:
#         log("Loading Chinese text from previous data.")
#         feed["zh"] = _prev_papers["zh"]

# except Exception as e:
#     log(f"Failed to get Chinese text: {e}")

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
# debug
# with open(con.DATA_FILE, "r", encoding="utf-8") as f:
#     feed = json.load(f)

# import importlib
# importlib.reload(helper)

log("Generating page.")
html_index = helper.make_html(feed, bg_images=False)

log("Renaming previous page.")
helper.try_rename_file(
    con.PAGE_FILE, con.DATA_DIR, helper.add_date_to_name(name=".html", date=feed_date)
)

# log("[Experimental] Generating Chinese page for reading.")
# html_zh = helper.make_html_zh(feed)
# if html_zh:
#     log("Renaming previous Chinese page.")
#     helper.try_rename_file(
#         "zh.html", con.DATA_DIR, helper.add_date_to_name("_zh_reading_task.html")
#     )
#     log("Writing Chinese reading task.")
#     with open("zh.html", "w", encoding="utf-8") as f:
#         f.write(html_zh)

log("Writing result.")
with open(con.PAGE_FILE, "w", encoding="utf-8") as f:
    f.write(html_index)

log("Renaming log file.")
helper.try_rename_file(
    con.LOG_FILE,
    con.LOG_DIR,
    helper.add_date_to_name("_last_log.txt", helper.CURRENT_DATE),
)

# for paper in feed["papers"]:
#     if paper["score"] >= 10:
#         log(f"[Experimental] Generating an image for paper {paper['title']}.")
#         img_name = f"{paper['hash']}.jpg"
#         if not helper.if_paper_image_exists(paper):
#             api.generate_image_for_paper(paper, img_name)
#         else:
#             log(f"[Experimental] Image for paper {paper['title']} already exists.")


# %%
# TOP MONTHLY

import json
import os
from datetime import datetime, timedelta, timezone
from glob import glob
from pathlib import Path

import requests
from babel.dates import format_date
from bs4 import BeautifulSoup
from tqdm import tqdm

import constants as con
import helper
from helper import log

BASE_URL = "https://huggingface.co/papers"
_prev_papers, _issue_id = helper.init()

prev_papers = glob("./d/*.json")

month_to_generate = datetime.now(timezone.utc)
# month_to_generate = datetime.now(timezone.utc) - timedelta(days=30)

month_to_generate_str = month_to_generate.strftime("%Y-%m")
prev_papers = [paper for paper in prev_papers if month_to_generate_str in paper]

papers = []
for doc in prev_papers:
    with open(doc, "r", encoding="utf-8") as fin:
        prev_feed = json.load(fin)
        for paper in prev_feed["papers"]:
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
            if not paper["id"] in [x["id"] for x in papers]:
                papers.append(paper)
            
            #fix pdf image titles
            if "pdf_title_img" not in paper or not paper["pdf_title_img"]:
                paper["pdf_title_img"] = con.PAPER_PDF_IMAGE_STUB

            #fix authors
            if "authors" not in paper or not paper["authors"]:
                paper["authors"] = []

            #fix affiliations
            if "affiliations" not in paper or not paper["affiliations"]:
                paper["affiliations"] = []


from calendar import monthrange
from datetime import date, datetime


def get_month_date(current_date):
    feed_date = current_date
    year = current_date.year
    month = current_date.month
    day = current_date.day

    if month == 1:
        prev_year = year - 1
        prev_month = 12
    else:
        prev_year = year
        prev_month = month - 1    
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    
    _, prev_month_days = monthrange(prev_year, prev_month)
    _, next_month_days = monthrange(next_year, next_month)    
    prev_day = min(day, prev_month_days)
    next_day = min(day, next_month_days)    
    prev_date = date(prev_year, prev_month, prev_day)
    next_date = date(next_year, next_month, next_day)
    
    return feed_date, prev_date, next_date


feed_date, prev_feed_date, next_feed_date = get_month_date(month_to_generate)

formatted_date = format_date(feed_date, format="LLLL YYYY", locale="ru_RU").capitalize()
formatted_date_en = format_date(feed_date, format="LLLL YYYY", locale="en_US")
formatted_date_zh = helper.format_date_zh(feed_date, month_only=True)
short_date_prev = prev_feed_date.strftime("%m.%Y")
short_date_next = next_feed_date.strftime("%m.%Y")
short_date_prev_en = prev_feed_date.strftime("%m/%Y")
short_date_next_en = next_feed_date.strftime("%m/%Y")
short_date_prev_zh = helper.format_date_zh(prev_feed_date, month_only=True)
short_date_next_zh = helper.format_date_zh(next_feed_date, month_only=True)

formatted_time_utc = month_to_generate.strftime("%Y-%m-%d %H:%M")

current_month_page = f"{feed_date.strftime('%Y-%m')}.html"
link_prev = f"{prev_feed_date.strftime('%Y-%m')}.html"
link_next = f"{next_feed_date.strftime('%Y-%m')}.html"

feed = {
    "date": {"ru": formatted_date, "en": formatted_date_en, "zh": formatted_date_zh},
    "time_utc": formatted_time_utc,
    "issue_id": _issue_id + 1,
    "home_page_url": BASE_URL,
    "papers": papers,
    "link_prev": link_prev,
    "link_next": link_next,
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

feed["categories"] = helper.counted_cats(feed["papers"])

log("Generating top page (month).")
html_page = helper.make_html(feed, bg_images=False, format="monthly")

log("Writing top page (month).")
monthly_path = f"./m/{current_month_page}"
Path(monthly_path).parent.mkdir(parents=True, exist_ok=True)
with open(monthly_path, "w", encoding="utf-8") as f:
    f.write(html_page)

# %%

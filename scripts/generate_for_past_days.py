# %%
import json
import os
from datetime import datetime, timedelta

import requests
from babel.dates import format_date
from bs4 import BeautifulSoup
from tqdm import tqdm

import constants as con
import helper
from helper import log, get_arxiv_id
from glob import glob

import api
from extra import ArxivParser


def generate_for_day(day_str):
    FEED_DATE = datetime.strptime(f"{day_str} 09:00", "%Y-%m-%d %H:%M")
    _prev_papers, _issue_id = helper.init(data_file=f"./d/{day_str}.json")

    print("ISSUE ID:", _issue_id)
    print("PREV PAPERS:", _prev_papers["time_utc"] if _prev_papers else None)
    log("Get feed.")


    BASE_URL = f"https://huggingface.co/papers?date={day_str}"

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
            helper.process_with_timeout(
                do_extra_parsing,
                timeout_seconds=con.PDF_PARSING_TIMEOUT,
                url = url,
                delete_pdf=False,
                recalculate_pdf=True,
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


    weekday, feed_date, prev_feed_date, next_feed_date = get_week_info(FEED_DATE)

    formatted_date = format_date(feed_date, format="d MMMM", locale="ru_RU")
    formatted_date_en = format_date(feed_date, format="MMMM d", locale="en_US")
    formatted_date_zh = helper.format_date_zh(feed_date)
    short_date_prev = prev_feed_date.strftime("%d.%m")
    short_date_next = next_feed_date.strftime("%d.%m")
    short_date_prev_en = prev_feed_date.strftime("%m/%d")
    short_date_next_en = next_feed_date.strftime("%m/%d")
    short_date_prev_zh = helper.format_date_zh(prev_feed_date)
    short_date_next_zh = helper.format_date_zh(next_feed_date)

    formatted_time_utc = FEED_DATE.strftime("%Y-%m-%d %H:%M")

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

    log("Loading Chinese text from previous data.")
    if "zh" in _prev_papers:
        feed["zh"] = _prev_papers["zh"]

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
            # log(
            #     f'Using data from previous issue: {json.dumps(prev_data["data"], ensure_ascii=False)[:300]}'
            # )
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
                    model="claude-sonnet-4-5-20250929",
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

    log("Saving new data file.")
    json.dump(
        feed,
        open(con.DATA_FILE, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=4,
    )

    log("Renaming data file.")
    helper.try_rename_file(
        con.DATA_FILE, con.DATA_DIR, helper.add_date_to_name(name=".json", date=feed_date)
    )

    log("Generating page.")
    html_index = helper.make_html(feed, bg_images=False)

    log("Writing result.")
    with open(con.PAGE_FILE, "w", encoding="utf-8") as f:
        f.write(html_index)

    log("Renaming previous page.")
    helper.try_rename_file(
        con.PAGE_FILE, con.DATA_DIR, helper.add_date_to_name(name=".html", date=feed_date)
    )

# %%
# Generate for one day
# generate_for_day("2024-09-30")

# generate_for_day("2024-09-27")
# generate_for_day("2024-09-26")
# generate_for_day("2024-09-25")
# generate_for_day("2024-09-24")
# generate_for_day("2024-09-23")

# generate_for_day("2024-09-20")
# generate_for_day("2024-09-19")
# generate_for_day("2024-09-18")
# generate_for_day("2024-09-17")
# generate_for_day("2024-09-16")

# generate_for_day("2024-09-13")
# generate_for_day("2024-09-12")
# generate_for_day("2024-09-11")
# generate_for_day("2024-09-10")
# generate_for_day("2024-09-09")

# generate_for_day("2024-09-06")
# generate_for_day("2024-09-05")
# generate_for_day("2024-09-04")
# generate_for_day("2024-09-03")
# generate_for_day("2024-09-02")

#%%
prev_papers = glob("./d/*.json")
prev_papers[-46:-41]

#%%
#update all prev issues with missed papers

prev_papers = glob("./d/*.json")

for doc in tqdm(prev_papers[-46:-41]):

    feed_date_str = f"{doc[4:14]}"
    print(feed_date_str)
    generate_for_day(feed_date_str)

# %%
1+1
# %%

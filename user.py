# %%
import json
import os
import time
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import gigadoom as gd
import google.generativeai as genai
import markdown
from arxiv import Client, Search
from babel.dates import format_date
from tqdm import tqdm

import api
import constants as con
import helper
from extra import ArxivParser
from helper import get_arxiv_id, log

urls, papers = [], []
if os.path.exists(con.USER_FILE):
    log("Get user file.")
    with open(con.USER_FILE) as fin:
        urls = fin.read().splitlines()
else:
    log("No user file. Exit.")


# GEMINI
GEMINI_KEY = os.getenv("GEMINI_KEY")

import google.generativeai as genai

def get_text_gemini(prompt):
    genai.configure(api_key=GEMINI_KEY)
    generation_config = {
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
    }
    model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    generation_config=generation_config,
    )
    chat_session = model.start_chat(history=[])
    response = chat_session.send_message(prompt)
    return response.text


if urls:
    log(f"Found {len(urls)} URLs")
    for url in urls:
        # check if url is arxiv or huggingface
        if not "arxiv.org" in url and not "huggingface.co" in url:
            log(f"URL {url} is not arxiv or huggingface. Skip.")
            continue
        arxiv_id = get_arxiv_id(url)
        client = Client()
        search = Search(id_list=[arxiv_id])
        paper = next(client.results(search))

        papers.append(
            {
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
            }
        )

if len(papers) == 0:
    log("No papers found. Exiting.")
    exit()

# %%

log(f"Downloading and parsing papers (pdf, html). Total: {len(papers)}.")
def do_extra_parsing(
    url, delete_pdf=True, recalculate_pdf=False, recalculate_html=False
):
    parser = ArxivParser(
        url,
        delete_pdf=delete_pdf,
        recalculate_pdf=recalculate_pdf,
        recalculate_html=recalculate_html,
    )
    _ = parser.download_and_parse_pdf()
    _ = parser.parse_html()


for paper in tqdm(papers):
    url = paper["url"]
    log(f"Downloading and parsing paper {url}.")
    try:
        result = helper.process_with_timeout(
            do_extra_parsing,
            timeout_seconds=con.PDF_PARSING_TIMEOUT,
            url=url,
            delete_pdf=False,  # debug
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
            paper["affiliations"] = (
                extra_data["affiliations"] if "affiliations" in extra_data else []
            )
            paper["sections"] = (
                extra_data["sections"] if "sections" in extra_data else []
            )

    pdf_title_img_path = os.path.join(con.PAPER_PDF_TITLE_IMG, f"{arxiv_id}.jpg")
    paper["pdf_title_img"] = con.PAPER_PDF_IMAGE_STUB
    if os.path.isfile(pdf_title_img_path):
        pdf_title_img_path = pdf_title_img_path.replace("./", "")
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


# %%
# search in existed papers
from glob import glob

docs = glob(f"{con.DATA_DIR}/*.json")

_prev_papers = {"papers": []}

for doc in docs:
    prev = json.load(open(doc, "r", encoding="utf8"))
    prev_ids = [get_arxiv_id(x["url"]) for x in prev["papers"]]
    feed_ids = [x["id"] for x in feed["papers"]]

    if set(prev_ids).intersection(set(feed_ids)):
        print("detected")
        _prev_papers["papers"].extend(
            [x for x in prev["papers"] if get_arxiv_id(x["url"]) in feed_ids]
        )

    if len(_prev_papers["papers"]) == len(feed["papers"]):
        break

# %%
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


# %%
log("Prepare full review data.")


def check_sections(sections):
    res = sections
    if len(sections) == 2:
        res = [sections[0]]
        print("Trying to split section.")

        abs_len = len(res[0]["content"])
        content_to_split = sections[1]["content"][abs_len - 20 :]

        k = 3
        k_len = (len(content_to_split)) // k
        for i in range(k):
            if i == 0:
                title = "Introduction"
            else:
                title = ""

            res.append(
                {
                    "title": title,
                    "content": content_to_split[i * k_len : (i + 1) * k_len],
                }
            )
    else:
        res = [sections[0]]
        for section in sections[1:]:
            content_to_split = section["content"]

            if len(content_to_split.replace(" ", "")) < 700:
                print("Skip short part")
                continue

            is_abstract = False
            if "abstract" in section["title"].lower():
                abs_len = len(res[0]["content"])
                content_to_split = section["content"][abs_len - 20 :]
                is_abstract = True
            
            content_len = len(content_to_split)
            if content_len < 30000:
                k = 4
            elif content_len < 40000:
                k = 5
            elif content_len < 50000:
                k = 6
            else:
                k = 8

            if len(content_to_split) > 20000:
                print("Split long section")
                k = 3
                k_len = (len(content_to_split)) // k
                for i in range(k):
                    title = ""
                    res.append(
                        {
                            "title": title,
                            "content": content_to_split[i * k_len : (i + 1) * k_len],
                        }
                    )
            else:
                if not is_abstract:
                    res.append(section)
    return res


def check_doc(doc_json):
    stop_words = [
        "references",
        "appendix",
        "acknowledgment",
        "about this document",
    ]
    stop_words_after = ["conclusion"]
    exclude_sections = ["start"]
    # exclude_sections = ['start', 'abstract']
    concatenate_sections = ["preprint"]

    sections = doc_json["sections"][
        :1
    ]  # leave default abstract (from arxiv library) and exclude pdf one
    for section in doc_json["sections"][1:]:
        stop_after = False

        if (
            any([x in section["title"].lower() for x in exclude_sections])
            or not section["content"].strip()
        ):
            continue

        elif any([x in section["title"].lower() for x in concatenate_sections]):
            print("Concatenate to last section", sections[-1]["title"])
            sections[-1]["content"] += f"\n{section['content']}"
            continue
        elif any([x in section["title"].lower() for x in stop_words]):
            print("STOP", section["title"])
            break
        elif any([x in section["title"].lower() for x in stop_words_after]):
            print("STOP AFTER", section["title"])
            stop_after = True

        sections.append({"title": section["title"], "content": section["content"]})

        if stop_after:
            break

    print("len(sections)", len(sections))
    sections = check_sections(sections)
    print("Total len:", sum([len(x["content"]) for x in sections]), "chars")

    return sections


def fix_titles(title, sections):
    updated_titles = []
    for section in sections:
        if section["title"]:
            updated_titles.append(section["title"])
        else:
            prompt = f"""I give you a part of machine learning paper. Create a header for it. It should be short.\nText: \"{section['content'][:2000]}\""""

            generated_title = api.get_text(
                prompt=prompt,
                api="openai",
                model="gpt-4o-mini",
                system_prompt="You returning only one header for text. No explanations needed.",
                temperature=0
            )

            updated_titles.append(generated_title)

            time.sleep(5)

    print("Updated titles:", updated_titles)

    titles = json.dumps(updated_titles, ensure_ascii=False)
    prompt = f"""I will give you a list of headings of machine learning paper. Clean them from digits and make only first letter capital. Keep proper names in capital letters if needed, consider paper title for this purpose: "{title}". Return object with field 'items' with list of headings and nothing else. \nHeadings: [{titles}]"""

    return api.get_structured(
        prompt=prompt,
        cls=api.List,
        model="gpt-4o-mini",
        system_prompt="You return object with field 'items' with list of strings and nothing else.",temperature=0
    )


def make_summary_gemini(text, limit=10000):
    prompt = f"Ты ассистент, который объясняет статьи на тему машинного обучения. Ты отвечаешь на русском языке.\n\nПрочитай текст и напиши его понятное и подробное изложение. Не пиши лишние комментарии (можешь добавлять только комментарии по сути статьи). Это должно выглядеть как изложение одного из разделов статьи, а не как начало отдельной статьи. Пиши на русском.\n\n{text[:limit]}"
    res = get_text_gemini(prompt)
    res = markdown.markdown(res)
    return res

for paper in tqdm(feed["papers"]):
    paper["clean_sections"] = check_doc(paper)
    new_titles = fix_titles(paper["title"], paper["clean_sections"])["items"]
    print("new_titles", new_titles)

    if len(new_titles) == len(paper["clean_sections"]):
        for i, section in enumerate(paper["clean_sections"]):
            section["title"] = new_titles[i].replace("#", "").strip()
    else:
        print("Different headings")

    log("Generating summaries")
    for section in tqdm(paper["clean_sections"]):
        # section["summary"] = make_summary(section["content"])
        section["summary"] = make_summary_gemini(section["content"])


# %%
for section in paper["clean_sections"]:
    print(len(section["content"]), len(section["summary"]), section["title"])


# %%
log("Saving user requested file.")
for paper in feed["papers"]:
    paper.pop("sections", None)
user_requested_data = []
if os.path.exists(con.USER_REQUESTED_DATA):
    try:
        user_requested_data = json.load(
            open(con.USER_REQUESTED_DATA, "r", encoding="utf-8")
        )
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
import importlib

importlib.reload(helper)

#load from file for editing
user_requested_data = json.load(open(con.USER_REQUESTED_DATA, "r", encoding="utf-8"))


log("Generating page.")
for feed_paper in feed["papers"]:
    img_data_path = f"{con.PAPER_IMG_DATA_DIR}/{feed_paper['id']}.json"
    print(img_data_path)
    if os.path.exists(img_data_path):
        print('Found img data')
        img_data = json.load(open(img_data_path, "r", encoding="utf-8"))

    edited_paper = [x for x in user_requested_data if x["id"] == feed_paper['id']]
    if edited_paper:
        print("Found edited paper")
        feed_paper = edited_paper[0]
        # for s in feed_paper["clean_sections"]:
        #     s["summary"] = markdown.markdown(s["summary"])
    else:
        print("Not found edited paper")

    simple_feed = deepcopy(feed)
    simple_feed["papers"] = [feed_paper]
    simple_feed["categories"] = helper.counted_cats(simple_feed["papers"])

    html_index = helper.make_html(simple_feed, bg_images=False, is_full=True, img_data=img_data)

    log("Writing result.")
    fname = f"{feed_paper['id']}.html"
    paper_page = f"{con.USER_DIR}/{fname}"
    Path(con.USER_DIR).mkdir(parents=True, exist_ok=True)
    with open(paper_page, "w", encoding="utf-8") as f:
        f.write(html_index)

# %%
name_dict = {}
for d in user_requested_data:
    name_dict[d["id"]] = d["title"]

# %%
# import constants as con
# from helper import log
# from arxiv import Client, Search
# name_dict = {}

log(f"Making index file for {con.USER_DIR} folder.")
try:
    files = [f for f in os.listdir(con.USER_DIR) if f.endswith(".html")]
    files = [f for f in files if f != "index.html"]
    files.sort(key=lambda x: os.path.getctime(f"./u/{x}"), reverse=True)

    log(f"Found {len(files)} files.")

    # Add CSS styles and make it a table
    html = """
    <html>
    <head>
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-C1CRWDNJ1J"></script>
        <script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-C1CRWDNJ1J');
        </script>
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
            <tr><th>#</th><th>Title</th><th>Link</th></tr>
    """

    for i, file in enumerate(files, 1):
        id = file.replace(".html", "")
        if id in name_dict:
            title = name_dict[id]
        else:
            client = Client()
            search = Search(id_list=[id])
            paper = next(client.results(search))
            title = paper.title

        html += (
            f'<tr><td>{i}</td><td>{title}</td><td><a href="{file}">{file}</a></td></tr>'
        )

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

# %%

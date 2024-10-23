import hashlib
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from babel.dates import format_date

import constants as con

CURRENT_YEAR = datetime.now(timezone.utc).year
CURRENT_DATE = datetime.now(timezone.utc)

from bs4 import BeautifulSoup


def init():
    Path(con.LOG_DIR).mkdir(exist_ok=True)
    Path(con.DATA_DIR).mkdir(exist_ok=True)

    if os.path.isfile(con.DATA_FILE):
        log("Read previous papers.")
        with open(con.DATA_FILE, "r", encoding="utf-8") as f:
            prev_papers = json.load(f)
    else:
        log("No previous papers found.")
        prev_papers = {}

    if "issue_id" in prev_papers:
        issue_id = prev_papers["issue_id"]
    else:
        issue_id = 0

    return prev_papers, issue_id


def log(msg):
    print(msg)
    with open(con.LOG_FILE, "a", encoding="utf-8") as fout:
        date = datetime.now().strftime("%d.%m.%Y %H:%M")
        fout.write(f"[{date}] {msg}\n")


def try_rename_file(fpath, new_dir, new_name=None):
    if not new_name:
        new_fpath = os.path.join(new_dir, fpath)
    else:
        new_fpath = os.path.join(new_dir, new_name)
    if os.path.isfile(fpath):
        log(f"Renaming previous data. {fpath} to {new_fpath}")
        try:
            os.remove(new_fpath)
        except OSError:
            pass
        os.replace(fpath, new_fpath)
    else:
        log(f"No file to rename. {fpath}")

def add_date_to_name(name, date=None):
    if not date:    
        date = datetime.now() - timedelta(1)        
    date = date.strftime("%Y-%m-%d")
    new_fpath = f"{date}{name}"
    return new_fpath


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
        date_sort = "1963-01-17"
        date_ru = format_date(CURRENT_DATE, format="d MMMM", locale="ru_RU")
        log(f"Error. Unable to format date {date_str}")
    return date_sort, date_ru


def try_get_prev_paper(paper, prev_papers):
    prev_data = None
    if "papers" in prev_papers:
        prev_ids = [x["id"] for x in prev_papers["papers"]]
        if paper["id"] in prev_ids:
            prev_paper = [x for x in prev_papers["papers"] if x["id"] == paper["id"]][0]
            if "data" in prev_paper and not "error" in prev_paper["data"]:
                prev_data = prev_paper
    return prev_data, bool(prev_data)


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


def get_hash(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:16]


def if_paper_image_exists(paper):
    img_path = os.path.join(
        con.IMG_DIR, paper["pub_date"].replace("-", ""), f"{paper['hash']}.jpg"
    )
    return os.path.isfile(img_path)

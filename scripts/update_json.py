# %%
from glob import glob
import helper
import constants as con
import api
import json

prev_papers = glob("./d/*.json")

len(prev_papers)

# %%
import json
from datetime import datetime, timezone, timedelta

for doc in prev_papers:
    with open(doc, "r", encoding="utf-8") as fin:
        feed = json.load(fin)

        for paper in feed["papers"]:
            abs = paper["abstract"][:3000]
            paper["data"]["categories"] = api.get_categories(abs)

    json.dump(
        feed,
        open(doc, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=4,
    )

    # break
# %%
for doc in prev_papers:
    with open(doc, "r", encoding="utf-8") as fin:
        feed = json.load(fin)

        for paper in feed["papers"]:
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

    json.dump(
        feed,
        open(doc, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=4,
    )


# %%
# add hashes

for doc in prev_papers:
    with open(doc, "r", encoding="utf-8") as fin:
        feed = json.load(fin)

        for paper in feed["papers"]:
            paper["hash"] = helper.get_hash(paper["url"])

    json.dump(
        feed,
        open(doc, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=4,
    )
# %%
# add counted categories

for doc in prev_papers:
    with open(doc, "r", encoding="utf-8") as fin:
        feed = json.load(fin)

        feed["categories"] = helper.counted_cats(feed["papers"])

    json.dump(
        feed,
        open(doc, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=4,
    )
# %%
for json_path in prev_papers[1:]:
    with open(json_path, "r", encoding="utf-8") as fin:
        feed = json.load(fin)

        for paper in feed["papers"]:
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

            abs = paper["abstract"][:3000]

            system_prompt_en = "You are explaining concepts in simple words."
            prompt_en = f"Read an abstract of the ML paper and return a JSON with fields: 'desc': explanation of the paper (4 sentences), use correct machine learning terms. 'title': a slogan of a main idea of the article. Return only JSON and nothing else.\n\n{abs}"

            system_prompt_zh = "You are explaining concepts in simple words in Chinese."
            prompt_zh = f"Read an abstract of the ML paper and return a JSON with fields: 'desc': explanation of the paper in Chinese (4 sentences), use correct machine learning terms. 'title': a slogan of a main idea of the article in Chinese. Return only JSON and nothing else.\n\n{abs}"

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
            
            paper["data"] = helper.rearrange_data(paper)
            paper.pop('data_en', None)
            paper.pop('data_zh', None)

    json.dump(
        feed,
        open(json_path, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=4,
    )

#%%
1+1
# %%
emb = {}

for json_path in prev_papers:
    with open(json_path, "r", encoding="utf-8") as fin:
        feed = json.load(fin)

        for p in feed["papers"]:
            if "embedding" in p["data"]:
                emb[p["hash"]] = p["data"]["embedding"]

json.dump(
    emb,
    open('./embeddings.json', "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=4,
)


# %%
#add dates
from babel.dates import format_date
from datetime import datetime, timezone, timedelta

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

for doc in prev_papers:
    with open(doc, "r", encoding="utf-8") as fin:
        feed = json.load(fin)
        
        feed_date_str = f"{doc[4:14]} 20:26"
        feed_date = datetime.strptime(feed_date_str, "%Y-%m-%d %H:%M")

        for paper in feed["papers"]:
            published_date = datetime.strptime(paper["pub_date"], "%Y-%m-%d")
            paper["pub_date_card"] = {'ru': format_date(published_date, format="d MMMM", locale="ru_RU"),
                              'en': format_date(published_date, format="MMMM d", locale="en_US"),
                              'zh': helper.format_date_zh(published_date)}
        
        formatted_date = format_date(feed_date, format="d MMMM", locale="ru_RU")
        formatted_date_en = format_date(feed_date, format="MMMM d", locale="en_US")
        formatted_date_zh = helper.format_date_zh(feed_date)
            
        feed["date"] = {'ru': formatted_date, 'en': formatted_date_en, 'zh': formatted_date_zh}

        weekday, feed_date, prev_feed_date, next_feed_date = get_week_info(feed_date)

        short_date_prev = prev_feed_date.strftime("%d.%m")
        short_date_next = next_feed_date.strftime("%d.%m")
        short_date_prev_en = prev_feed_date.strftime("%m/%d")
        short_date_next_en = next_feed_date.strftime("%m/%d")
        short_date_prev_zh = helper.format_date_zh(prev_feed_date)
        short_date_next_zh = helper.format_date_zh(next_feed_date)
        
        feed["short_date_prev"] = {'ru': short_date_prev, 'en': short_date_prev_en, 'zh': short_date_prev_zh}
        feed["short_date_next"] = {'ru': short_date_next, 'en': short_date_next_en, 'zh': short_date_next_zh}

    json.dump(
        feed,
        open(doc, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=4,
    )

# %%

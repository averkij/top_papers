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
                model="gpt-4o",
            )
            # add Chinese desc
            paper["data_zh"] = api.get_structured(
                prompt=prompt_zh,
                system_prompt=system_prompt_zh,
                cls=api.Article,
                temperature=0,
                model="gpt-4o",
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

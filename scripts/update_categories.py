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

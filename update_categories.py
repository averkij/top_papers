#%%
from glob import glob
import helper
import constants as con
import api

prev_papers = glob('./d/*.json')

len(prev_papers)

# %%
import json
from datetime import datetime, timezone, timedelta

for doc in prev_papers[2:]:
    with open(doc, "r", encoding="utf-8") as fin:
        feed = json.load(fin)

        for p in feed["papers"]:
            abs = p["abstract"][:3000]
            p["data"]["categories"] = api.get_categories(p)

    json.dump(
        feed,
        open(doc, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=4,
    )

    # break
# %%
1+1
# %%

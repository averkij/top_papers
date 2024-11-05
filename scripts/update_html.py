# %%
from glob import glob
from babel.dates import format_date
import helper
import constants as con

prev_papers = glob("./d/*.json")

len(prev_papers)

#%%

import json
from datetime import datetime, timezone, timedelta

for doc in prev_papers:
    with open(doc, "r", encoding="utf-8") as fin:
        feed = json.load(fin)

        html_index = helper.make_html(feed)

    html_path = doc.replace("json", "html")

    with open(html_path, "w", encoding="utf-8") as fout:
        fout.write(html_index)

    # break


# %%

#%%
# %%
from glob import glob
import helper
import constants as con
import api
import json
import time
import extra

prev_data = glob("./assets/json/*.json")

len(prev_data)


# %%
#ADD MISSED AFFILIATIONS

limit = 10000
for i,data in enumerate(prev_data):
    if i <= 81:
        continue

    doc = json.load(open(data, encoding="utf8"))

    if not doc["affiliations"] or "error" in doc["affiliations"]:
        print(">", i)
        acc = ""
        rest_len = limit

        for section in doc["sections"][1:]:
            if rest_len >= 0:
                take_text = section["content"][:rest_len]
                acc += take_text
                rest_len -= len(acc)
            else:
                break

            # print(section["title"])
            # print(len(section["content"]))

        # print(len(acc))
        # print(acc)

        affiliations = extra.get_affiliations(acc[:6500], api='mistral', model='mistral-large-latest')
        print(affiliations)

        if affiliations:
            doc["affiliations"] = affiliations
            json.dump(doc, open(data, 'w', encoding="utf8"), ensure_ascii=False, indent=4)
            print("*" * 80)
        
        time.sleep(1)

        # break
# %%


#%%
from glob import glob
from babel.dates import format_date
import json
from datetime import datetime, timezone, timedelta

prev_papers = glob('../d/*.json')

len(prev_papers)

CURRENT_DATE = datetime.now(timezone.utc)

# %%
def get_week_info(date):
    weekday = date.weekday()
    feed_date = date
    prev_feed_date = feed_date - timedelta(1)
    next_feed_date = feed_date + timedelta(1)

    #HF Daily don't have updates on weekend
    if weekday == 0: #Monday
        prev_feed_date = prev_feed_date - timedelta(2)
    if weekday == 4: #Friday
        next_feed_date = next_feed_date + timedelta(2)
    if weekday == 5: #Saturday
        weekday = 4
        feed_date = feed_date - timedelta(1)
        prev_feed_date = prev_feed_date - timedelta(1)
        next_feed_date = next_feed_date + timedelta(1)
    elif weekday == 6: #Sunday
        weekday = 4
        feed_date = feed_date - timedelta(2)
        prev_feed_date = prev_feed_date - timedelta(2)
    return weekday, feed_date, prev_feed_date, next_feed_date

for doc in prev_papers:
    with open(doc, "r", encoding="utf-8") as fin:
        feed = json.load(fin)

        weekday, feed_date, prev_feed_date, next_feed_date = get_week_info(CURRENT_DATE)

        formatted_date = format_date(feed_date, format="d MMMM", locale="ru_RU")
        formatted_date_en = format_date(feed_date, format="d MMMM", locale="en_US")
        formatted_date_prev = format_date(prev_feed_date, format="d MMMM", locale="ru_RU")
        formatted_date_next = format_date(next_feed_date, format="d MMMM", locale="ru_RU")
        short_date_prev = prev_feed_date.strftime('%d.%m')
        short_date_next = next_feed_date.strftime('%d.%m')

        feed["date_en"] = formatted_date_en
        feed["date_prev"] = formatted_date_prev
        feed["date_next"] = formatted_date_next
        feed["short_date_prev"] = short_date_prev
        feed["short_date_next"] = short_date_next

    json.dump(
        feed,
        open(doc, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=4,
    )

# %%

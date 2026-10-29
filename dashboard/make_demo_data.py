"""
Builds dashboard/demo-data.js: made-up sample data for the dashboard's demo
mode (the version hosted on GitHub Pages). Nothing here comes from a real
scrape: creators, posts, authors and links are all generated.

The demo searches a single term, "kopitiam". Its creator section scores
kopitiam food creators as collaboration leads, using the same four signal
columns as the real agency scraper with food-creator words in them. The
page relabels those columns in demo mode.

The file holds two snapshots, "before" and "after", so a simulated run in
the demo visibly adds creators and updates engagement, plus an English
translation of every Chinese string ("i18n") for the page's language toggle.

    python dashboard/make_demo_data.py
"""

import json
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent

SEARCH_TERM = "kopitiam"
# What the demo pretends each scraper searched for.
DEMO_CREATOR_SEARCH = {"tiers": [{"tier": None, "name": "Search term", "sort": "popularity_descending",
                                  "keywords": [SEARCH_TERM]}]}
DEMO_POST_SEARCH = {"keywords": [SEARCH_TERM], "max_results": 20,
                    "sort": "popularity_descending", "note_type": "all", "time_filter": "all"}

# English for every Chinese string the demo uses; filled in as strings are made.
I18N = {}


def en(zh, english):
    """Record a translation and return the original (Chinese) text."""
    if zh and zh != english:
        I18N[zh] = english
    return zh


# Words a kopitiam collaboration lead's captions might use, per signal column.
DEMO_SIGNALS = {
    "food_creator": [en("探店", "food hunting"), en("美食博主", "food blogger"), en("吃货", "foodie"),
                     en("测评", "reviews"), en("美食分享", "food sharing"), "vlog"],
    "kopitiam_focus": ["kopitiam", en("茶室", "tea house"), en("南洋咖啡", "Nanyang coffee"), en("咖椰吐司", "kaya toast"),
                       en("白咖啡", "white coffee"), en("老字号", "heritage shop"), en("半熟蛋", "soft-boiled eggs")],
    "contact_route": [en("私信", "DM"), en("邮箱", "email"), en("合作请联系", "contact for collabs"), "WhatsApp",
                      en("vx", "WeChat")],
    "collab_intent": [en("合作", "collab"), en("商务合作", "business collab"), en("品牌合作", "brand partnership"),
                      en("探店邀约", "tasting invite"), en("置换", "barter deal")],
}

rng = random.Random(7)

# Same columns and points as the real scraper; the page shows them as
# Food creator / Kopitiam focus / Contact route / Open to collabs.
SIGNAL_COLUMNS = {
    "operator_signals": ("food_creator", 25),
    "group_signals": ("kopitiam_focus", 20),
    "contact_signals": ("contact_route", 15),
    "commercial_signals": ("collab_intent", 10),
}
# How often a demo creator shows each kind of signal.
SIGNAL_ODDS = {"operator_signals": 0.8, "group_signals": 0.6, "contact_signals": 0.3, "commercial_signals": 0.45}

# Creator names, masked the way MediaCrawler masks them (first and last character kept).
NICKS = [("吃货小玲", "FoodieLing"), ("阿茶日记", "AhChaDiary"), ("咖啡小林", "CoffeeLim"), ("探店阿杰", "JayEats"),
         ("美食小黄", "WongBites"), ("茶室日常", "KopitiamDaily"), ("小美爱吃", "MeiLovesFood"), ("陈陈探店", "ChenExplores"),
         ("早餐阿玲", "BreakfastLing"), ("南洋咖啡控", "NanyangFan"), ("吉隆坡吃货", "KLFoodie"), ("怡保小陈", "IpohChen")]
NOTE_TITLES = [
    ("这家 kopitiam 开了{n}年，早餐还是要排队", "This kopitiam has been open {n} years and still has a breakfast queue"),
    ("kopitiam 早餐合集｜第{n}家最惊喜", "Kopitiam breakfast roundup | #{n} surprised me most"),
    ("跟着本地人吃 kopitiam，人均 RM{n}", "Eating kopitiam like a local for RM{n} a head"),
    ("怡保白咖啡 vs 南洋咖啡，我喝了{n}杯", "Ipoh white coffee vs Nanyang coffee: I drank {n} cups"),
    ("kopitiam 探店 vlog 第{n}集", "Kopitiam food-hunting vlog, episode {n}"),
    ("kopitiam 隐藏菜单｜点了{n}样", "Kopitiam secret menu | I ordered {n} things"),
    ("咖椰吐司+半熟蛋，{n}块钱的幸福", "Kaya toast and soft-boiled eggs: {n} ringgit of happiness"),
    ("带外国朋友去 kopitiam，{n}分钟就爱上", "Took overseas friends to a kopitiam and they were hooked in {n} minutes"),
]


def masked_nick():
    zh, english = rng.choice(NICKS)
    return en(f"{zh[0]}***{zh[-1]}", f"{english[:2]}***{english[-2:]}")


def lead(i, today):
    row = {"score": 0, "nickname": masked_nick(), "creator_id": f"demo{rng.getrandbits(48):012x}"}
    row["tiers"] = "1"
    row["keywords"] = SEARCH_TERM
    n_posts = rng.choices([1, 2, 3, 4, 6], weights=[60, 20, 8, 8, 4])[0]
    top = int(rng.lognormvariate(4.2, 1.1))
    row["n_posts"] = n_posts
    row["top_likes"] = top
    row["total_likes"] = top + sum(int(rng.lognormvariate(2.5, 1.0)) for _ in range(n_posts - 1))
    score = 0
    for col, (key, pts) in SIGNAL_COLUMNS.items():
        if rng.random() < SIGNAL_ODDS[col]:
            terms = rng.sample(DEMO_SIGNALS[key], rng.choice([1, 1, 2, 3]))
            row[col] = ", ".join(terms)
            score += pts
        else:
            row[col] = ""
    row["score"] = score
    row["latest_post"] = (today - timedelta(days=int(rng.expovariate(1 / 60)))).isoformat()
    n = rng.choice([3, 5, 8, 12, 20, 30])
    zh, english = rng.choice(NOTE_TITLES)
    row["top_note_title"] = en(zh.format(n=n), english.format(n=n))
    row["top_note_url"] = f"demo://note/{i}"
    # Same column order as scrape_agencies.py writes.
    cols = ["score", "nickname", "creator_id", "tiers", "keywords", "n_posts", "top_likes", "total_likes",
            "operator_signals", "group_signals", "contact_signals", "commercial_signals",
            "latest_post", "top_note_title", "top_note_url"]
    return {c: row[c] for c in cols}


POSTS = [  # (title, caption), each as (Chinese, English)
    (("🇲🇾RM9.90 椰浆饭排队现场🔥", "🇲🇾The RM9.90 nasi lemak queue 🔥"),
     ("排了一个小时才吃到，值不值得？ #kopitiam #椰浆饭", "Queued an hour for it. Worth it? #kopitiam #nasilemak")),
    (("Kopi O 冰 vs 热，你站哪边？", "Kopi O, iced or hot? Pick a side"), ("老板说本地人都喝热的 #kopi", "The owner says locals drink it hot #kopi")),
    (("", ""), ("新分店开张第一天，人比想象中多太多了", "Opening day at the new branch, and it was far busier than expected")),
    (("吉隆坡早餐地图｜10家 kopitiam", "KL breakfast map | 10 kopitiams"), ("收藏这一篇就够了 #吉隆坡美食", "Save this one and you're set #KLfood")),
    (("kopitiam 隐藏菜单大公开", "Kopitiam secret menu revealed"), ("老板说熟客才知道 #kopitiam", "The owner says only regulars know #kopitiam")),
    (("Kaya toast 做法大公开", "How to make kaya toast"), ("在家也能做出茶室味道", "Get that kopitiam taste at home")),
    (("下午茶 set 只要 RM12.90", "Afternoon tea set for just RM12.90"), ("两个人刚刚好", "Just right for two")),
    (("带外国朋友第一次去 kopitiam", "Taking overseas friends to their first kopitiam"), ("他们的反应太好笑了 #kopitiam", "Their reactions were hilarious #kopitiam")),
    (("茶室打工一天 vlog", "A day working at a kopitiam (vlog)"), ("原来冲一杯 kopi 有这么多讲究", "Who knew a cup of kopi took this much skill")),
    (("新品试吃：咸蛋鸡腿饭", "Taste test: salted egg chicken rice"), ("说实话有点惊艳", "Honestly, pretty impressive")),
    (("怡保白咖啡到底好在哪", "What makes Ipoh white coffee so good?"), ("跟老师傅学了一下午", "Spent an afternoon learning from a master")),
    (("周末排队攻略｜避开人潮", "Weekend queue guide | beat the crowds"), ("早上 8 点前去最稳", "Go before 8am to be safe")),
    (("", ""), ("这家的 roti bakar 真的会想念", "I'm going to miss this place's roti bakar")),
    (("茶室联名周边开箱", "Unboxing the kopitiam collab merch"), ("杯子太可爱了", "The cups are too cute")),
    (("马来西亚人的一天从这里开始☕", "Where a Malaysian's day begins ☕"), ("#早餐 #kopitiam", "#breakfast #kopitiam")),
]


def posts(today, boost=1.0):
    rows = []
    for i, ((title, title_en), (desc, desc_en)) in enumerate(POSTS):
        en(title, title_en)
        en(desc, desc_en)
        r = random.Random(100 + i)  # same base numbers in both snapshots
        likes = int(r.lognormvariate(5.2, 0.9) * boost)
        collects = int(likes * r.uniform(0.15, 0.9))
        comments = int(likes * r.uniform(0.02, 0.25))
        shares = int(likes * r.uniform(0.05, 0.8))
        score = likes + collects * 2 + comments * 1.5 + shares * 1.5
        when = datetime.combine(today - timedelta(days=r.randint(3, 300)), datetime.min.time()) + timedelta(minutes=r.randint(420, 1380))
        rows.append({
            "score": round(score, 1), "title": title, "description": desc, "hashtags": "",
            "likes": likes, "collects": collects, "comments": comments, "shares": shares,
            "author": f"demo_foodie_{i + 1:02d}", "url": f"demo://post/{i}", "time": when.isoformat(),
        })
    rows.sort(key=lambda p: p["score"], reverse=True)
    return rows


def snapshot(leads, post_rows, stamp):
    leads = sorted(leads, key=lambda r: (r["score"], r["top_likes"]), reverse=True)
    return {
        "leads": [{k: str(v) for k, v in r.items()} for r in leads],
        "leads_file": {"name": "agencies.csv", "modified": stamp},
        "posts": [{k: str(v) for k, v in r.items()} for r in post_rows],
        "posts_file": {"name": "oriental_kopi_search.csv", "modified": stamp},
        "search": {"agencies": dict(DEMO_CREATOR_SEARCH, source="run", ran_at=stamp),
                   "posts": dict(DEMO_POST_SEARCH, source="run", ran_at=stamp)},
    }


if __name__ == "__main__":
    today = date(2026, 10, 1)
    base = [lead(i, today) for i in range(48)]
    extra = [lead(100 + i, today + timedelta(days=1)) for i in range(7)]
    data = {
        "before": snapshot(base, posts(today), "2026-10-01T09:30:00"),
        "after": snapshot(base + extra, posts(today, boost=1.08), "2026-10-02T09:30:00"),
    }
    # Every Chinese string the page can show must have an English version.
    cjk = re.compile(r"[\u3400-\u9fff]")
    missing = {term for snap in data.values() for rows in (snap["leads"], snap["posts"]) for r in rows
               for v in r.values() for term in [v, *v.split(", ")] if cjk.search(term) and term not in I18N
               and not all(t in I18N or not cjk.search(t) for t in v.split(", "))}
    assert not missing, f"No English for: {sorted(missing)}"
    data["i18n"] = {"en": I18N}
    out = HERE / "demo-data.js"
    out.write_text(
        "// Made-up sample data for demo mode. Generated by make_demo_data.py; not from a real scrape.\n"
        "window.DEMO_DATA = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {out} ({len(base)} -> {len(base) + len(extra)} leads, {len(POSTS)} posts)")

"""
RedNote (Xiaohongshu) competitor research scraper -- Oriental Kopi.

Uses the Apify actor "zen-studio/rednote-search-scraper"
(console: https://console.apify.com/actors/hO5NqsA6aC1bz3jra/input).

Confirmed input parameters (from the actor's Input tab):
    keywords              string[]  required  search terms (CN/EN/hashtag/emoji ok)
    maxResults             integer  default 100, per keyword, 0-10000 (0 = all)
    sortType                string  general / popularity_descending / time_descending
    topUpFromOtherSorts    boolean  default true -- merges across sort orders for
                                    more unique notes; deeper time-range sweep only
                                    kicks in above maxResults=1000
    noteType                string  all / video / image / live
    timeFilter              string  all / 1d / 1w / 6mo

No login/cookies needed for this actor.

The actor's OUTPUT field names weren't independently verifiable ahead of
time, so engagement_score()/save_outputs() use pick() to check several
common variants per field. PRINT_RAW_SAMPLE prints one raw result on first
run so you can confirm field names match (and tell me if they don't, so I
can tighten pick() to the real names).

Setup:
    pip install -r requirements.txt
    Create a .env file in this folder with:
        APIFY_API_TOKEN=your_token   # console.apify.com/settings/integrations

Cost note: pricing wasn't shown in what you pasted -- check the actor's
Pricing tab before a big run, since cost scales linearly with maxResults
and each keyword gets its own budget (2 keywords x maxResults=100 = up to
200 notes billed). Start small (e.g. maxResults=20) to sanity-check output
before scaling up.
"""

import os
import csv
import json
from datetime import datetime, timedelta, timezone
from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

ACTOR_ID = "zen-studio/rednote-search-scraper"
API_TOKEN = os.environ.get("APIFY_API_TOKEN")

SEARCH_KEYWORDS = [
    "地接星耀",
    "🇸🇬本地地陪"
    # add their Chinese-name variant here once confirmed from their profile
]

# Actor input settings -- tune as needed
MAX_RESULTS_PER_KEYWORD = 20    # start small; raise once output looks right
SORT_TYPE = "popularity_descending"   # best fit for "trending/hot topics"
TOP_UP_FROM_OTHER_SORTS = True
NOTE_TYPE = "all"
TIME_FILTER = "all"

PRINT_RAW_SAMPLE = True


def get_dataset_id(run):
    """apify-client has changed Run from a plain dict to a typed object in
    some versions -- support both so this doesn't break on version bumps."""
    if isinstance(run, dict):
        return run.get("defaultDatasetId") or run.get("default_dataset_id")
    return getattr(run, "defaultDatasetId", None) or getattr(run, "default_dataset_id", None)


def get_client():
    if not API_TOKEN:
        raise SystemExit("Set APIFY_API_TOKEN in .env first.")
    return ApifyClient(API_TOKEN)


def run_search(client, keywords, max_results):
    run_input = {
        "keywords": keywords,
        "maxResults": max_results,
        "sortType": SORT_TYPE,
        "topUpFromOtherSorts": TOP_UP_FROM_OTHER_SORTS,
        "noteType": NOTE_TYPE,
        "timeFilter": TIME_FILTER,
    }
    return client.actor(ACTOR_ID).call(run_input=run_input)


def pick(d, *keys, default=None):
    """Returns the first present value among several possible key names,
    since the exact output schema wasn't independently verified."""
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return default


def get_interactions(post):
    return pick(post, "engagement", "interactions", "interactInfo", "interaction", default=post)


def engagement_score(post):
    i = get_interactions(post)
    likes = pick(i, "liked_count", "likeCount", "likes", "liked", default=0) or 0
    collects = pick(i, "collected_count", "collectCount", "collects", "favoriteCount", default=0) or 0
    comments = pick(i, "comments_count", "comment_count", "commentCount", "comments", default=0) or 0
    shares = pick(i, "shared_count", "share_count", "shareCount", "shares", default=0) or 0
    try:
        return float(likes) + float(collects) * 2 + float(comments) * 1.5 + float(shares) * 1.5
    except (TypeError, ValueError):
        return 0.0


def save_outputs(posts, prefix):
    posts_sorted = sorted(posts, key=engagement_score, reverse=True)

    json_path = f"{prefix}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(posts_sorted, f, ensure_ascii=False, indent=2)

    csv_path = f"{prefix}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["score", "title", "description", "hashtags", "likes",
                          "collects", "comments", "shares", "author", "url", "time"])
        for p in posts_sorted:
            i = get_interactions(p)
            t = pick(p, "timestamp", "time", "publishTime", "createdAt")
            date = ""
            if isinstance(t, (int, float)):
                try:
                    date = datetime.fromtimestamp(t / 1000 if t > 10**12 else t).isoformat()
                except (ValueError, OSError):
                    date = str(t)
            hashtags = pick(p, "hashtags", "tags", default=[])
            author = pick(p, "user", "author", default={})
            writer.writerow([
                round(engagement_score(p), 1),
                pick(p, "title", "displayTitle", default=""),
                (pick(p, "desc", "description", "content", "body", default="") or "").replace("\n", " "),
                ", ".join(hashtags) if isinstance(hashtags, list) else hashtags,
                pick(i, "liked_count", "likeCount", "likes", default=0),
                pick(i, "collected_count", "collectCount", "collects", default=0),
                pick(i, "comments_count", "comment_count", "commentCount", "comments", default=0),
                pick(i, "shared_count", "share_count", "shareCount", "shares", default=0),
                pick(author, "nickname", "nickName", default="") if isinstance(author, dict) else author,
                pick(p, "url", "postUrl", "noteUrl", default=""),
                date,
            ])
    print(f"Saved {len(posts_sorted)} posts -> {json_path}, {csv_path}")
    return posts_sorted


TIME_FILTER_DAYS = {"1d": 1, "1w": 7, "6mo": 180}


def filter_by_days(posts, days=7):
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    kept = []
    for p in posts:
        t = pick(p, "timestamp", "time", "publishTime", "createdAt")
        if not isinstance(t, (int, float)):
            kept.append(p)  # keep if timestamp unreadable
            continue
        ts = t / 1000 if t > 10**12 else t
        try:
            post_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            if post_dt >= cutoff:
                kept.append(p)
        except (ValueError, OSError):
            kept.append(p)
    return kept


def print_top(posts, n=10):
    print(f"\nTop {n} by engagement score:\n")
    for p in posts[:n]:
        i = get_interactions(p)
        title = pick(p, "title", "displayTitle", default="(no title)")
        likes = pick(i, "liked_count", "likeCount", "likes", default=0)
        collects = pick(i, "collected_count", "collectCount", "collects", default=0)
        comments = pick(i, "comments_count", "comment_count", "commentCount", "comments", default=0)
        url = pick(p, "url", "postUrl", "noteUrl", default="")
        print(f"[{round(engagement_score(p))}] {title}")
        print(f"    likes {likes} | collects {collects} | comments {comments}")
        print(f"    {url}\n")


if __name__ == "__main__":
    client = get_client()

    print(f"Searching RedNote for: {SEARCH_KEYWORDS} (maxResults={MAX_RESULTS_PER_KEYWORD}/keyword)...")
    run = run_search(client, SEARCH_KEYWORDS, MAX_RESULTS_PER_KEYWORD)
    dataset_id = get_dataset_id(run)
    if not dataset_id:
        raise SystemExit(f"Could not find a dataset id on the run result: {run!r}")
    items = list(client.dataset(dataset_id).iterate_items())
    print(f"Got {len(items)} raw items back.")
    days = TIME_FILTER_DAYS.get(TIME_FILTER)
    if days:
        items = filter_by_days(items, days=days)
        print(f"{len(items)} items after filtering to past {days} day(s).")

    if PRINT_RAW_SAMPLE and items:
        print("\n--- Raw sample of first result (check field names) ---")
        print(json.dumps(items[0], ensure_ascii=False, indent=2)[:2000])
        print("--- end sample ---\n")

    posts_sorted = save_outputs(items, "oriental_kopi_search")
    print_top(posts_sorted)
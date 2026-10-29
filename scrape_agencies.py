"""
RedNote agency/operator lead scraper -- Ipoh Town Kopitiam (Jewel Changi).

Runs the tiered keywords from rednote_search_terms.py through MediaCrawler
(github.com/NanmiCoder/MediaCrawler) and aggregates results into agencies.csv,
one row per author, ranked by score_profile().

Mirrors the MediaCrawler integration in scrape_oriental_kopi_rednote.py:
patches MediaCrawler's config, runs `main.py --platform xhs --lt cookie
--type search`, then reads the search_contents jsonl it writes.

Sort strategy (per config notes): operators post frequently with low
engagement, so Tiers 1-3 (and the English Tier 6) search 最新
(time_descending) to avoid burying them under viral tourist content;
Tiers 4-5 hunt viral food/Jewel posts, so they search 最热
(popularity_descending). SORT_TYPE is a single global in MediaCrawler, so
each sort order is a separate crawl; MediaCrawler already loops over every
comma-joined keyword within one crawl, so this is just 2 runs total.

NOTE on author identity: the current MediaCrawler ("教学版") anonymises users
-- it stores a SHA256 `creator_hash` instead of the raw user id, masks the
nickname (张***硕), and drops avatar/profile-link/signature. So leads are
grouped by creator_hash and the nickname column is masked; there is no
direct profile URL. `top_note_url` (openable via its xsec_token) is the way
back to a lead's content. If you point this at a fork that preserves raw
`user_id`/`nickname`, those are used instead.

Setup (same as scrape_oriental_kopi_rednote.py):
    git clone https://github.com/NanmiCoder/MediaCrawler MediaCrawler
    pip install -r MediaCrawler/requirements.txt
    playwright install chromium
    # .env: XHS_COOKIES=web_session=...; a1=...   (XHS_COOKIE also accepted)
"""

import os
import re
import csv
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

from rednote_search_terms import TIERS, BIO_SIGNALS, score_profile

load_dotenv()

MEDIACRAWLER_DIR = Path(__file__).parent / "MediaCrawler"
XHS_COOKIE = os.environ.get("XHS_COOKIES") or os.environ.get("XHS_COOKIE", "")

CRAWLER_MAX_NOTES_COUNT = 20   # per keyword; MediaCrawler floors this at 20
CRAWLER_MAX_SLEEP_SEC = 4      # sleep between pages; higher = less risk-control

# tiers -> MediaCrawler SORT_TYPE. Each entry is one crawl.
SORT_BATCHES = [
    ((1, 2, 3, 6), "time_descending"),        # 最新: operator/trade/group terms
    ((4, 5), "popularity_descending"),        # 最热: viral Jewel/food content
]

KEYWORD_TIER = {kw: n for n, terms in TIERS.items() for kw in terms}
ALL_TERMS = set(KEYWORD_TIER)

OUT_CSV = "agencies.csv"


# -- MediaCrawler integration (mirrors scrape_oriental_kopi_rednote.py) -------

OVERRIDE_BEGIN = "# === scrape_agencies overrides (auto-managed) ==="
OVERRIDE_END = "# === end scrape_agencies overrides ==="


def _mc_config_path():
    p = MEDIACRAWLER_DIR / "config" / "base_config.py"
    if not p.exists():
        raise SystemExit(
            f"MediaCrawler not found at {MEDIACRAWLER_DIR}.\n"
            "Run: git clone https://github.com/NanmiCoder/MediaCrawler MediaCrawler"
        )
    return p


def update_mediacrawler_config(keywords, cookie, sort_type):
    """Set our keywords/cookie/sort order by appending an override block to the
    end of base_config.py. Config values are plain module-level assignments and
    the last one wins, so this is robust to however the defaults are written
    (base_config star-imports xhs_config above this block, so SORT_TYPE lands
    here too). The block is re-written each call, so it stays idempotent."""
    base = _mc_config_path()
    text = base.read_text(encoding="utf-8")
    text = re.sub(re.escape(OVERRIDE_BEGIN) + r".*?" + re.escape(OVERRIDE_END) + r"\n?",
                  "", text, flags=re.DOTALL)

    kw = ",".join(keywords).replace('"', '\\"')
    ck = cookie.replace("\\", "\\\\").replace('"', '\\"')
    block = f"""
{OVERRIDE_BEGIN}
KEYWORDS = "{kw}"
LOGIN_TYPE = "cookie"
COOKIES = "{ck}"
CRAWLER_TYPE = "search"
ENABLE_CDP_MODE = False
HEADLESS = True
XHS_INTERNATIONAL = True
ENABLE_GET_COMMENTS = False
SAVE_DATA_OPTION = "jsonl"
CRAWLER_MAX_NOTES_COUNT = {CRAWLER_MAX_NOTES_COUNT}
CRAWLER_MAX_SLEEP_SEC = {CRAWLER_MAX_SLEEP_SEC}
SORT_TYPE = "{sort_type}"
{OVERRIDE_END}
"""
    base.write_text(text.rstrip("\n") + "\n" + block, encoding="utf-8")
    print(f"Configured MediaCrawler: {len(keywords)} keyword(s), sort={sort_type}")


def _python_exe():
    venv_python = Path(__file__).parent / "venv" / "bin" / "python3"
    return str(venv_python) if venv_python.exists() else sys.executable


def run_mediacrawler():
    """Run one crawl. Returns True on clean exit. A non-zero exit is NOT fatal:
    RedNote often kills the session mid-run (登录已过期) and MediaCrawler then
    crashes, but every note fetched before that is already on disk, so we warn
    and let the caller carry on to parse what was saved."""
    print("Running MediaCrawler... (may take a few min)")
    result = subprocess.run(
        [_python_exe(), "main.py", "--platform", "xhs", "--lt", "cookie", "--type", "search"],
        cwd=MEDIACRAWLER_DIR,
        text=True,
        timeout=1800,
    )
    if result.returncode != 0:
        print("  WARNING: MediaCrawler exited non-zero (likely session expired / "
              "risk-control). Keeping notes collected so far.")
        return False
    return True


def _read_jsonl_notes():
    """Every note row MediaCrawler has written so far (empty list if none)."""
    data_dir = MEDIACRAWLER_DIR / "data" / "xhs"
    notes = []
    for path in sorted(data_dir.glob("**/search_contents*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    notes.append(json.loads(line))
    return notes


def covered_keywords():
    """Tier keywords already present on disk, so a resumed run can skip them
    (RedNote kills the session after enough searches, so runs finish partial;
    re-running with a fresh cookie should crawl only what's still missing)."""
    return {n.get("source_keyword") for n in _read_jsonl_notes()} & ALL_TERMS


def load_search_notes():
    """Tier notes on disk (source_keyword in our terms), deduped by note_id."""
    notes = {}
    for note in _read_jsonl_notes():
        if note.get("source_keyword") in ALL_TERMS:
            notes.setdefault(note.get("note_id"), note)
    if not notes:
        raise SystemExit("No tier notes found on disk -- nothing crawled successfully.")
    return list(notes.values())


# -- Lead aggregation ---------------------------------------------------------

def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def note_date(note):
    t = note.get("time")
    if not isinstance(t, (int, float)) or t <= 0:
        return ""
    try:
        return datetime.fromtimestamp(t / 1000 if t > 10**12 else t).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return ""


def creator_key(note):
    """Anonymised MediaCrawler gives creator_hash; a fork may keep user_id."""
    user = note.get("user") or {}
    return note.get("creator_hash") or user.get("user_id") or note.get("user_id")


def creator_name(note):
    user = note.get("user") or {}
    return note.get("nickname") or user.get("nickname") or ""


def matched_signals(text, category):
    return sorted({kw for kw in BIO_SIGNALS[category] if kw in text})


def build_leads(notes):
    """Group notes by creator, score each creator's combined caption text."""
    authors = {}
    for note in notes:
        key = creator_key(note)
        if not key:
            continue
        a = authors.setdefault(key, {"notes": {}, "keywords": set()})
        a["notes"].setdefault(note.get("note_id"), note)
        if note.get("source_keyword"):
            a["keywords"].add(note["source_keyword"])

    leads = []
    for key, a in authors.items():
        notes_ = list(a["notes"].values())
        text = " ".join(f"{n.get('title') or ''} {n.get('desc') or ''}" for n in notes_)
        likes = [_int(n.get("liked_count")) for n in notes_]
        top_likes = max(likes, default=0)
        top_note = max(notes_, key=lambda n: _int(n.get("liked_count")))
        tiers = sorted({KEYWORD_TIER[kw] for kw in a["keywords"] if kw in KEYWORD_TIER})
        leads.append({
            "score": score_profile(text, followers=0, top_likes=top_likes),
            "nickname": creator_name(top_note),
            "creator_id": key,
            "tiers": ",".join(map(str, tiers)),
            "keywords": ", ".join(sorted(a["keywords"])),
            "n_posts": len(notes_),
            "top_likes": top_likes,
            "total_likes": sum(likes),
            "operator_signals": ", ".join(matched_signals(text, "operator_role")),
            "group_signals": ", ".join(matched_signals(text, "group_capability")),
            "contact_signals": ", ".join(matched_signals(text, "contact_route")),
            "commercial_signals": ", ".join(matched_signals(text, "commercial_intent")),
            "latest_post": max((note_date(n) for n in notes_), default=""),
            "top_note_title": (top_note.get("title") or "").replace("\n", " "),
            "top_note_url": top_note.get("note_url") or top_note.get("url", ""),
        })
    leads.sort(key=lambda r: (r["score"], r["top_likes"]), reverse=True)
    return leads


def save_csv(leads, path):
    if not leads:
        print("No leads to write.")
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(leads[0].keys()))
        writer.writeheader()
        writer.writerows(leads)
    print(f"Saved {len(leads)} leads -> {path}")


if __name__ == "__main__":
    if not XHS_COOKIE:
        raise SystemExit("Set XHS_COOKIES in .env first (see file header).")

    done = covered_keywords()
    if done:
        print(f"Resuming: {len(done)} keyword(s) already on disk will be skipped.")

    for tier_nums, sort_type in SORT_BATCHES:
        keywords = [kw for n in tier_nums for kw in TIERS[n] if kw not in done]
        if not keywords:
            print(f"\n=== Tiers {tier_nums}: all keywords already crawled, skipping ===")
            continue
        print(f"\n=== Tiers {tier_nums}: {len(keywords)} keywords, sort={sort_type} ===")
        update_mediacrawler_config(keywords, XHS_COOKIE, sort_type)
        run_mediacrawler()

    notes = load_search_notes()
    print(f"\nLoaded {len(notes)} unique tier notes from MediaCrawler output.")

    leads = build_leads(notes)
    save_csv(leads, OUT_CSV)

    print("\nTop 10 leads (2+ signal categories = strong lead):")
    for r in leads[:10]:
        print(f"[{r['score']:>3}] {r['nickname']}  tiers {r['tiers']}  "
              f"posts {r['n_posts']}  likes {r['top_likes']}")

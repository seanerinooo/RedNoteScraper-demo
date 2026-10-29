"""
RedNote competitor post analyzer + Telegram digest sender.

Takes the CSV output from scrape_oriental_kopi_rednote.py, runs the top N
posts (by engagement score, already sorted by the scraper) through Claude
using content_style_analysis_framework.md as the analysis framework, then
sends the results to Telegram: a short highlights message plus the full
structural breakdown as an attached file.

Setup:
    pip install -r requirements.txt
    Add to the .env file in this folder (same one used by scrape_oriental_kopi_rednote.py):
        ANTHROPIC_API_KEY=your_key          # console.anthropic.com
        TELEGRAM_BOT_TOKEN=your_bot_token   # from @BotFather
        TELEGRAM_CHAT_ID=your_chat_id

Getting your Telegram chat ID:
    1. Create a bot via @BotFather, get its token
    2. Send any message to your new bot
    3. Visit https://api.telegram.org/bot<TOKEN>/getUpdates in a browser
    4. Find "chat":{"id": ...} in the response -- that's your chat_id

Usage:
    python analyze_and_send.py oriental_kopi_search.csv
    python analyze_and_send.py oriental_kopi_search.csv --top-n 20

Chaining with the scraper (e.g. in a weekly cron entry):
    python scrape_oriental_kopi_rednote.py && \
    python analyze_and_send.py oriental_kopi_search.csv
"""

import os
import csv
import argparse
from datetime import datetime
from pathlib import Path

import requests
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

FRAMEWORK_PATH = Path(__file__).parent / "content_style_analysis_framework.md"
MODEL = "claude-sonnet-4-6"
DEFAULT_TOP_N = 15
DIGEST_HIGHLIGHT_COUNT = 5


def load_posts(csv_path, top_n):
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # CSV is already sorted by score desc by the scraper, but sort
    # defensively in case the file was edited or merged from elsewhere
    rows.sort(key=lambda r: float(r.get("score", 0) or 0), reverse=True)
    return rows[:top_n]


def format_posts_for_prompt(posts):
    blocks = []
    for i, p in enumerate(posts, 1):
        blocks.append(
            f"### Post {i} (engagement score: {p.get('score')})\n"
            f"Title: {p.get('title')}\n"
            f"Description: {p.get('description')}\n"
            f"Hashtags: {p.get('hashtags')}\n"
            f"Likes: {p.get('likes')} | Collects: {p.get('collects')} | "
            f"Comments: {p.get('comments')} | Shares: {p.get('shares')}\n"
            f"Author: {p.get('author')} | URL: {p.get('url')}\n"
        )
    return "\n".join(blocks)


def run_analysis(posts, framework_text, client):
    system_prompt = (
        "You are analyzing competitor social media posts for ipohtown.asia, "
        "a kopitiam/Nanyang cafe brand benchmarking against Oriental Kopi. "
        "Apply the following analysis framework to EACH post provided below. "
        "Most content will be in Chinese -- translate it into English as "
        "part of your analysis, don't just transliterate. Be concise: "
        "roughly 4-8 lines covering all sections per post, not an essay.\n\n"
        "Use EXACTLY this markdown format for each post:\n\n"
        "## Post N: [Title]\n\n"
        "| Hook | Keypoints | Psychology | Ad-disguise | Virality |\n"
        "|:----:|:---------:|:----------:|:-----------:|:--------:|\n"
        "| X/5  |    X/5    |    X/5     |     X/5     |   X/5    |\n\n"
        "**Hook:** one sentence\n\n"
        "**Key points:** one sentence\n\n"
        "**Selling point:** one sentence\n\n"
        "**Psychology:** one sentence\n\n"
        "**Why it doesn't read as an ad:** one sentence\n\n"
        "**Virality triggers:** one sentence\n\n"
        "> **Template lesson for ipohtown.asia:** one sentence action.\n\n"
        "---\n\n"
        "End with a '## Pattern Summary' section containing a markdown table of cross-post patterns.\n\n"
        f"{framework_text}"
    )
    posts_block = format_posts_for_prompt(posts)
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": f"Analyze these {len(posts)} posts:\n\n{posts_block}",
        }],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def build_digest(posts):
    n = min(DIGEST_HIGHLIGHT_COUNT, len(posts))
    lines = [
        f"*RedNote Competitor Digest -- {datetime.now().strftime('%d %b %Y')}*",
        f"\nAnalyzed top {len(posts)} posts. Top {n} by engagement score:\n",
    ]
    for i, p in enumerate(posts[:n], 1):
        lines.append(f"{i}. {p.get('title') or '(no title)'} -- score {p.get('score')}")
        lines.append(f"   {p.get('url')}")
    lines.append("\nFull breakdown attached below.")
    return "\n".join(lines)


def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
    if not resp.ok:
        # Markdown parse errors are common if a title contains stray
        # asterisks/underscores -- fall back to plain text rather than fail
        resp = requests.post(url, data={"chat_id": chat_id, "text": text})
    resp.raise_for_status()


def send_telegram_document(token, chat_id, file_path, caption=""):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with open(file_path, "rb") as f:
        resp = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"document": f},
        )
    resp.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="Path to scraper CSV output")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N,
                         help=f"How many top posts to analyze (default {DEFAULT_TOP_N})")
    parser.add_argument("--out", default=None, help="Path to save the full analysis markdown")
    args = parser.parse_args()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not all([anthropic_key, tg_token, tg_chat_id]):
        raise SystemExit(
            "Set ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, and TELEGRAM_CHAT_ID env vars first."
        )

    if not FRAMEWORK_PATH.exists():
        raise SystemExit(
            f"Framework file not found at {FRAMEWORK_PATH} -- keep it in the same "
            "folder as this script, or edit FRAMEWORK_PATH."
        )
    framework_text = FRAMEWORK_PATH.read_text(encoding="utf-8")

    posts = load_posts(args.csv_path, args.top_n)
    if not posts:
        raise SystemExit(f"No posts found in {args.csv_path}.")

    print(f"Analyzing top {len(posts)} posts with Claude...")
    client = Anthropic(api_key=anthropic_key)
    analysis_text = run_analysis(posts, framework_text, client)

    out_path = args.out or f"analysis_{datetime.now().strftime('%Y%m%d')}.md"
    Path(out_path).write_text(analysis_text, encoding="utf-8")
    print(f"Full analysis saved -> {out_path}")

    digest = build_digest(posts)
    print("Sending digest to Telegram...")
    send_telegram_message(tg_token, tg_chat_id, digest)
    send_telegram_document(tg_token, tg_chat_id, out_path, caption="Full competitor analysis")
    send_telegram_document(tg_token, tg_chat_id, args.csv_path, caption="Raw post data (CSV)")
    print("Done.")


if __name__ == "__main__":
    main()
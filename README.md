# RedNote Market Research Tool

Python scrapers that find tour agency leads and track competitor engagement on RedNote (Xiaohongshu), with a local dashboard to start scrapes, follow their progress live and explore the results.

**[Live demo](https://YOUR-USERNAME.github.io/YOUR-REPO/)** (sample data; runs are simulated)

![Dashboard demo](docs/demo.gif)

## What it does

- **Agency lead finder** (`scrape_agencies.py`): searches tiered Chinese keywords through [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler), groups notes by creator and scores each creator for outreach. Points come from operator words (地陪, 包车, 旅行社), group capability (研学, 团建, 大巴), a contact route (微信, WhatsApp, 私信) and commercial intent (报价, 接单, 余位).
- **Competitor tracker** (`scrape_oriental_kopi_rednote.py`): pulls a competitor's posts through an Apify actor and ranks them by engagement score: likes + 2 × saves + 1.5 × comments + 1.5 × shares.
- **Content analysis** (`analyze_and_send.py`): runs the top posts through Claude with a content-style framework and sends a digest to Telegram.
- **Dashboard** (`dashboard/`): a zero-dependency Python server and a single-page UI. Start either scraper from the page, watch its log stream in a loading screen, stop it, then explore score distributions, the most common signal words, engagement per post and sortable, searchable tables.

## Run it locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add your Apify token and RedNote cookie

# The agency scraper also needs MediaCrawler next to it:
git clone https://github.com/NanmiCoder/MediaCrawler MediaCrawler
pip install -r MediaCrawler/requirements.txt
playwright install chromium

python dashboard/server.py      # then open http://127.0.0.1:8765
```

The server only listens on your machine, runs one scraper at a time and refuses requests from other websites.

## Demo mode

Opened anywhere other than the local server (or with `?demo` in the address), the dashboard loads made-up data from `dashboard/demo-data.js` and simulates runs. Nothing is scraped. The demo searches one term, **kopitiam**: it shows kopitiam food creators scored as collaboration leads (food-creator words, kopitiam focus, a contact route, openness to collabs) and the most engaging kopitiam posts. A language switch shows the results in English (the default) or in the original Chinese. Regenerate the sample data with `python dashboard/make_demo_data.py`. The GitHub Actions workflow in `.github/workflows/pages.yml` publishes the demo to GitHub Pages.

## Built with

Python · Apify · Playwright (via MediaCrawler) · Claude API · vanilla JS and SVG charts

## Notes

For market research on public posts. MediaCrawler is a separate project with its own non-commercial license; it is not included here. Scraping is subject to RedNote's terms, so keep volumes low.

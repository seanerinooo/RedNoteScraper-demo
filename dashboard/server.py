"""
Local dashboard for the RedNote scrapers.

Serves dashboard/index.html, the latest scraper CSVs as JSON, and lets the
page start a scraper and follow its output while it runs.

Run (from the RedNote folder, with the venv so the scrapers find their deps):
    venv/bin/python dashboard/server.py
then open http://127.0.0.1:8765

Only listens on 127.0.0.1. One scraper runs at a time.
"""

import ast
import csv
import importlib
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HOST, PORT = "127.0.0.1", int(os.environ.get("DASHBOARD_PORT", "8765"))

JOBS = {
    "agencies": {
        "label": "Agency leads",
        "script": "scrape_agencies.py",
    },
    "kopi": {
        "label": "Competitor posts",
        "script": "scrape_oriental_kopi_rednote.py",
    },
}

# scrape_agencies.py writes agencies.csv; older runs were saved as agencies2.csv.
LEAD_FILES = ["agencies.csv", "agencies2.csv"]
POST_FILE = "oriental_kopi_search.csv"
# Search terms each successful run actually used, so the page can show them
# beside the results even after the scripts' settings change.
LAST_SEARCH = HERE / "last_search.json"

TIER_NAMES = {1: "Operator identity", 2: "Trade and agency", 3: "Group types",
              4: "Jewel and Changi", 5: "Food and kopitiam", 6: "English"}


def script_constants(script, names):
    """Read top-level literal settings from a scraper without importing it."""
    found = {}
    for node in ast.parse((ROOT / script).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in names:
                try:
                    found[name] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    return found


def agency_search_config():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    terms = importlib.reload(importlib.import_module("rednote_search_terms"))
    batches = script_constants(JOBS["agencies"]["script"], {"SORT_BATCHES"}).get("SORT_BATCHES", [])
    sort_of = {n: sort for tiers, sort in batches for n in tiers}
    return {"tiers": [{"tier": n, "name": TIER_NAMES.get(n, f"Tier {n}"), "sort": sort_of.get(n),
                       "keywords": list(kws)} for n, kws in sorted(terms.TIERS.items()) if n in sort_of]}


def post_search_config():
    c = script_constants(JOBS["kopi"]["script"],
                         {"SEARCH_KEYWORDS", "MAX_RESULTS_PER_KEYWORD", "SORT_TYPE", "NOTE_TYPE", "TIME_FILTER"})
    return {"keywords": c.get("SEARCH_KEYWORDS", []), "max_results": c.get("MAX_RESULTS_PER_KEYWORD"),
            "sort": c.get("SORT_TYPE"), "note_type": c.get("NOTE_TYPE"), "time_filter": c.get("TIME_FILTER")}


SEARCH_CONFIG = {"agencies": agency_search_config, "kopi": post_search_config}


def read_last_search():
    try:
        return json.loads(LAST_SEARCH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class Runner:
    """Holds the one scraper process that may be running and its output."""

    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.job = None
        self.started = None
        self.finished = None
        self.returncode = None
        self.stopped = False
        self.log = deque(maxlen=400)
        self.search = None

    def start(self, job):
        with self.lock:
            if self.proc and self.proc.poll() is None:
                return False, f"{JOBS[self.job]['label']} is already running."
            try:
                self.search = SEARCH_CONFIG[job]()
            except Exception:
                self.search = None
            env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
            self.proc = subprocess.Popen(
                [sys.executable, "-u", JOBS[job]["script"]],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=True,
            )
            self.job = job
            self.started = time.time()
            self.finished = None
            self.returncode = None
            self.stopped = False
            self.log.clear()
            threading.Thread(target=self._pump, args=(self.proc,), daemon=True).start()
            return True, None

    def _pump(self, proc):
        for line in proc.stdout:
            self.log.append(line.rstrip("\n"))
        proc.wait()
        with self.lock:
            if proc is self.proc:
                self.returncode = proc.returncode
                self.finished = time.time()
                if proc.returncode == 0 and self.search is not None:
                    saved = read_last_search()
                    saved[self.job] = dict(self.search, ran_at=datetime.fromtimestamp(self.finished).isoformat(timespec="seconds"))
                    LAST_SEARCH.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")

    def stop(self):
        with self.lock:
            if not self.proc or self.proc.poll() is not None:
                return False
            self.stopped = True
            try:
                # The agency scraper starts MediaCrawler as a child; stop the whole group.
                os.killpg(self.proc.pid, 15)
            except ProcessLookupError:
                pass
            return True

    def status(self):
        with self.lock:
            running = bool(self.proc and self.proc.poll() is None)
            return {
                "running": running,
                "job": self.job,
                "label": JOBS[self.job]["label"] if self.job else None,
                "started": self.started,
                "finished": self.finished,
                "returncode": self.returncode,
                "stopped": self.stopped,
                "now": time.time(),
                "log": list(self.log),
            }


RUNNER = Runner()


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def file_info(path):
    return {
        "name": path.name,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
    }


def load_data():
    out = {"leads": [], "leads_file": None, "posts": [], "posts_file": None}
    lead_paths = [ROOT / n for n in LEAD_FILES if (ROOT / n).exists()]
    if lead_paths:
        newest = max(lead_paths, key=lambda p: p.stat().st_mtime)
        out["leads"], out["leads_file"] = read_csv(newest), file_info(newest)
    post_path = ROOT / POST_FILE
    if post_path.exists():
        out["posts"], out["posts_file"] = read_csv(post_path), file_info(post_path)
    out["search"] = {"agencies": search_for("agencies", agency_search_config, lead_paths and newest),
                     "posts": search_for("kopi", post_search_config, post_path if post_path.exists() else None)}
    return out


def search_for(job, current, results_path):
    """The terms behind the results file: the run that wrote it if we recorded one,
    otherwise the script's current settings, flagged as possibly different."""
    run = read_last_search().get(job)
    if run and results_path and datetime.fromisoformat(run["ran_at"]).timestamp() >= results_path.stat().st_mtime - 5:
        return dict(run, source="run")
    try:
        return dict(current(), source="config")
    except Exception as e:
        return {"source": "error", "error": str(e)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _same_origin(self):
        # Refuse requests started by other websites open in the browser.
        origin = self.headers.get("Origin")
        allowed = {f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"}
        return self.headers.get("X-Dashboard") == "1" and (origin is None or origin in allowed)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/demo-data.js":
            self._send(200, (HERE / "demo-data.js").read_bytes(), "text/javascript; charset=utf-8")
        elif path == "/api/data":
            try:
                self._send(200, load_data())
            except Exception as e:  # a half-written CSV mid-run, for example
                self._send(500, {"error": f"Could not read the scraper output: {e}"})
        elif path == "/api/status":
            self._send(200, RUNNER.status())
        else:
            self._send(404, {"error": "Not found"})

    def do_POST(self):
        if not self._same_origin():
            self._send(403, {"error": "Requests must come from the dashboard page."})
            return
        if self.path.startswith("/api/run/"):
            job = self.path.rsplit("/", 1)[-1]
            if job not in JOBS:
                self._send(404, {"error": f"Unknown scraper: {job}"})
                return
            ok, err = RUNNER.start(job)
            self._send(200 if ok else 409, RUNNER.status() if ok else {"error": err})
        elif self.path == "/api/stop":
            RUNNER.stop()
            self._send(200, RUNNER.status())
        else:
            self._send(404, {"error": "Not found"})


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"RedNote dashboard: http://{HOST}:{PORT}  (Ctrl+C to quit)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        RUNNER.stop()

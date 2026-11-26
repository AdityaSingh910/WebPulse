# WebPulse: complete walkthrough

**Audience:** you, presenting and defending WebPulse in the final-year viva.
**Contents:** how to operate every feature, how to demonstrate it, and how it works inside, with real source
references, real logs and real measurements.
**Facts as of:** 26 Nov 2026 (commit `613c77b7`, Phase 12). Everything marked ✅ was tested in this project. Anything
not tested says so.

WebPulse is a modified and simplified version of the open-source **changedetection.io** (v0.70.4, Apache-2.0).
Section 10 lists which parts are inherited and which are WebPulse's own.

**Contents**
1. [Start, stop and the screen layout](#1-start-stop-and-the-screen-layout)
2. [Architecture in one page](#2-architecture-in-one-page)
3. [Website monitoring](#3-website-monitoring)
4. [Product price and stock monitoring](#4-product-price-and-stock-monitoring)
5. [Job listing monitoring](#5-job-listing-monitoring)
6. [Notifications (Email, Telegram, history)](#6-notifications-email-telegram-history)
7. [Web scraping: static and dynamic](#7-web-scraping-static-and-dynamic)
8. [Backend and system design](#8-backend-and-system-design)
9. [Storage, REST API, backup and restore](#9-storage-rest-api-backup-and-restore)
10. [Security and reliability](#10-security-and-reliability)
11. [Controlled demonstration script](#11-controlled-demonstration-script)
12. [10-minute presentation plan](#12-10-minute-presentation-plan)
13. [Viva quick answers](#13-viva-quick-answers)
14. [Final checklist](#14-final-checklist)

**Two kinds of data, never mixed up**

| | Real websites | Controlled demonstration |
|---|---|---|
| What | Wikipedia, Hacker News, Decathlon, Sleepy Owl, boAt, HackerRank, Meesho, python.org, Quotes/Books to Scrape | WebPulse's own small demo site on this computer (`*.webpulse-demo.test`) |
| How to recognise it | Normal titles; groups "Indian shops (live)", "Job listings", "… (live)" | Title starts with `[Demo]`, an orange **Demo** chip, group "Demo site (simulated)" |
| Changes happen | When the real website changes. You cannot trigger them | When you press a button on **Controlled demo** |
| History | Only what WebPulse really recorded | Recorded the same way, but the changes were made on purpose |

---

## 1. Start, stop and the screen layout

```powershell
cd C:\Users\adity\OneDrive\Desktop\Solo_College_Project\changedetection.io
.\run.ps1
```

`run.ps1` starts three processes, each listening on 127.0.0.1 only:

| Process | Address | Purpose |
|---|---|---|
| Headless Microsoft Edge | 127.0.0.1:9222 (CDP) | for pages built with JavaScript |
| Demo site | 127.0.0.1:8199 | `e2e/fixture_server.py`, used by the Controlled demo |
| WebPulse | **http://127.0.0.1:5000** | the application |

It also sets the environment:

| Variable | Value | Effect |
|---|---|---|
| `LISTEN_HOST` | 127.0.0.1 | WebPulse is not reachable from other machines |
| `FETCH_WORKERS` | 3 | three concurrent workers |
| `REQUESTS_RETRY_MAX_COUNT` | 2 | at most 2 retries after a network error |
| `WEBPULSE_DEMO_SITE` | http://127.0.0.1:8199 | switches on the Controlled demo page |

It never sets `ALLOW_IANA_RESTRICTED_ADDRESSES`, so SSRF protection stays on.

* **Keep the PowerShell window open.** Its log lines are the "backend logs" quoted in this document; a copy is also
  written to `%TEMP%\webpulse-run.log`. **Ctrl+C** stops all three processes. Closing the window with ✕ leaves the
  demo site running.
* **Keep the laptop plugged in, with sleep set to "Never".** A sleeping laptop freezes WebPulse; see section 10.5.

**Data folder:** `C:\Users\adity\cdio-data\webpulse-demo`.

**Screen layout**

| Area | Contents |
|---|---|
| Sidebar | Home · Websites · Products · Job listings · Notifications · Controlled demo · Settings |
| Top bar | **Monitoring/Paused** (pause the scheduler) · **Alerts on/Muted** · search · dark mode |
| Home | an add form (Watch website / Track product / Track jobs / More options), six use-case cards, a Controlled demonstration strip, and a "Behind the scenes" row (Scheduler, Workers and queue, Page reading, REST API, Saved data) |
| Settings | General (interval, versions kept, password) and **More tools** (Notifications, Groups, Import, Check queue and workers, Backups, Add by pointing, Delete all history). **Show technical settings** reveals the remaining tabs |

---

## 2. Architecture in one page

```
Browser (Jinja2 HTML + small JS, Socket.IO client)
   │  HTTP form posts / GET pages (CSRF-protected)          ▲ live row updates (Socket.IO)
   ▼                                                        │
Flask app  changedetectionio/flask_app.py  (+ blueprints in changedetectionio/blueprint/*)
   │   home · watchlist · ui(edit/diff/preview/queue/views) · settings(+notifications) · demo_lab · backups · tags · imports
   │   REST API  /api/v1/*  (api/, flask_restful, x-api-key)
   │
   ├─ datastore  store/__init__.py  ── in-memory dict  data['watching'][uuid] = Watch(...)
   │                                    persisted as JSON + files under <data folder>/<uuid>/
   │
   ├─ scheduler thread  ticker_thread_check_time_launch_checks()  (every 1 s)
   │        └─ due watches ──► RecheckPriorityQueue (binary min-heap, queue_handlers.py)
   │                                      ▲ manual "Check now" / API recheck push priority 1
   │
   ├─ 3 worker threads (worker_pool.py), each with its own asyncio loop ── async_update_worker() (worker.py)
   │        claim uuid ─► SSRF gate ─► fetcher (requests | Playwright→Edge)
   │        ─► processor (text_json_diff | restock_diff) ─► MD5 compare
   │        ─► save version (Brotli) ─► queue notification ─► release uuid
   │
   └─ notification thread  notification_runner()  ── Apprise ─► Email (SMTP) / Telegram / webhook
                                                     └─ notification-history.jsonl (masked)
```

**The life of one check:**
1. The scheduler or a click pushes a `PrioritizedItem` onto the heap.
2. A worker pops it, claims the UUID, checks the URL is not private (SSRF), and downloads the page.
3. It converts the page to text (or extracts the price), applies filters, and computes the MD5.
4. If the MD5 differs, it saves a compressed version, queues an alert, and tells the browser via Socket.IO.

---

## 3. Website monitoring

### 3.1 Add a real website ✅ (done in Feature 1 with Wikipedia)

| | |
|---|---|
| Purpose | Be told when any public web page changes |
| Page | **Home** |
| Input | `https://en.wikipedia.org/wiki/Main_Page` |
| Click | **Watch website** |
| Expect | Redirect to **Websites**; within a couple of seconds the row shows "Wikipedia, the free encyclopedia" and a recent "Checked" time |
| Verify | The row has no error. **View page** shows the page text |

Real log (26 Nov 11:55, 0.96 s from click to stored version):

```
store:add_watch:867             Adding URL 'https://en.wikipedia.org/wiki/Main_Page' - c11ad97d-…
model:commit:711                Committed watch c11ad97d-… to c11ad97d-…/watch.json
"POST /form/add/quickwatch HTTP/1.1" 302
worker_pool:claim_uuid_for_processing   Worker 2 claimed UUID: c11ad97d-…
worker:async_update_worker:173  Worker 2 processing watch UUID c11ad97d-… Priority 1 URL https://en.wikipedia.org/wiki/Main_Page
validate_url:is_private_hostname  Hostname 'en.wikipedia.org' is NOT private/IANA restricted.
content_fetchers                Content fetcher 'html_requests' (Read the page directly …)
text_json_diff.processor:666    Previous MD5: e8579edb…, Fetched MD5 e8579edb…
model.Watch:_brotli_save        Finished brotli compression - From 38148 to 8643 bytes.
model.Watch:_brotli_save        Finished brotli compression - From 261388 to 46647 bytes.
worker:614                      Worker 2 completed watch c11ad97d-… in 1.38s
```

**Code path:**

| Step | Code |
|---|---|
| The Home form posts `processor=text_json_diff` | `blueprint/home/templates/home.html` |
| The route checks CSRF and the URL, then adds the watch | `blueprint/ui/views.py:92` `form_quick_watch_add()` → `store/__init__.py:732` `add_watch()`: `uuid4`, in-memory dict, atomic `watch.json` |
| The first check is queued | `PrioritizedItem(priority=1)` (views.py:159), then a 302 redirect |
| The worker downloads the page and decides whether it changed | `worker.py:48`; `processors/base.py:194` `call_browser()`; `processors/text_json_diff/processor.py:494` `run_changedetection()` |
| The version is saved | `model/Watch.py:797` `save_history_blob()` |

On the first check both MD5s are the same because the code sets `previous_md5 = fetched` when there is none
(processor.py, the `if not watch.get('previous_md5')` branch). The worker saves a first version anyway, because
`history_n` is 0 (`worker.py:472`).

**Presentation:** add the URL with the backend window beside the browser. Point at "Priority 1", "NOT private" and
"From 38148 to 8643 bytes".

### 3.2 Automatic and manual checks ✅

* **Automatic.** Every website has an interval. Settings → General "Check every" is the default (3 hours); a
  website's own interval is set in Edit → General. You set Wikipedia to 1 hour.
* **Manual.** **Check now** on a row, or **Check all now** on the list, queues at priority 1 and jumps the queue.
* **Verify.** Your manual check of Wikipedia at 12:04:43 logged `Previous MD5: e8579edb…, Fetched MD5: e8579edb…`.
  The text was unchanged, so no version was saved and nothing was flagged: no false alarm.
* **Scheduler log line** (real, from the morning of 26 Nov):
  `flask_app:ticker_thread_check_time_launch_checks:1974 - > Queued watch UUID … Checked at 1795609513 queued at 1795669878.31 priority 1795669878`.
  The priority is the current Unix time.
* **Measured.** A 10 s interval produced checks exactly 10 s apart (gaps 10, 10, 10, 10). A manual check finished
  in 0.3–0.7 s while all three workers were busy.

### 3.3 Detecting added, removed and modified content ✅ (real: Hacker News)

| | |
|---|---|
| Page | **Websites** → Hacker News – front page headlines → **View changes** |
| Expect | Green lines = new headlines, red = headlines gone; a "changed → changed into" pair for a replaced line |
| Real data | Hacker News has 5 genuine versions: 25 Nov 16:13 and 22:13, 26 Nov 04:13, 10:41 and 11:56 |

**Algorithm** (`diff/__init__.py`):
1. `render_diff()` (line 424) splits both versions into lines.
2. `customSequenceMatcher()` (line 309) runs Python's `difflib.SequenceMatcher`. This is Ratcliff/Obershelp: find
   the longest common block of lines, then recurse on the parts to the left and right.
3. `get_opcodes()` returns `equal`, `insert`, `delete` and `replace`.

The real opcodes between the 10:48 and 11:56 versions of Hacker News (30 lines each, 27 shared):

```
equal    old[ 0: 3] new[ 0: 3]
replace  old[ 3: 4] new[ 3: 4] | "The Great Automatic Grammatizator…" → "Lions' Commentary on Unix…"
insert   old[ 5: 5] new[ 5: 6] | Minipg: PostgreSQL as a Single Executable
delete   old[ 8: 9] new[11:11] | Slow Ubuntu security response times
insert   old[ 7: 7] new[ 8:10] | Slow Ubuntu security response times / The Great Automatic Grammatizator…
```

**How each opcode is shown** (lines 385–422):

| Opcode | Shown as |
|---|---|
| `equal` | skipped, so unchanged content does not appear (tick **Same/non-changed** on the change page to show it) |
| `delete` | `@removed_PLACEMARKER…` |
| `insert` | `@added_PLACEMARKER…` |
| `replace` | `@changed…` followed by `@changed_into…`. In "Words" mode, a single changed line is compared **word by word** with `diff_match_patch` (`render_inline_word_diff`, line 79) |

**Rendering:**
* `processors/text_json_diff/difference.py:104` `render()` calls `render_diff()`.
* `notification/handler.py:84` `apply_html_color_to_body()` turns the markers into inline-styled `<span>`s: red
  `#fadad7/#b30000`, green `#eaf2c2/#406619`. Inline styles are used because the same function colours email, and
  Gmail strips `<style>`.
* The page escapes all text first and then un-escapes only its own spans (`blueprint/ui/diff.py:25`
  `diff_unescape_difference_spans`). This is XSS protection.

**Limitation: moves are not detected.** A headline that moved down the page shows as red at its old place and
green at its new place.

**Presentation:** open Hacker News → View changes. Point at one green and one red line, then at a headline that
appears in both colours: "a moved story is a delete plus an insert".

### 3.4 History and comparing any two versions ✅

* **Page:** View changes. The two version selectors at the top choose "from" and "to"; the options bar below
  offers **Words / Lines**, **Same/non-changed** (also show unchanged lines) and **Ignore Whitespace**.
* **Storage:** `<uuid>/history.txt`, one line per version (`timestamp,file`). For example Hacker News:
  `1795603424,0a882f18….txt` … `1795674399,41e259a9….txt`.
* **API:** `GET /api/v1/watch/<uuid>/history`, then `GET /api/v1/watch/<uuid>/difference/<from>/<to>`. Both were
  tested; see 9.4.

### 3.5 CSS selectors, XPath and keyword filtering ✅ (tested on live Hacker News, 26 Nov)

| Stage | Lines kept |
|---|---|
| whole Hacker News page | 64 |
| `.titleline > a` (headline links only) | 30 |
| + `/.*\b(?:AI\|LLM\|security\|Linux\|Python\|open source)(?:s\|es\|ing)?\b.*/i` | 4 |

**Practical steps:**
1. Go to **Websites** → **Edit** on a website → **Show technical options** → **Page section & filters**.
2. In **"Only watch this part of the page"**, type `.titleline > a` (CSS). An XPath such as
   `//span[@class="titleline"]/a` also works. JSONPath (`json:$.jobs[*].title`) is for JSON APIs.
3. Click **Activate preview** to see the filtered text live.
4. In **Extract text**, enter the `/…/i` rule above, then **Save**.

**Important detail** (`processors/text_json_diff/processor.py:186` `extract_by_regex`):
* a plain keyword like `AI` returns **only the matched word**, even inside other words ("tr**ai**ns");
* a `/…/` regex with `.*` on both sides returns the whole line.

This is why "Track jobs" builds `/.*\b(?:words)(?:s|es|ing|ship|ships)?\b.*/i` (`blueprint/ui/views.py`
`job_keywords_rule()`). The `\b` word boundaries stop "intern" matching "Internal Audit".

**Real lesson from your own watch `acdb1a8a`:** it has the keyword rule but no CSS selector, so the kept lines still
include rank numbers ("10. Slow Ubuntu security…") and the footer line "… | Security | …". It recorded 3 "changes"
in 6 minutes just because stories moved rank. Adding `.titleline > a` removes that noise.

**Filter pipeline order** (`processor.py`):
1. CSS/XPath include filters (`apply_include_filters`, line 350, via `html_tools.include_filters`, line 277:
   BeautifulSoup `select()`; XPath through lxml/elementpath).
2. HTML → text with **inscriptis** (`html_tools.html_to_text`).
3. Ignore rules (`strip_ignore_text`).
4. Extract-text rules.
5. MD5 of what remains.

Because the MD5 is computed **after** filtering, changes outside the selected part never count.

---

## 4. Product price and stock monitoring

### 4.1 Track a real Indian product ✅

| | |
|---|---|
| Page | **Home** |
| Input | e.g. `https://www.decathlon.in/p/8189216/men-mountain-hiking-warm-fleece-gilet-jacket-black` (already watched) |
| Click | **Track product** |
| Expect | **Products** list row with ₹ price and an In stock / Out of stock badge |

**Real results** (re-verified 26 Nov ~11:56, all without errors):

| Product | Price | Stock | Read by | Interval |
|---|---|---|---|---|
| Decathlon India – Forclaz 200 men's hiking gilet | ₹799 | in stock | plain HTTP, 1.32 s | 12 h |
| same Decathlon product | ₹799 | in stock | real browser (Edge), 10.43 s | 24 h |
| Sleepy Owl Coffee – enamel mug | ₹564 | **out of stock** (the shop's own JSON-LD says `OutOfStock`) | plain HTTP | 24 h |
| boAt Stone 650 | ₹1,999 | out of stock (per the shop's data) | plain HTTP | 24 h |

Each product currently has one saved version, because nothing has changed yet. Real price changes appear only when
the shop changes its price; leave WebPulse running.

Real log for the Decathlon check:

```
worker:173  Worker 1 processing watch UUID e267257d-… Priority 1 URL https://www.decathlon.in/p/8189216/…
processors.restock_diff.processor:469  restock - raw document checksum last='e0b41ee1…' current='e157f7a3…'
processors.restock_diff.processor:697  Comparing NEW price '799.0' against previous check's price '799.0' -> price unchanged
worker:614  Worker 1 completed watch e267257d-… in 1.32s
```

**How the name, price, currency and stock are found** (`processors/restock_diff/processor.py`):
1. `extract_itemprop_availability_safe()` (line 206) first tries a fast pure-Python pass over the data shops publish
   for search engines: **JSON-LD** (`<script type="application/ld+json">` with `"@type":"Product"`, `offers.price`,
   `priceCurrency`, `availability`), **microdata** (`itemprop="price"`) and **Open Graph** (`og:price:amount`).
2. If that is incomplete, it uses **extruct** (line 247), which on Linux runs in a subprocess to isolate memory.
3. `get_itemprop_availability()` (line 318) normalises the result: `https://schema.org/OutOfStock` → in_stock False.
4. If a page lists several different prices (product variants), it raises `MoreThanOnePriceFound`. Then you add a
   CSS selector for the price element (Edit → Page section & filters), which `_price_from_user_filters` (line 414)
   uses.

The product name is the page `<title>` / `og:title` ("Page <title> is …" in the log). The saved version is a small
text line, e.g. `In Stock: True - Price: 799.0`, which `_parse_restock_snapshot()` reads back for charts.

### 4.2 Price increases and decreases, with percentages ✅ (controlled demo; real when shops change)

* **Rule** (processor.py:690–725): with **Follow price changes** on, a new price differs from the previous one →
  change. Optional limits are in Edit → **Price & stock** tab:
  * "Below price to trigger notification" / "Above price to trigger notification";
  * "Threshold (%) for price changes since the previous check" (ignore small changes).
* **Percentage:** `processors/restock_diff/__init__.py:77` `get_price_change_percent()` =
  `round((price − last_price) / last_price × 100, 1)`. Verified: 999 → 849 gives **−15.0 %**, 2999 → 2549 gives
  **−15.0 %**. Shown as a green ▼ / red ▲ in the lists and on the Home card.
* **Demonstrate:** Controlled demo → **Drop the price** (section 11).

### 4.3 Out of stock and back in stock ✅ (controlled demo; real for Sleepy Owl and boAt if they restock)

* **Setting:** Edit → **Price & stock** → "Re-stock detection":

  | Option | When it counts as a change |
  |---|---|
  | **In Stock only** (default for a product added from Home) | only when it goes out of stock → in stock |
  | **Any availability changes** | both directions. Used by the real Indian products and the demo product (`demo/setup_presentation.py`) |
  | **Off** | stock is ignored |

  Code: processor.py:637–688.
* **Real opportunity:** Sleepy Owl and boAt are currently out of stock. If either restocks before your
  presentation, WebPulse records a genuine restock with its date and time.

### 4.4 Historical price chart and statistics ✅

* **Page:** **Products** → row → **Price history** (once there are 2+ versions).
* **Expect:** a price/stock chart, a table, and statistics (now, lowest, highest, average, "cheaper than N %").
* **Code:** `processors/restock_diff/difference.py:51` `_build_series()` reads every version, and line 67
  `compute_price_summary()` computes count, min, max, mean, median and quartiles (`statistics.quantiles`,
  inclusive), the "cheaper than" share and the low/typical/high status.
* **Verified against a hand calculation** for `[2999, 2549, 2549, 2999, 1999]`: mean 2619, p25 2549, median 2549,
  p75 2999, cheaper-than 80 %, status low, all-time low ✓.
* **Limitation:** each saved version counts once, and versions are saved only when something changes. The average
  is therefore "average over price changes", not weighted by how long each price lasted.
* **Also:** **XLSX export** of the price history (tested, E10).

---

## 5. Job listing monitoring

Job monitoring is a dedicated **structured monitor** (Phase 13), comparable to the product price monitor. WebPulse
reads each opening (title, company, location, type, team and its own job link), remembers it by its job link, and
reports openings that are **new, removed or changed**. It does not show page-text differences.

### 5.1 Real careers pages ✅ (first structured read on 26 Nov, 15:59)

| Source | URL | How it is read | Openings on the page → kept by keywords |
|---|---|---|---|
| Hevo Data (Lever) | `https://jobs.lever.co/hevodata` | Lever job board | 42 → **18** (e.g. "SDE II · Bangalore, India · Full time · On-site · Backend") |
| Meesho (Lever) | `https://jobs.lever.co/meesho` | Lever job board | 49 → **10** |
| HackerRank (Greenhouse) | `https://job-boards.greenhouse.io/hackerrank` | Greenhouse job board | 32 → **17** (e.g. "DevOps Engineer II · Hybrid in Bangalore, India · Engineering") |
| Python.org job board | `https://www.python.org/jobs/` | Page section `.list-recent-jobs h2 a` | 22 → 22 (no keywords; each job has its own company) |

Checked every 6–12 h; robots.txt allows each page. Lever's robots.txt adds `Content-Signal: use=reference` (no AI
training), which this personal monitoring respects. That first read is the **starting point**: those openings are
recorded but not counted as "new". Real new, removed or changed openings appear as the companies update their boards.

**The Hevo problem, fixed.** The Hevo watch showed the whole page even though `.posting-title` was set. The cause was
**not** the selector: replaying the stored page through the real filter code gave 42 postings and then 18 technical
roles. The real cause was the **Trigger text** field ("Keyword triggers - Trigger/wait for text"), which contained
`engineer, developer, intern, data, software` as **one line**. A trigger line must appear exactly on the page, and
that sentence never does. `RuleEngine.evaluate_trigger_text()` therefore blocked every check, so no new version was
ever saved, and the only version stayed the first one, which was taken before the selector was set (the full page).
The job monitor does not use trigger text (keywords go in "Only track jobs mentioning…"), and the line was removed
from the Hevo watch (a backup was made first).

### 5.2 Try it

1. **Sidebar → Job listings.**
   * **Expect:** one card per careers page showing *active / new / removed / changed* counts, plus totals and the
     period switch (7 days / 30 days / since monitoring started).
2. Click **Openings** on Hevo Data.
   * **Expect:** a table with title (and team), location, type, **First detected**, **Last seen** and **Apply**
     (opens the job on Lever).
   * The filters **All / New / Active / Removed / Modified** show only those openings.
   * A **New** badge marks openings first seen after monitoring started.
   * Removed openings are struck through and keep the date they disappeared.
3. Scroll down to **Active openings over time**: a step chart (hover a point for the counts). Below it are
   **Additions and removals per day** (the table view) and the **Job history**, which lists what changed at each
   check by job title, not raw text.
4. **Only track jobs mentioning…** shows the keywords in plain words. To change them, type
   `engineer, data, intern` and press **Save**.
   * **Expect:** a new starting point, with no alert and no "new" or "removed" jobs. A filter edit is not a job
     change.
5. **Add one yourself:**
   1. **Home** → paste `https://jobs.lever.co/<company>` or `https://job-boards.greenhouse.io/<company>`.
   2. **More options**: leave the page section empty (Lever and Greenhouse are recognised automatically) and enter
      the keywords.
   3. Click **Track jobs**. You land on that company's Openings page.
6. **Text versions** (on the Openings page) still shows the raw text versions for anyone who wants them.

### 5.3 How it works

```
scheduler → queue → worker → fetcher (plain HTTP or Edge, SSRF check, proxy)       [inherited, unchanged]
        → processors/job_listings/processor.py  run_changedetection()            [WebPulse]
             extract.extract_jobs(html, url, selectors)   → openings
             extract.keyword_matcher(extract_text rules)  → only matching titles
             tracker.apply_check(state, openings, …)      → added / removed / modified, jobs.json
        → worker saves a version (one sorted line per opening) and sends the alert   [inherited]
```

* **Extraction** (`extract.py`), first match wins:
  1. Lever (`div.posting[data-qa-posting-id]`);
  2. Greenhouse (`.job-post a` / `div.opening`);
  3. your page section (CSS or XPath; each match is a job card, a job link, or a list of jobs);
  4. schema.org `JobPosting` (JSON-LD);
  5. automatic: job-like links outside the navigation and footer.

  For Lever and Greenhouse, a selector only narrows the result to the openings inside it.
* **Identity:** the canonical job URL (absolute, no `#fragment`, tracking parameters such as `utm_*` removed, job-id
  parameters such as `gh_jid` kept). Without a link: a hash of title + location. So:
  * reordering is not a change;
  * the same link twice counts once;
  * two openings with the same title in different cities stay two (Hevo's two "Solution Engineer (Post-sales)").
* **Comparison** (`tracker.py`) works on sets of ids:
  * new = id not active before;
  * removed = active before but missing now;
  * modified = same id with a different title, company, location, type or team (the old → new values are stored);
  * a removed opening that comes back is new again and keeps its first-detected date.
* **Baseline:** the first successful read. Changing the selector or keywords starts a new baseline: openings that no
  longer match are forgotten, not "removed". That version is saved without an alert (a one-line hook in
  `worker.py`).
* **Failures never remove jobs:**
  * a failed fetch never reaches the processor;
  * a page section that matches nothing, or a page with no openings at all (blocked page, bot check, redesign), is
    recorded as the watch's error and the stored openings are kept;
  * the exception is a **confirmed empty board**: only an explicit signal from the board counts, namely Lever's
    `.no-postings-message` ("No job postings currently open"), Greenhouse's count header "0 jobs", or a "no open
    positions" message inside the selected page section. Then the openings are removed and the reason is shown on
    the Openings page;
  * a sudden drop to 20 % or less of the openings (from at least 10) must be seen on **two checks in a row** before
    the missing openings are marked as removed.
* **Storage:** `jobs.json` in the watch's folder, written atomically:
  * every opening with `first_seen`, `added_at`, `last_seen`, `status`, `removed_at`, `modified_at` and its last 20
    field changes;
  * one `events` entry per check that changed something, which feeds the history, the chart and the per-day table.

  It is bounded: 1,000 events and 1,500 removed openings. The version text is one sorted line per active opening
  (`Title · Location · Type · Team  URL`), so notifications show "+ new opening" / "- removed opening" lines with the
  apply link.
* **Pages:** `blueprint/jobs` (`/jobs/`, `/jobs/<uuid>`, keywords, check now). On a job watch, "View changes" opens the
  Openings page; `?raw=1` gives the text diff.
* **Tests:**
  * `tests/unit/test_job_listings.py`: 21 tests covering Lever, Greenhouse, generic, JSON-LD, automatic mode,
    duplicates, canonical URLs, keywords, baseline, new/removed/modified, reordering, re-baseline, the sudden-drop
    confirmation, re-opened jobs, the New window and persistence;
  * e2e **J01–J17** (the real Track jobs form, the demo careers page, alerts, reordering, duplicates, a temporary
    failure, keyword re-baseline), **P06–P07** (after a restart) and **U32** (in the browser).

### 5.4 Converting existing careers pages

The watches created before Phase 13 were switched from `text_json_diff` to `job_listings` with WebPulse stopped,
after a backup (`C:\Users\adity\cdio-data\webpulse-demo-backup-before-jobs-20261126-155914`).
`demo\setup_presentation.py` now does the same for any careers page in the "Job listings" group.

Upstream keeps a separate version index per processor (`history.txt` for text, `history-job_listings.txt` for jobs),
so the old text versions stay on disk but are not shown while the watch is a job monitor. Switching the processor
back shows them again.

---

## 6. Notifications (Email, Telegram, history)

**Status on 26 Nov:**
* Email and Telegram are **not configured yet**.
* URL building, masking and turning channels off are tested ✅ (U31).
* Webhook delivery is tested ✅ (U15, C18).
* **Real Email/Telegram delivery has not been tested.** Only you can do that, with your own credentials.

### 6.1 Email (Gmail) — you do this

1. Google account → **Security** → turn on **2-Step Verification**.
2. Open **myaccount.google.com/apppasswords**, name it "WebPulse", **Create**, and copy the 16 letters.
3. WebPulse → **Notifications** → **Email**:
   * **Your email address:** your Gmail;
   * **App password:** the 16 letters;
   * **Send alerts to:** empty (yourself).
4. Click **Save and send test**. Expect a pop-up "Saved. A test email was sent…".
5. **Verify:**
   * the email arrives (check spam too);
   * **Notification history** shows "Test · Email · Delivered to the service".

Outlook/Hotmail, Yahoo and Zoho also work. For another provider, open "Use a different mail server".

### 6.2 Telegram — you do this

1. In Telegram, open **@BotFather** (blue tick), send `/newbot`, and copy the token.
2. Open your new bot, press **Start**, and send "hi".
3. WebPulse → **Notifications** → **Telegram**: paste the token, click **Find my chat ID**, then **Save and send
   test**.
4. **Verify:** the message arrives on your phone, and a history row reads "Telegram · Delivered".

### 6.3 Alerts for real events

Once Email/Telegram is set up, every saved change of a website that isn't muted sends an alert. Wording: "WebPulse:
{{watch_title}} changed", with the coloured difference and a link to the change page.

| Event | How to trigger it on demand |
|---|---|
| Website change | Controlled demo → **Change the page text** |
| Price drop | **Drop the price** |
| Out of stock / restock | **Sell out** / **Restock** |
| New job | **Publish a new job** |
| Ignored job (no alert) | **Publish a non-technical job** |

Real websites send alerts when they really change (Hacker News is muted on purpose, because it changes many times
an hour).

### 6.4 How it works

| Step | Code |
|---|---|
| Change found | `worker.py:511` → `send_content_changed_notification()` → `notification_service.py:509`: picks the senders (watch → group → system settings, `notification_senders()` line 79), builds the message tokens, `notification_q.put()` |
| Sending | `flask_app.py` `notification_runner()` (thread) → `notification/handler.py:333` `process_notification()` → **Apprise**: one Apprise instance per URL; it captures Apprise's log and treats a warning or error as a failure |
| Simple settings | `notification/simple_setup.py` (WebPulse) turns the form into Apprise URLs (`mailtos://user:app-password@gmail.com/?to=…`, `tgram://token/chatid`); `blueprint/settings/notifications/__init__.py` |
| History | `notification/history.py` (WebPulse) appends one masked JSON line per attempt to `notification-history.jsonl` (keeps 500). Destinations are masked; error text keeps only WARNING/ERROR lines, with passwords and bot tokens replaced by `****` |

**Failure handling:** a failed send is recorded as "Failed" with the reason ("Why?"). The website shows "Notification
error detected", and checks continue. "Delivered to the service" means Gmail or Telegram **accepted** the message;
the inbox or phone is the final proof.

### 6.5 Credential security

* The password and bot token are never sent back to the page: the field shows "Saved – leave empty to keep it"
  (tested, U31).
* They never appear in logs (checked on the live log on 26 Nov).
* **Limitation:** like upstream, they are stored **unencrypted** in `changedetection.json`, protected only by your
  Windows account's file permissions. **Turn off** deletes them. To revoke: delete the app password at Google, or
  send `/revoke` to BotFather.

---

## 7. Web scraping: static and dynamic

### 7.1 Static scraping with Requests ✅

* `content_fetchers/requests.py` (`html_requests`) downloads with the Python `requests` library:
  * Brotli/gzip decoding;
  * a 45 s timeout;
  * a manual redirect loop that re-checks each hop for SSRF.

  It is fast (Decathlon 1.32 s) and needs no browser.
* It works when the content is in the HTML the server sends: Wikipedia, Hacker News, Decathlon, Sleepy Owl, boAt
  and the job boards.

### 7.2 Dynamic scraping with Playwright and Microsoft Edge ✅

* **Code:** `content_fetchers/playwright.py` (`html_webdriver`):
  * `connect_over_cdp()` to the headless Edge that run.ps1 started (port 9222);
  * `new_context()`, `new_page()`, navigate, an optional wait;
  * `page.evaluate()` collects element positions (visual selector) and stock hints;
  * `page.content()` returns the **rendered** HTML;
  * a full-page screenshot.
* **Choose it:** Edit → Show technical options → **Page reading** → "Open the page in a real browser", or the
  checkbox under More options on Home.

**Real evidence: Quotes to Scrape, a page made for scraping practice, `https://quotes.toscrape.com/js/`:**

| Watch | Saved text | Contains the quotes? |
|---|---|---|
| "…JavaScript page via plain HTTP (static)" | **105 bytes**: only "Quotes to Scrape · Login · Next →" | no: the quotes are added by JavaScript |
| "…JavaScript-rendered page" (Edge) | **1,667 bytes**: "“The world as we have created it…” by Albert Einstein …" | yes |

**Presentation:** open **View page** on both Quotes watches side by side.

**Cost:** the same Decathlon page took **10.43 s** in Edge versus 1.32 s plain. Use the browser only where needed.

### 7.3 HTML parsing ✅

`html_tools.html_to_text()` uses **inscriptis**, which keeps the layout (lists and line breaks), so a diff is
line-based. Filters use BeautifulSoup `select()` (CSS) and lxml/elementpath (XPath). JSON responses are filtered with
JSONPath.

### 7.4 Why it is free, and when it fails

* **Free:** WebPulse is ordinary HTTP plus the Edge that ships with Windows, with no paid scraping API or proxy
  service. Apprise and SMTP/Telegram are free.
* **It fails when:**

  | Situation | What happens |
  |---|---|
  | The site blocks bots: a "verify you are human" page or CAPTCHA (boAt showed one after several quick requests) | WebPulse does **not** bypass it; the check records an error and the next scheduled check retries |
  | A login is required | The page cannot be read |
  | robots.txt or the site's terms forbid it | Not used, by choice (Amazon.in and Flipkart were not used) |
  | The layout changes | A CSS selector stops matching ("Alert me if that part of the page can no longer be found") |
  | Several prices on one page | `MoreThanOnePriceFound` → add a price selector |

* **Timeouts and retries:** 45 s per request, plus at most **2 retries** (run.ps1). Measured with a 5 s timeout:
  * DNS failure 2.0 s;
  * connection refused 8.1 s;
  * slow site 16.2 s;
  * with the upstream default of 6 retries: 31–67 s.

---

## 8. Backend and system design

### 8.1 Flask application and blueprints

* **Start-up:**
  1. `changedetection.py` → `changedetectionio/__init__.py` `main()` parses `-d` (data folder) and `-p` (port).
  2. It builds the datastore, then `flask_app.changedetection_app()` creates the Flask app.
  3. That app registers the blueprints, starts the scheduler thread, the worker pool and the notification runner,
     and initialises Socket.IO.
* **Blueprints** (`blueprint/`):

  | Blueprint | Pages |
  |---|---|
  | `home` (WebPulse) | `/` |
  | `watchlist` | `/watches/` |
  | `ui` | edit, diff, preview, queue, quick-add views |
  | `settings` + `settings/notifications` (WebPulse page) | settings and notifications |
  | `demo_lab` (WebPulse) | `/demo/` |
  | `backups` (+ `restore`) | backups |
  | `tags` | groups |
  | `imports` | import |
  | `browser_steps`, `conditions`, `price_data_follower` | browser steps, conditions, price data |

* **Templates:** Jinja2. `templates/base.html` is the WebPulse shell (sidebar, top bar). Styles come from
  `static/styles/scss/webpulse.scss`, compiled to `webpulse.css` with sass.

### 8.2 Frontend ↔ backend communication

* **Forms:** HTML forms POST with a CSRF token. The server redirects back, and the result appears as a toast
  (`static/js/flask-toast-bridge.js`). Errors stay on the page.
* **Live updates:** **Socket.IO** (`realtime/socket_server.py`, threading mode). Workers send signals (blinker) →
  `handle_watch_update()` emits `watch_update` to the room of each website (`watch_room()`), so a row updates
  without a reload. If no browser is connected, the handler skips the work.
* **AJAX:** a few spots (test notification on the advanced page, the edit-page preview).

### 8.3 Scheduler ✅

`flask_app.py:1783` `ticker_thread_check_time_launch_checks()` runs once a second in its own thread. For every
watch that is not paused or already queued:
* it computes `seconds_since_last_recheck`;
* it adds the optional jitter;
* it respects time-window schedules (`is_within_schedule`);
* if due (≥ the interval and ≥ `MINIMUM_SECONDS_RECHECK_TIME`, 3 s), it pushes
  `PrioritizedItem(priority=int(time.time()))`.

"Monitoring/Paused" in the top bar sets `all_paused`, and the scheduler then queues nothing. Manual checks still
work.

### 8.4 Priority queue = binary min-heap ✅

* `queue_handlers.py` `RecheckPriorityQueue` keeps a list ordered with **`heapq`**: `heappush` (line 82),
  `heappop` (line 162), each O(log n). It is guarded by a `threading.Lock`, plus a second `queue.Queue` used only to
  wake waiting workers.
* `queuedWatchMetaData.PrioritizedItem` is a `@dataclass(order=True)` compared only on `priority`.
* Manual checks use 1, scheduled ones use the Unix time (~1.8 billion), so a manual check always comes out first.
  Scheduled checks come out oldest-due first.
* Measured: a manual check finished in 0.3–0.7 s while all 3 workers were busy.

### 8.5 Threads and asyncio ✅

* `worker_pool.py`: each worker is a **`threading.Thread`** running its own **asyncio event loop**
  (`asyncio.new_event_loop()`, line 56).
* `worker.py:48` `async_update_worker()` awaits the queue, the fetch (Playwright is async) and processing. Blocking
  CPU work, `run_changedetection`, runs in an executor (`loop.run_in_executor`, line 220) so the loop stays
  responsive.
* A worker restarts itself after 10 jobs or 1 hour (`WORKER_MAX_JOBS`, `WORKER_MAX_RUNTIME`) to release memory.
  You can see "Worker 0 restarting after …" in the log.

### 8.6 Thread safety and race conditions ✅

* `worker_pool.py:285` `claim_uuid_for_processing()`, under `_uuid_processing_lock`, adds the UUID to
  `currently_processing_uuids` only if no worker has it, so **two workers never check the same website at once**.
  `release_uuid_from_processing()` removes it in a `finally`.
* The scheduler skips watches that are already queued (`queued_uuids`).
* The datastore has a lock, and every JSON write is **atomic**: a temporary file, then a rename.
* A queued item records `scheduled_at`; if the watch was already checked after that time, the worker drops the stale
  item (`worker.py:110`).
* Measured: slow sites only delay others while all workers are busy (5 quick pages waited ~4.3 s behind three 4 s
  pages).

### 8.7 MD5 hashing and change detection ✅

* `processors/text_json_diff/processor.py:487`: `hashlib.md5(text.encode('utf-8')).hexdigest()` of the **filtered**
  text. A changed or not-changed decision is one 32-character comparison with `previous_md5`.
* A second MD5 of the **raw download** (`last-checksum.txt`, `processors/base.py:71`) lets an identical download skip
  processing altogether.
* MD5 is used as a fast **fingerprint**, not for security; a collision would at worst miss one change.

### 8.8 Line-level and word-level diff ✅

See 3.3. **Lines:** `difflib.SequenceMatcher` (Ratcliff/Obershelp, roughly O(n²) worst case, fast in practice).
**Words:** `diff_match_patch` (Myers' O(ND) algorithm) inside a single replaced line, with a tokenizer that keeps
HTML tags whole (`diff/tokenizers`). Toggle **Words/Lines** on the change page.

### 8.9 Socket.IO real-time updates ✅

Covered in 8.2. You can see "Socket.IO: Client connected" in the log when a page opens. The queue page and the
"Checking now" counter in the sidebar update live.

---

## 9. Storage, REST API, backup and restore

### 9.1 JSON datastore and UUID folders ✅

```
C:\Users\adity\cdio-data\webpulse-demo\
  changedetection.json          settings (interval, notification URLs, API key, …)
  notification-history.jsonl    WebPulse notification history (masked)
  proxies.json                  the demo-site proxy
  <tag-uuid>\tag.json           groups
  <watch-uuid>\watch.json       one website's settings and state
  <watch-uuid>\history.txt      version index (history-restock_diff.txt for products)
  <watch-uuid>\<md5>.txt[.br]   versions (text)   ·  <timestamp>.html.br  last raw HTML
  <watch-uuid>\last-checksum.txt, last-screenshot.png (browser watches), elements.deflate (visual selector)
```

A UUID (`uuid4`) gives every website a unique, collision-free folder name.

### 9.2 Snapshots and Brotli compression ✅

`model/Watch.py:797` `save_history_blob()`:
* text over 20 KB (`BROTLI_COMPRESS_SIZE_THRESHOLD`, `SNAPSHOT_BROTLI_COMPRESSION_THRESHOLD`) is saved with
  **Brotli** (`MODE_TEXT`). Real: Wikipedia text 38,148 → 8,643 bytes (−77 %);
* raw HTML is always Brotli-compressed: 261,388 → 46,647 bytes (−82 %);
* small versions (Hacker News, ~1.5 KB) stay plain `.txt`;
* old versions beyond "Page versions to keep per website" are deleted.

### 9.3 Persistence after a restart ✅

The datastore is just files, so stopping (Ctrl+C) and starting `run.ps1` again reloads everything. Measured on a
throw-away instance: 21 of 21 watches kept their version count, and the price state was unchanged. Your real history
from 25 Nov is still there after several restarts.

**Presentation:** note a product's price and version count, press Ctrl+C, run `.\run.ps1`, and show the same data.

### 9.4 REST API ✅

* **Authentication:** header `x-api-key: <key>`. Settings → **REST API** tab → **Reveal** / **Copy**. The key is
  compared with `hmac.compare_digest` (`api/auth.py`), which takes constant time.
* **Endpoints** (`flask_app.py:983–1041`):

  | Endpoint | Purpose |
  |---|---|
  | `/api/v1/watch` (list, create) | list or add websites |
  | `/watch/<uuid>` | read; `?recheck=1`, pause, mute; PUT and DELETE |
  | `/watch/<uuid>/history`, `/history/<timestamp>` | the versions |
  | `/watch/<uuid>/difference/<from>/<to>` | the difference between two versions |
  | `/watch/<uuid>/favicon` | the site's icon |
  | `/systeminfo` | workers, paused, muted, processors |
  | `/search?q=` | add `&partial=true` for substring matching |
  | `/tags`, `/tag`, `/tag/<uuid>`, `/import`, `/changes`, `/notifications`, `/full-spec` | groups, import, changes, notifications, the full API spec |

  Requests are validated against `docs/api-spec.yaml` (OpenAPI).

* **Real calls on 26 Nov:**

```powershell
$key = '<paste from Settings → REST API>'
Invoke-RestMethod http://127.0.0.1:5000/api/v1/systeminfo -Headers @{'x-api-key'=$key}
#  → fetch_workers 3, all_paused false, base_url http://127.0.0.1:5000 …
Invoke-RestMethod http://127.0.0.1:5000/api/v1/watch/e1e203a9-41f4-4685-bb25-9f10e57e44fe/history -Headers @{'x-api-key'=$key}
#  → { "1795603424": "…0a882f18….txt", … }   (Hacker News, 5 versions)
Invoke-RestMethod "http://127.0.0.1:5000/api/v1/search?q=decathlon&partial=true" -Headers @{'x-api-key'=$key}
#  → 2 matches  (without partial=true: exact match only → {} )
Invoke-WebRequest http://127.0.0.1:5000/api/v1/watch          # no key → 403
```

### 9.5 Backup and restore ✅ (tested 26 Nov on throw-away instances)

* **Backup:** Settings → More tools → **Backups** → **Create backup**. The zip is built in a background thread,
  listed, and can be downloaded. Tested: 37.7 KB, 23 files (`.json`, `.txt`, `.br`).
* **Restore:** Backups page → **Restore** tab. Upload the zip and choose whether to include groups and websites and
  whether to replace existing ones of the same UUID. Restore brings back websites and groups only; it does **not**
  override the main application settings. Tested into an **empty** instance: same website UUID, 2/2 versions with
  identical timestamps, and the price state (849, previously 999, out of stock) restored.
* **Code:** `blueprint/backups/__init__.py` (request-backup, download) and `blueprint/backups/restore.py`.

---

## 10. Security and reliability

### 10.1 SSRF protection ✅

`validate_url.is_fetch_url_allowed()` → `is_private_hostname()` resolves the host and refuses if **any** address is
private, loopback, link-local, CGNAT or reserved. It runs **at fetch time**, so DNS-rebinding tricks fail too, and
every redirect hop is re-checked.

Tested on the live instance (26 Nov): these four were refused with "Fetch blocked: … resolves to a private/reserved
IP":
* `http://127.0.0.1:5000/api/v1/watch`;
* `http://169.254.169.254/latest/meta-data/` (cloud metadata);
* `http://10.0.0.1/`;
* `http://localhost:8199/state.json`.

`file:///C:/Windows/win.ini` is refused when added. E2E S06–S08 cover the same.

The demo site is reached only through its named proxy and **never forwards** (U34: it answers metadata-IP and
WebPulse-API requests with its own 404 and refuses HTTPS tunnels). It is never used as an automatic default proxy.

### 10.2 CSRF ✅

Flask-WTF `CSRFProtect` (`flask_app.py:225`) and `SameSite=Lax` cookies. POSTs without a token get 400 (tested live
on `/demo/action` and `/settings/notifications/`; E2E S04, E22).

### 10.3 XSS ✅

* Jinja2 auto-escapes all output.
* The change page escapes everything and then re-allows only its own colour spans (3.3).
* Notification values are HTML-escaped before rendering HTML emails (`notification/handler.py`).
* The demo site escapes its output.

### 10.4 Authentication and credentials ✅

* **Optional password:** Settings → General. It is stored as PBKDF2-SHA256 with a random salt
  (`flask_app.py:786`) and compared in constant time (tested: S01–S03, U25).
* **API key:** a separate key, compared in constant time.
* **Notification secrets:** see 6.5. They are stored unencrypted, the same as upstream.
* **Network exposure:** everything listens on 127.0.0.1 only (checked with `netstat`).

### 10.5 Network failures, timeouts, retries and sleep ✅

* **Failures** (DNS, refused, timeout, 404) are stored as the website's error and shown in red in the list; the app
  keeps running (measured).
* **Retries:** 2 (set in run.ps1; upstream defaults to 6). **Timeout:** 45 s.
* **Laptop sleep:** checks of ~444 s on 26 Nov were the laptop sleeping mid-request (Windows Kernel-Power: sleep
  10:41:20, resume 10:48:41). That is not a bug. Overdue checks run after waking.

### 10.6 Automated tests ✅

| Suite | Result (26 Nov) | What it covers |
|---|---|---|
| `e2e\run_e2e.ps1 -Browser -UI` | **118/118** | 60 core API/UI checks (incl. 20 structured job checks J01–J20), 7 persistence, 8 security (SSRF, password, CSRF), 8 browser (Playwright + Edge), 35 UI tests clicking the real interface |
| `e2e\run_unit.ps1` | 457 passed, 0 new failures | the upstream unit tests + 25 WebPulse job-monitor tests |
| | 8 known Windows failures | 4 need admin rights or Developer Mode for symlinks; 1 is a Linux-only SSRF exception the test assumes; 2 are outdated upstream tests; 1 needs `fork()` (pytest-flask live server). Details in `e2e/known_windows_unit_failures.txt` |
| | templates 37/37, imports 52/52 | |

### 10.7 Known limitations

* Moves in a list show as delete + insert (3.3).
* Price statistics are per change, not time-weighted (4.4).
* Bot checks and CAPTCHAs are not bypassed. Login-only pages cannot be read.
* Real Email/Telegram delivery depends on your credentials and is not yet verified.
* Notification secrets are stored unencrypted on disk.
* A sleeping laptop pauses monitoring.
* Upstream's Linux-only integration tests (`tests/*.py`) cannot run on Windows; `e2e/` replaces them.
* jq filters are unavailable on Windows (no wheel); CSS, XPath and JSONPath work.
* Job monitoring reads the openings the page itself lists. Boards that load jobs only with JavaScript need the
  browser fetch method. A board with zero openings is accepted only when it says so explicitly (Lever, Greenhouse,
  or a "no open positions" message in the selected section); a custom page without such a message shows an error
  instead. Keywords match the job **title** only.
* Custom SMTP logs in with the part of the address before the @. Gmail, Outlook, Yahoo and Zoho are configured
  automatically.

---

## 11. Controlled demonstration script

**Page:** sidebar → **Controlled demo**. Everything here changes only WebPulse's own demo site on this computer.

| Step | Click | Expect within ~5 s (the page refreshes itself) | Alert (if Email/Telegram set up) |
|---|---|---|---|
| 1 | **Drop the price** | Demo shop price ₹2,999 → ₹2,549 (−15 %); "What WebPulse has seen" shows the new price | "[Demo] Wireless earbuds changed", with the price diff |
| 2 | **Raise the price** | the price rises ~12 % | yes |
| 3 | **Sell out**, then **Restock** | an Out of stock badge, then In stock | yes, both: the demo product uses "Any availability changes" |
| 4 | **Publish a new job** | **Openings** (button under "What WebPulse has seen"): the job with a **New** badge, "+1 new" in the history | yes |
| 5 | **Change a job** | the same opening is **Modified**: location "Bengaluru" → "Hybrid, Bengaluru" (same job link, so not removed + added) | yes |
| 6 | **Remove a job** | **Removed** filter: struck through, with the time it disappeared | yes |
| 7 | **Publish a non-technical job** | "Office Administrator" appears on the demo page but nothing changes in WebPulse | **no**: the keyword filter worked |
| 7b | **Reorder the jobs** | the same jobs in a different order: no change, no new version | **no**: openings are compared by their job link |
| 7c | **Block the careers page**, then **Unblock** | a "verify you are human" page: the watch shows an error and **every opening is kept**; after Unblock the error clears with no change | no |
| 8 | **Change the page text** | the news text changes; **View changes** shows red/green | yes |
| 9 | **Reset the demo site** | the demo site returns to its start; WebPulse's history is kept | no (nothing is checked) |

**Backend log to point at:**
`Worker N processing watch UUID … Priority 1 URL http://shop.webpulse-demo.test/product.html`, then
`Comparing NEW price '2549.0' against previous check's price '2999.0'`, then a `Change detected …` line, then the
notification lines.

**How it works:**
* `blueprint/demo_lab/__init__.py` (WebPulse) posts to the demo site's `/set` and then queues priority-1 checks of
  the matching `[Demo]` watches.
* It is enabled only when `WEBPULSE_DEMO_SITE` is exactly `http://127.0.0.1:<port>`.
* The demo watches use `*.webpulse-demo.test` addresses through the "WebPulse demo site" proxy, so SSRF protection
  stays on.

Tested by U33 (price drop detected) and by driving the page in a browser.

---

## 12. 10-minute presentation plan

1. **Home (1 min).** The six use cases, "Behind the scenes", and the backend window beside the browser.
2. **Real website (2 min).** Hacker News → View changes: genuine changes with timestamps. Explain the MD5 →
   SequenceMatcher → red/green steps. Wikipedia: changes captured automatically by the 1-hour interval.
3. **Real products (1.5 min).** Products: Decathlon ₹799 (plain vs browser), Sleepy Owl out of stock (the shop's
   own data). Any genuine price or stock change collected by then.
4. **Real jobs (1 min).** Job listings: one card per company with active/new/removed/changed counts. Open Hevo Data:
   18 technical openings with location, type, first detected and an Apply link; the chart and job history below.
5. **Controlled demo, live (2.5 min).** Drop the price → alert on the phone. Publish a new job → alert. Publish a
   non-technical job → no alert.
6. **Notification history and security (1 min).** History rows; password and token never shown; SSRF; localhost
   only.
7. **Static vs dynamic (0.5 min).** The two Quotes to Scrape watches: 105 bytes vs 1,667 bytes.
8. **Persistence (0.5 min).** Ctrl+C, `.\run.ps1`, everything still there.

**If the internet fails:** the Controlled demo still works (alerts need the internet), and all recorded history can
still be shown.

---

## 13. Viva quick answers

* **Why MD5?** A fast fixed-size fingerprint: "changed?" becomes one string comparison. Not used for security.
* **Why compare text and not HTML?** HTML has noise (scripts, IDs, ads). The text after filters is what a person
  sees.
* **Why a heap?** O(log n) insert and remove, and a manual check (priority 1) always comes out before the scheduled
  ones (Unix-time priorities).
* **Why threads plus asyncio?** Each worker thread handles one site at a time. asyncio lets the Playwright fetch and
  queue waits proceed without blocking, and CPU work goes to an executor.
* **How are races prevented?** A UUID claim under a lock, already-queued checks, atomic file writes, and dropping
  stale queue items.
* **Why Brotli?** Better compression for text than gzip (77–82 % saved here), fast to decompress for diffs.
* **Why JSON files and not a database?** One user, small data, easy backup (zip), no server. That is upstream's
  design. Limitation: not for many concurrent users.
* **How do you avoid SSRF?** The address is resolved and checked at fetch time, every redirect hop is checked, and
  `file://` is refused.
* **Is the scraping legal and polite?** robots.txt is allowed for every page used, checks are 6–24 h apart, there
  are no logins, and bot checks and CAPTCHAs are not bypassed. Amazon.in and Flipkart were excluded.
* **What did you build vs inherit?** See the table below.

### What is inherited and what is WebPulse's own

| Inherited from changedetection.io (Apache-2.0) | WebPulse (this project) |
|---|---|
| Datastore, Watch model, Brotli snapshots | Removal of LLM/MCP, PWA, RSS output, image diff, Selenium/Puppeteer (Phases 2–7) |
| Scheduler thread, priority queue, async workers, UUID claims | WebPulse UI: shell, sidebar, Home use-case dashboard, design system, technical-settings toggle, plain labels |
| Fetchers (requests, Playwright) and the SSRF gate | Notifications page (Email/Telegram, `simple_setup.py`) and the persistent masked notification history (`history.py`) |
| `text_json_diff` and `restock_diff` processors, filters, MD5, the diff engine | Structured job monitor: the `job_listings` processor (`extract.py`, `tracker.py`), the Job listings and Openings pages, the Track jobs form and keyword rule |
| Price extraction (JSON-LD, microdata, OG, extruct) and price statistics | Controlled demo page (`demo_lab`) and the hardened demo site |
| Apprise notifications, REST API, backups/restore, CSRF, password hashing, Socket.IO | `run.ps1` single start, the retry setting, the demo-proxy safety fix, the preview-500 and link fixes, the e2e harness (96 checks), the presentation tooling, and the documentation |

Every changed file is listed in `CHANGES.md`. Modified files carry a notice header. `LICENSE` is unchanged, and
`NOTICE` has an addendum.

---

## 14. Final checklist

Legend: ✅ yes · ⚠️ partly or needs a condition · ❌ no · — not applicable

| Feature | Implemented | Tested | Works with real websites | Needs controlled demo to show on demand | Needs your credentials | Known limitation |
|---|---|---|---|---|---|---|
| Add and monitor a website | ✅ | ✅ (U03, C01–C05, live Wikipedia) | ✅ Wikipedia, Hacker News | — | — | — |
| Automatic and manual checks | ✅ | ✅ (E14, measured 10 s gaps, priority) | ✅ | — | — | Sleep pauses checks |
| Added/removed/modified detection | ✅ | ✅ (C08, U05/U06, real Hacker News) | ✅ Hacker News (5 real versions) | ⚠️ for on-cue changes | — | Moves = delete + insert |
| History and version comparison | ✅ | ✅ (C11–C12, E08) | ✅ | — | — | — |
| CSS / XPath / keyword filters | ✅ | ✅ (U32, live Hacker News 64→30→4) | ✅ | — | — | Plain keyword returns the word only; use `/…/` |
| Indian product: name, price, currency, stock | ✅ | ✅ (C06–C07, live) | ✅ Decathlon, Sleepy Owl, boAt | — | — | Bot checks; several prices need a selector |
| Price increase/decrease and % | ✅ | ✅ (C10, U33, formula verified) | ⚠️ only when shops change prices | ✅ | — | — |
| Out of stock / back in stock | ✅ | ✅ (C09, U08, demo) | ⚠️ Sleepy Owl and boAt currently out of stock; a restock would be genuine | ✅ | — | Default for new products: alert on restock only |
| Price chart, min/max/average | ✅ | ✅ (C13–C14, U09–U10, hand calculation) | ⚠️ needs 2+ real price versions | ✅ | — | Not time-weighted |
| Job boards: structured openings (Hevo, Meesho, HackerRank, python.org) | ✅ | ✅ (live 26 Nov: 18/10/17/22; unit tests; J01–J04) | ✅ | — | — | JavaScript-only boards need the browser; a custom page with 0 openings and no "no openings" message shows an error |
| New / removed / modified openings, reordering, duplicates, failures | ✅ | ✅ (J05–J13, unit tests, demo buttons) | ⚠️ real job changes take days | ✅ | — | — |
| Job keyword filter (titles), re-baseline on edit | ✅ | ✅ (J02, J08, J14, U32) | ✅ | — | — | Matches titles only |
| Job history, chart, per-day table, persistence | ✅ | ✅ (J11, P06–P07) | ⚠️ needs real changes over time | ✅ | — | — |
| Email notification | ✅ | ⚠️ URL building and masking (U31); **real delivery not yet tested** | — | — | ✅ Gmail app password | Secret stored unencrypted |
| Telegram notification | ✅ | ⚠️ as above; **real delivery not yet tested** | — | — | ✅ bot token | Same |
| Notification history and failure handling | ✅ | ✅ (U30, U15) | — | — | — | "Delivered" = accepted by the service |
| Static scraping (Requests) | ✅ | ✅ | ✅ | — | — | JavaScript pages come back empty |
| Dynamic scraping (Playwright + Edge) | ✅ | ✅ (B01–B08, Quotes, Decathlon) | ✅ | — | — | ~8× slower |
| JSON-LD / microdata / Open Graph | ✅ | ✅ (C06, live) | ✅ | — | — | — |
| Scheduler, heap, workers, thread safety | ✅ | ✅ (E14, E15, measured) | ✅ | — | — | — |
| MD5 and diff algorithms | ✅ | ✅ | ✅ | — | — | — |
| Socket.IO live updates | ✅ | ⚠️ seen working in the UI; no dedicated test | ✅ | — | — | — |
| JSON datastore, UUID folders, Brotli | ✅ | ✅ (P01–P05, measured ratios) | ✅ | — | — | Single-user design |
| Persistence after restart | ✅ | ✅ (P01–P05, 21/21 measured) | ✅ | — | — | — |
| REST API and key | ✅ | ✅ (C01–C17, E01–E02, live calls) | ✅ | — | ⚠️ the API key (Settings) | Search is exact unless `partial=true` |
| Backup and restore | ✅ | ✅ (tested 26 Nov) | ✅ | — | — | — |
| SSRF, CSRF, XSS, password | ✅ | ✅ (S01–S08, U34, live checks) | ✅ | — | — | — |
| Network failure handling and retries | ✅ | ✅ (measured) | ✅ | — | — | — |
| Controlled demo | ✅ | ✅ (U33, browser-driven) | — (by design) | ✅ | — | Not real-world data; always labelled |

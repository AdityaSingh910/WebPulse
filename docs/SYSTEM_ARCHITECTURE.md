# WebPulse: system architecture

WebPulse is a **modular monolith**: one Python process holding a Flask web application, a scheduler thread, a pool
of asynchronous fetch workers, a notification thread and a JSON-file datastore. Two optional helper processes run
beside it: headless Microsoft Edge, for pages that need JavaScript, and the local demo site, for controlled
demonstrations.

The core engine is inherited from [changedetection.io](https://github.com/dgtlmoon/changedetection.io) (Apache-2.0).
`docs/ORIGINAL_CONTRIBUTIONS.md` says what WebPulse added or changed. Paths below are relative to `changedetectionio/`
unless they start with `e2e/`, `demo/` or `run.ps1`.

---

## 1. Overall system architecture

```mermaid
flowchart LR
    subgraph User["User's computer (everything binds to 127.0.0.1)"]
        B["Web browser<br/>http://127.0.0.1:5000"]
        subgraph P["WebPulse process (changedetection.py)"]
            F["Flask app + blueprints<br/>flask_app.changedetection_app()"]
            SIO["Socket.IO server<br/>realtime/socket_server.py"]
            API["REST API /api/v1<br/>api/*.py, api/auth.py"]
            SCH["Scheduler thread<br/>ticker_thread_check_time_launch_checks()"]
            Q[("RecheckPriorityQueue<br/>queue_handlers.py (heapq)")]
            W["Async workers x3<br/>worker.async_update_worker()"]
            PR["Processors<br/>text_json_diff / restock_diff / job_listings"]
            N["Notification thread<br/>notification_runner()"]
            DS[("JSON datastore<br/>store/ChangeDetectionStore")]
        end
        E["Headless Edge (CDP :9222)<br/>started by run.ps1"]
        D["Demo site (:8199)<br/>e2e/fixture_server.py"]
    end
    Internet[("Public websites<br/>shops, job boards, news")]
    Mail["Gmail / Telegram<br/>(Apprise)"]

    B <-->|HTTP + CSRF| F
    B <-->|WebSocket| SIO
    B -->|x-api-key| API
    F --> DS
    API --> DS
    SCH -->|due watches| Q
    F -->|Check now = priority 1| Q
    Q --> W
    W -->|plain HTTP| Internet
    W -->|CDP| E --> Internet
    W -->|named demo proxy| D
    W --> PR --> DS
    W -->|changed| N --> Mail
    W -.->|signals| SIO
```

| Layer | Main files | Notes |
|---|---|---|
| Entry point | `changedetection.py` → `__init__.py: main()` | parses `-d <datastore> -p <port>`; `sigshutdown_handler()` saves and exits on SIGINT/SIGTERM |
| Web app | `flask_app.py: changedetection_app()`, `blueprint/*` | Jinja2 templates, Flask-WTF CSRF, optional password login |
| Real time | `realtime/socket_server.py: SignalHandler` | blinker signals → Socket.IO events to open pages |
| Scheduler | `flask_app.py: ticker_thread_check_time_launch_checks()` | one thread; finds due watches |
| Queue | `queue_handlers.py: RecheckPriorityQueue`, `queuedWatchMetaData.py: PrioritizedItem` | binary min-heap |
| Workers | `worker_pool.py: start_async_workers()`, `worker.py: async_update_worker()` | `FETCH_WORKERS` (3 by default in `run.ps1`) |
| Fetchers | `content_fetchers/requests.py`, `content_fetchers/playwright.py` | plain HTTP / Playwright over CDP to Edge |
| Processors | `processors/text_json_diff`, `processors/restock_diff`, `processors/job_listings` | one plug-in per kind of monitoring |
| Storage | `store/__init__.py: ChangeDetectionStore`, `store/file_saving_datastore.py: save_json_atomic()` | JSON + Brotli files |
| Notifications | `notification_service.py`, `notification/history.py`, `notification/simple_setup.py` | Apprise URLs |
| Security | `validate_url.py`, `api/auth.py`, Flask-WTF | SSRF gate, API key, CSRF |

---

## 2. Website monitoring workflow

```mermaid
sequenceDiagram
    autonumber
    participant S as Scheduler / "Check now"
    participant Q as Priority queue
    participant W as Worker
    participant G as SSRF gate (validate_url.py)
    participant F as Fetcher (requests / Edge)
    participant P as text_json_diff processor
    participant M as Watch model / datastore
    participant N as Notification queue
    S->>Q: PrioritizedItem(priority, uuid)
    Q->>W: lowest priority first
    W->>W: claim_uuid_for_processing(uuid)
    W->>G: is_fetch_url_allowed(url) (DNS re-resolved now)
    W->>F: call_browser() - GET page
    F-->>W: HTML, status, headers
    W->>P: run_changedetection(watch)
    P->>P: subtractive selectors, CSS/XPath include filters (FilterConfig)
    P->>P: html_to_text(), ignore text, extract_text regex
    P->>P: MD5 (ChecksumCalculator) vs previous_md5
    P-->>W: changed?, update_obj, text
    alt changed or first check
        W->>M: save_history_blob() (Brotli if > 20 KB) + history.txt line
        W->>N: send_content_changed_notification() (from the 2nd version)
    else same MD5
        W->>M: update last_checked only (no new version)
    end
```

* **Change detection:** an MD5 of the filtered text (`processors/text_json_diff/processor.py: ChecksumCalculator`).
  Identical text gives an identical hash, so no version is stored. This was verified live in Phase 14 for 4 sites.
* **Differences:** `diff/__init__.py: render_diff()` (difflib opcodes; word level with diff-match-patch). Added text
  is shown green and removed text red.
* **Filters:** CSS and XPath (`html_tools.include_filters()`, `xpath_filter()`), regex (`ContentTransformer.extract_by_regex()`),
  trigger and ignore text (`RuleEngine`).

---

## 3. Product price and stock monitoring

```mermaid
flowchart TD
    A[Fetched product page] --> B{"Structured data?<br/>pure_python_extractor (JSON-LD, microdata, Open Graph)<br/>then extruct"}
    B -->|price + availability| C["Restock dict<br/>price, currency, in_stock"]
    B -->|nothing| X["ProcessorException<br/>'Unable to extract restock data'<br/>old price/stock KEPT"]
    B -->|several prices| Y["MoreThanOnePriceFound -> error<br/>(or the user's CSS price filter)"]
    C --> K["Incomplete reading? (Phase 15)<br/>no price -> keep last price<br/>no stock -> keep last stock"]
    K --> D{"Compared with the stored values"}
    D -->|stock changed and in_stock_processing allows| CH[change]
    D -->|price changed, follow_price_changes| L{"min/max band?<br/>% threshold vs previous check?"}
    L -->|outside band / above threshold| CH
    L -->|inside / below| NC[no version]
    D -->|same| NC
    CH --> V["Version 'In Stock: True - Price: 799.0'<br/>+ notification"]
    V --> H["Price history: difference.py _build_series()<br/>compute_price_summary() (min, max, mean, median, quartiles)<br/>export_xlsx()"]
```

Source: `processors/restock_diff/processor.py: perform_site_check.run_changedetection()`, `get_itemprop_availability()`;
`processors/restock_diff/__init__.py: Restock.parse_currency()`, `get_price_change_percent()`.

---

## 4. Structured job monitoring (WebPulse)

```mermaid
flowchart TD
    A[Fetched careers page] --> E["extract.extract_jobs(html, url, selectors)"]
    E --> S1{"Which board?"}
    S1 -->|div.posting / .postings-wrapper| L[Lever]
    S1 -->|.job-post / div.opening| G["Greenhouse ('New' tag removed)"]
    S1 -->|li.opening-job| R[SmartRecruiters]
    S1 -->|user CSS/XPath section| C["Generic cards (_card_for, _parse_card)"]
    S1 -->|JSON-LD JobPosting| J[schema.org]
    S1 -->|none| AU[job-like links outside nav/footer]
    L & G & R & C & J & AU --> ID["Opening = title, company, location, type, team, url<br/>id = canonical job URL (tracking params removed)"]
    ID --> Z{"Any opening?"}
    Z -->|no, and confirmed_empty() finds an explicit signal| K
    Z -->|no signal| ERR["Error - every stored opening kept"]
    Z -->|yes| K["keyword_matcher(extract_text) on titles"]
    K --> T["tracker.apply_check(state, jobs, now, filter_hash, found)"]
    T --> B1{"first read / filters changed?"}
    B1 -->|yes| BL["baseline event - no alert<br/>(worker.suppress_change_notification)"]
    B1 -->|no| CMP["set comparison by id:<br/>new, removed, modified (field old -> new), re-opened"]
    CMP --> DROP{"drop to <= 20 % of >= 10?"}
    DROP -->|first time| SUS["SuspiciousDrop error - wait for confirmation"]
    DROP -->|no / confirmed| EV["event appended; jobs.json saved atomically"]
    EV --> SNAP["sorted one-line-per-opening text -> version + alert"]
```

* **Data structure:** `jobs.json` = `{jobs: {id: {title, company, location, employment_type, team, url, first_seen,
  added_at, last_seen, status, removed_at, modified_at, baseline, changes[]}}, events: [...], baseline_at,
  filter_hash, last_found, last_matched, declared_total, empty_reason, pending_drop}`.
* **Pages:** `blueprint/jobs/__init__.py` (`/jobs/`, `/jobs/<uuid>`) uses `tracker.summary()`, `filtered_jobs()`,
  `timeline()` and `chart_geometry()`.

---

## 5. Scheduler and priority queue

```mermaid
flowchart LR
    T["ticker_thread_check_time_launch_checks()<br/>loops over all watches"] --> C{"paused? time_schedule_limit?<br/>now - last_checked >= interval (+ jitter)?<br/>>= MINIMUM_SECONDS_RECHECK_TIME?<br/>not running / not queued?"}
    C -->|due| P1["PrioritizedItem(priority = int(time.time()))"]
    U["Check now (UI / API ?recheck=1)"] --> P0["PrioritizedItem(priority = 1)"]
    P1 --> H[("RecheckPriorityQueue<br/>heapq min-heap + RLock<br/>dataclass(order=True)")]
    P0 --> H
    H -->|"heappop: smallest priority first"| W[Worker]
```

* **Why a heap:** insert and remove are O(log n), and a manual check (priority 1) always comes out before scheduled
  checks (priority = Unix time, about 1.8 × 10⁹).
* **Measured (Phase 14):** a 10-second interval gave gaps of 10/10/10/10 s. With all 3 workers busy, a manual check
  finished in 3.0 s, ahead of 3 queued scheduled checks.
* **Laptop sleep (Phase 15):** freezing the process for 35 s ran the overdue check 0.2–0.4 s after resume, then the
  normal 10 s rhythm returned, with no burst.
* **The queue lives in memory.** Manual checks still queued at shutdown are lost (measured 0/9). Scheduled checks
  are simply found due again after a restart (6/6).

---

## 6. Worker concurrency

```mermaid
sequenceDiagram
    participant Q as Priority queue
    participant W1 as Worker 1 (own asyncio loop)
    participant W2 as Worker 2
    participant W3 as Worker 3
    participant L as claim lock (worker_pool.py)
    Q->>W1: item A
    W1->>L: claim_uuid_for_processing(A) - ok
    Q->>W2: item A (queued twice)
    W2->>L: claim(A) - already running: re-queued with a lower priority (max(1000, p*10)), checked afterwards
    Q->>W3: item B
    W3->>L: claim(B) - ok
    W1->>W1: await fetch (I/O, no thread blocked)
    W1->>W1: run_in_executor(run_changedetection) (CPU: lxml, inscriptis)
    W1->>L: release_uuid_from_processing(A)
```

* **Workers:** threads, each with its own asyncio event loop (`worker_pool.start_async_workers()`). Fetching is
  awaited; CPU-heavy parsing goes to an executor.
* **Race prevention:**
  * a UUID claim under a lock, so a watch is never processed twice at the same time (measured: 5 queued requests →
    2 sequential checks);
  * already-queued checks are skipped;
  * every write is atomic: a temporary file, then `os.replace`.
* **Measured:**
  * 6 × 3-second pages in 6.4 s (3 workers);
  * 1,000 local pages in 17.3 s with 3 workers (58 checks/s) and 10.3 s with 10 workers (97 checks/s).

---

## 7. Datastore and file layout

```mermaid
flowchart TD
    R["%USERPROFILE%\cdio-data\webpulse-demo\"] --> CJ["changedetection.json<br/>settings, API token, notification URLs, tags"]
    R --> NH["notification-history.jsonl<br/>(WebPulse, last 500 sends, secrets masked)"]
    R --> PX["proxies.json<br/>(named demo-site proxy)"]
    R --> U["&lt;watch-uuid&gt;\"]
    U --> WJ["watch.json<br/>URL, processor, filters, intervals, restock state"]
    U --> HT["history.txt / history-&lt;processor&gt;.txt<br/>'timestamp,snapshot-file' per version"]
    U --> SN["&lt;md5&gt;.txt or .txt.br<br/>version text (Brotli above 20 KB)"]
    U --> RAW["&lt;timestamp&gt;.html.br<br/>raw page of the latest versions"]
    U --> CK["last-checksum.txt<br/>raw-download MD5 (skip unchanged)"]
    U --> JJ["jobs.json<br/>(job_listings: openings + events)"]
    U --> RJ["restock_diff.json<br/>(product settings)"]
    U --> SS["last-screenshot.png / elements.deflate<br/>(browser fetches)"]
```

* **Writes:** `store/file_saving_datastore.py: save_json_atomic()` (temp file, `os.replace`, fsync) and
  `model/Watch.py: save_history_blob()`.
* **History indexes:** one per processor (`Watch.history_index_filename`). Switching a watch's processor shows a
  separate history; the old one stays on disk.
* **Measured:**
  * Brotli on real data: 33.6 MB → 3.8 MB (−88.6 %);
  * your live folder is 4.8 MB for 62 watches (median 110 KB per product, 21 KB per website, 41 KB per job board);
  * synthetic minimal pages take 3.4 KB per watch after the first version.

---

## 8. REST API communication

```mermaid
sequenceDiagram
    participant C as Client (curl / script)
    participant A as Flask-RESTful /api/v1
    participant K as api/auth.py
    participant O as OpenAPI validation
    participant D as Datastore
    participant Q as Queue
    C->>A: GET /api/v1/watch  (x-api-key: ...)
    A->>K: header == api_access_token ?
    K-->>C: 403 if missing or wrong
    A->>O: validate request against the OpenAPI spec
    A->>D: read watches
    A-->>C: 200 JSON
    C->>A: GET /api/v1/watch/<uuid>?recheck=1
    A->>Q: PrioritizedItem(priority=1)
    A-->>C: 200 "OK"
```

**Endpoints exercised in Phase 14:** `/systeminfo`, `/watch` (GET list, POST create), `/watch/<uuid>` (GET, PUT,
DELETE), `/watch/<uuid>/history`, `/watch/<uuid>/history/<ts>`, `/watch/<uuid>/difference/<a>/<b>`, `/tags`,
`/search?q=&partial=true`, `/import`. With no key or a wrong key the answer is 403.

---

## 9. Notification architecture

```mermaid
flowchart LR
    W[Worker: change saved] --> NQ[("notification queue")]
    NQ --> NR["notification_runner()<br/>flask_app.py"]
    NR --> NS["notification_service.py<br/>tokens: {{watch_url}}, {{diff}}, price..."]
    NS --> AP["Apprise<br/>mailtos:// (Gmail app password)<br/>tgram:// (bot token + chat id)<br/>json:// (webhook, tests)"]
    AP --> EM[Email]
    AP --> TG[Telegram]
    NR --> NH["notification/history.py: record()<br/>notification-history.jsonl<br/>passwords and tokens masked"]
    UI["Notifications page<br/>notification/simple_setup.py:<br/>build_email_url(), build_telegram_url(),<br/>find_telegram_chats()"] --> CJ[("changedetection.json<br/>notification_urls")]
    CJ --> NS
```

* **When an alert is sent:** a notification is queued only from the second version onwards, and never for a
  job-board baseline or for muted watches.
* **Delivery:** real delivery to Gmail or Telegram needs your own credentials. It has **not** been verified in this
  project (`docs/KNOWN_LIMITATIONS.md`).

---

## 10. Bottlenecks and scaling (summary; details in FINAL_PROJECT_READINESS.md §7)

| Resource | Measured | Practical limit on one laptop |
|---|---|---|
| Check throughput (local pages, plain HTTP) | 58/s with 3 workers, 97/s with 10 (1,000 watches) | real sites: limited by network latency (~1–2 s per page) to roughly 1.5–3 checks/s with 3 workers |
| Browser checks | 6–11 s each | ~0.3–0.5/s with 3 workers; Edge memory grows with concurrent pages |
| Memory | 96 MB empty, 106 MB with 1,000 watches | not the bottleneck up to thousands of watches |
| Startup | 2.9 s (100 watches), 15 s (1,000) | ~linear; about 2.5 min estimated for 10,000 (not measured) |
| Page latency | Home 0.04 s, list 0.05 s, API list 0.11 s at 1,000 | the list page paginates |
| Storage | 3.4 KB to 110+ KB per watch, more with history | disk is not the limit; the many small files are |

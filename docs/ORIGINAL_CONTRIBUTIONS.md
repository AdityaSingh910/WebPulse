# WebPulse: original contributions versus inherited functionality

WebPulse is built on **changedetection.io** by dgtlmoon and contributors (Apache License 2.0; `LICENSE` unchanged,
`NOTICE` with an addendum, `README.upstream.md` kept). The upstream base is commit `c74be04b` (24 Nov 2026). Every
WebPulse change is listed phase by phase in `CHANGES.md`, and every modified inherited file carries a "Modified 2026"
notice header.

**Scale of the work** (`git diff c74be04b HEAD`, translations excluded): 905 files changed, +11,182 / −62,293 lines.
Most of the removals are upstream features taken out for the simplified, single-user scope. That is 50 new files,
110 modified files and 777 deleted files, plus the Phase 15 changes listed in `docs/FINAL_PROJECT_READINESS.md`.

## 1. At a glance

| Area | Inherited from changedetection.io | Written or changed for WebPulse |
|---|---|---|
| Core engine | Flask app, scheduler thread, priority queue (heap), async worker pool, UUID claims, fetchers (requests, Playwright), JSON datastore with Brotli, the diff engine, REST API + OpenAPI, Socket.IO, Apprise notifications, backups, CSRF, password login, the SSRF gate (`validate_url.py`) | one-line worker hook for silent baselines; per-hop SSRF guard for the **browser** fetcher; tolerant retry setting; `run.ps1` launcher with safety checks |
| Website monitoring | `text_json_diff` processor, CSS/XPath/regex/JSON filters, MD5 change detection, text diffs | plain-language UI, "Track website" flow, contextual empty states |
| Product monitoring | `restock_diff` processor, JSON-LD/microdata/Open Graph extraction, price chart and statistics, XLSX export | Indian-shop selection and validation; **incomplete readings keep the last price/stock** (fixes a missed-alert bug and false stock alerts); Products page and labels |
| Job monitoring | none (upstream only diffs text) | **the whole `job_listings` processor**: extraction for Lever / Greenhouse / SmartRecruiters / CSS / JSON-LD / automatic, stable job identity, set-based comparison, baselines, sudden-drop confirmation, confirmed-empty detection, the job history, the Job listings and Openings pages |
| Notifications | Apprise, notification tokens and templates | simple Email/Telegram setup page (`simple_setup.py`), persistent masked notification history (`history.py`) |
| UI | upstream templates and styles | WebPulse design system (`webpulse.scss`), sidebar, Home use-case dashboard, technical-settings toggle, demo labelling, mobile fixes |
| Demonstration | none | Controlled demo page (`demo_lab`), local demo site (`e2e/fixture_server.py`), presentation set-up scripts |
| Testing | upstream pytest suite (Linux, pytest-flask live server) | Windows end-to-end harness (`e2e/`, 126 checks), unit tests for job monitoring (25), known-failure reconciliation |
| Documentation | upstream README | every file in `docs/`, `CHANGES.md` |

## 2. Modules written for WebPulse (new files)

| File | Lines | What it does | Key algorithms and data structures |
|---|---|---|---|
| `processors/job_listings/extract.py` | 497 | reads job openings from HTML | board detection by DOM signature; card discovery (`_card_for`: climb to the smallest ancestor holding exactly one job link); canonical-URL identity (`canonical_url`: absolute, no fragment, only job-id query keys); JSON-LD walk (`_ld_items`); `confirmed_empty`; `keyword_matcher`; `keywords_from_rules` |
| `processors/job_listings/tracker.py` | 224 | compares and stores openings | hash-map keyed by job id; set difference for new / removed / modified; baseline and re-baseline (filter hash); sudden-drop confirmation (two identical checks); bounded event log; atomic save |
| `processors/job_listings/processor.py` | 111 | plugs into the inherited worker life cycle | filter hash (MD5 of selectors and keywords); sorted snapshot so order never matters |
| `blueprint/jobs/__init__.py` + 2 templates | 158 | `/jobs/`, `/jobs/<uuid>` | 7/30-day/all-time windows; step-chart geometry computed server-side (inline SVG); per-day aggregation |
| `notification/simple_setup.py` | 157 | Email/Telegram form → Apprise URLs | URL building/parsing with escaping; Telegram chat discovery against a fixed host |
| `notification/history.py` | 122 | persistent notification history | JSONL ring of 500 entries; secret masking (`clean_error`) |
| `blueprint/demo_lab/__init__.py` + template | 187 | Controlled demo page | fixed-address demo site (no SSRF), CSRF-protected actions, priority-1 checks |
| `blueprint/home/__init__.py` + template | 141 | Home use-case dashboard | counts derived from the datastore and the job states |
| `static/styles/scss/webpulse.scss`, `static/js/webpulse-ui.js` | 1,195 + 103 | design system, light/dark, mobile | |
| `e2e/fixture_server.py` | 245 | local test and demo site | bounded state, never forwards, error/malformed/blocked/empty modes, SSRF test routes restricted to 127.0.0.1 |
| `e2e/test_e2e.py`, `e2e/ui_test.py`, `e2e/ssrf_redirect_test.py`, `run_e2e.ps1`, `run_unit.ps1`, `check_*.py` | 591 + 517 + 87 + 141 + 31 + 64 | Windows-native regression harness | throw-away instances on separate ports; checks C, E, J, R, P, S and U |
| `tests/unit/test_job_listings.py` | 25 tests | pure-function tests of extraction and tracking | |
| `demo/*.py`, `run.ps1` | 369 + 147 | data set-up, single start command | pre-flight checks (port, data folder, Python, Edge); helper-process cleanup by profile |

## 3. Inherited files changed by WebPulse (selection)

| File | Change |
|---|---|
| `worker.py` | removed features' hooks; **one hook**: `suppress_change_notification` lets a processor save a baseline version without an alert |
| `content_fetchers/playwright.py` | **Phase 15 SSRF fix**: every browser request is checked against the private-address gate (`_install_private_address_guard`); a redirect into a private address fails the fetch and nothing is saved |
| `content_fetchers/requests.py` | plain labels; an empty `REQUESTS_RETRY_MAX_COUNT` no longer breaks every fetch |
| `processors/restock_diff/processor.py` | **Phase 15**: a reading without a price keeps the last price; a reading without stock data keeps the last stock state |
| `static/js/realtime.js` | guarded `socket.disconnect()` on page unload (an uncaught "Transport not open" on every navigation) |
| `flask_app.py`, `blueprint/ui/*.py`, `store/__init__.py`, templates | blueprint registration, plain labels, the demo-proxy fallback fix, preview and link fixes, the "View changes" redirect for job watches |
| removed (777 files) | LLM/MCP integration, PWA, RSS output, image (SSIM) diff, Selenium/Puppeteer fetchers, many notification UIs, tests of removed features (`docs/SIMPLIFICATION_REPORT.md`) |

## 4. Engineering results that are WebPulse's own

* **Real-world data set:** 22 validated Indian products from 7 retailers, each price checked against an
  independent source (selling price, not MRP), and 14 career boards with 171 relevant openings.
* **Measurements:**
  * retries (Phase 12);
  * workers, scheduler and priority (Phase 14);
  * sleep/resume, restart, load at 100 and 1,000 watches, SSRF through redirects (Phase 15).
* **Bugs found and fixed:**
  * in inherited code: browser SSRF through redirects and JavaScript; missing price/stock readings; the
    Socket.IO unload error; the empty retry variable; XXE test URIs on Windows;
  * in WebPulse code: the Greenhouse "New" tag in titles, the empty Lever board, the duplicate `run.ps1` instances,
    Edge left running after exit, the demo "remove last job".

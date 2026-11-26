# Simplification Report

This report covers the simplified fork of [changedetection.io](https://github.com/dgtlmoon/changedetection.io),
built for a final-year engineering project.

* **Upstream baseline:** commit `c74be04` (v0.70.4), tagged `upstream-baseline-c74be04`. The `master` branch is
  untouched, and all work is on the `simplified` branch.
* **Environment:** Windows 11 with native Python 3.12. No Docker, no WSL2, no paid services.
* **How the figures were produced:**
  * Line counts come from `measure.sh`.
  * Repository size comes from `git ls-tree`.
  * Dependency figures come from `pip`, measured in a freshly created virtual environment.
  * RAM and test results come from `e2e/run_e2e.ps1` and `e2e/run_unit.ps1`.
  * Every figure was measured, not estimated.

---

## 1. Codebase size, before and after

Source lines count `.py`, `.html`, `.js`, `.scss` and `.yaml` files, excluding minified vendor JS.

| Metric | Original | Simplified | Change |
|---|---:|---:|---:|
| Files tracked in git | 1,317 | 563 | **−57 %** |
| Size of tracked files | 19.2 MB | 5.9 MB | **−69 %** |
| All source lines | 123,102 | 89,572 | −27 % |
| Application source lines (excl. tests) | 74,225 | 54,745 | −26 % |
| Python lines (excl. tests) | 49,572 | 35,207 | −29 % |
| Test lines (Python) | 48,877 | 34,817 | −29 %, tests of removed features only |
| Jinja2 templates | 6,909 | 4,636 | −33 % |
| JavaScript (excl. vendor `.min.js`) | 7,266 | 6,377 | −12 % |
| SCSS | 9,303 | 7,395 | −21 % |
| Compiled `styles.css` | 144.6 KB | 106.5 KB | −26 % |
| Language flag images | 5.1 MB | 132 KB | −97 % |
| `requirements.txt` entries | 70 | 57 | −19 % |

Git summary: 762 files deleted, 77 modified, 8 added; 155,157 lines deleted, 2,080 inserted. Most insertions are
the regenerated API docs, the rebuilt CSS and the new test harness.

**Why the total is about 27 %, not the 50–55 % first estimated.** The original plan assumed most of the upstream
test suite would be deleted. That suite needs Linux/`fork()`, so it cannot run on Windows. To keep the automated
tests as requested, only the tests of *removed* features were deleted, and about 34.8k test lines remain. The
deeply integrated conditions engine and browser-steps automation were also kept (see §4). Excluding tests, the
application itself shrank by 26 %, and its Python by 29 %.

## 2. Removed modules and features

| Feature | What was removed | Why it is safe to remove |
|---|---|---|
| LLM / AI integrations | `llm/`, the AI settings pages, the LLM restock plugin, AI notification tokens, AI UI (summaries, intent boxes, AI-mode toggle) | Optional, off unless an LLM provider is configured. Disabling it through config (`LLM_FEATURES_DISABLED`) was verified first |
| MCP server (AI assistant access) | `blueprint/mcp/` including OAuth, MCP settings, the MCP restock tools, two MCP hookspecs | Optional, and registered conditionally. Removing it also removes a login-gate exemption |
| Screenshot (visual SSIM) comparison | `processors/image_ssim_diff/`, comparison slider, image-diff styles | Already disabled by default upstream |
| PWA | Manifest, service worker, install QR code, Android share target | UI convenience only |
| RSS output feeds | `blueprint/rss/` (feedgen), RSS tokens and links | Optional. Its URL-token endpoints bypassed the login gate. *Reading* RSS feeds as watch content is **kept** |
| Proxy checker | `blueprint/check_proxies/` and its "Check/Scan all" UI | Diagnostic tool only. Proxy support itself is **kept** |
| Selenium and Puppeteer fetchers | `webdriver_selenium.py`, `puppeteer.py`, the CDP-event HAR recorder | Playwright covers browser fetching. This was verified **before** removal (§5, B01–B08) |
| Example plugins | `example_plugins/` | Documentation samples, never imported |
| Translations | 15 non-English locales, translation overlay, 536 flag images | `languages.py` falls back to English |
| Deployment config | Dockerfile, docker-compose, entrypoint, `.github/` CI | Docker is out of scope for this project |

**Dependencies removed:** `litellm`, `mcp-types`, `authlib`, `rank-bm25`, `selenium`, `pyppeteer-ng`,
`pyppeteerstealth`, `gevent`, `feedgen` and `segno`. Their transitive dependencies went too: openai, tokenizers,
tiktoken, huggingface-hub, hf-xet, boto3, botocore, s3transfer, aiohttp, fsspec, numpy, trio, websockets and
others. 60 packages in total.

**Dependencies added:**
* `playwright` (Apache-2.0) is now the only browser fetcher.
* `pillow` (MIT-CMU) is used for screenshots. Upstream never declared it; it arrived transitively through the LLM
  stack. The new `e2e/check_imports.py` found this gap.

**Moved to `requirements-dev.txt`:** `pytest`, `pytest-flask`, `pytest-mock` and `pytest-xdist`.

## 3. Dependency size and RAM usage

| | Original | Simplified | Change |
|---|---:|---:|---:|
| Installed packages | 178 | 119 | −33 % |
| `site-packages` size | 557 MB | 284 MB, of which Playwright is 117 MB | −49 % (−70 % without the optional browser driver) |
| Startup to first HTTP 200, warm, average of the 2nd and 3rd run | 1.87 s | 1.25 s | −33 % |
| Idle RAM, fresh datastore, 3 workers | 119.3 MB | 109.3 MB | −8 % |
| RAM after the core e2e workload, same harness | 160.6 MB | 145.7 MB | −9 % |
| RAM with the Playwright fetcher in use (app process only) | n/a | 133.1 MB | – |

The RAM saving is modest because upstream already imported `litellm` (about 200 MB) only on first use. The main
gains are install size, number of packages, startup time and attack surface. The headless Edge process used for
JavaScript pages is separate, and only runs with `run.ps1 -Browser`.

## 4. Retained functionality

| Requirement | Where it lives | Verified by |
|---|---|---|
| Website monitoring and change detection | `processors/text_json_diff`, `diff/`, `html_tools.py` | C08, C12, E08, B07 |
| Web scraping: CSS, XPath, JSONPath filters, plain HTTP and JavaScript browser | `html_tools.py`, `content_fetchers/requests.py`, `content_fetchers/playwright.py` | C04–C05, B02–B03 |
| Price and stock monitoring | `processors/restock_diff` (JSON-LD, microdata, extruct, price-parser) | C06–C07, C10, B04 |
| Historical price analytics and charts | `restock_diff/difference.py` (`compute_price_summary`), `restock-price-graph.js` | C13–C14, E10 (XLSX export), P05 |
| Scheduling | Ticker thread in `flask_app.py`, `time_handler.py` | E14: rechecks automatically every 5 s |
| Concurrent processing | `worker_pool.py`, async workers, UUID claim/release, priority queue | E15: peak ≥ 2 checks in parallel, 6 slow pages |
| REST API | `api/`, with OpenAPI validation and `x-api-key` auth | C01–C03, C11–C12, C16–C17, E12, E13, E18 |
| Dashboard | `blueprint/watchlist`, `blueprint/ui`, settings, tags, Socket.IO live updates | C15, E05–E09, E16–E17, E21–E22 |
| Notifications | `notification/`, Apprise (email, Discord, Telegram, webhooks…) | C18, E11 |
| Data persistence | `store/` (JSON plus snapshot files) | P01–P05, and a datastore created by upstream loads cleanly |

**Also kept, because the core depends on them or they remove nothing optional:**
* **Coupled to the core:** the conditions engine (wired into forms, models and both processors), browser steps and
  the visual selector (they use Playwright), the pluggy plugin infrastructure (the price chart is a hook
  implementation), Jinja2 URL/notification templating, and the Flask-Babel i18n framework, now English-only.
* **Small and useful for a demo:** tags/groups, backups, URL/XLSX import, the add-watch wizard, proxy configuration,
  and CORS for the browser extension.

**Security mechanisms kept and tested:**
* SSRF protection: S06–S08 check `127.0.0.1`, `169.254.169.254` (cloud metadata) and `10.0.0.1`.
* Password login with PBKDF2 (S01–S03), CSRF protection (S04, E22) and API-key authentication (E01–E02).
* URL scheme validation: `file://` and `javascript:` are rejected (E03–E04).
* The XLSX import keeps its XXE-safe parsing (`defusedxml`), and ReDoS-safe regex timeouts are kept.
* The app binds to `127.0.0.1` (`run.ps1`). `ALLOW_IANA_RESTRICTED_ADDRESSES` is set only on the throw-away e2e
  test instance, never by the launcher.

## 5. Test results (final run)

| Suite | Result |
|---|---|
| E2E core: the 18 original regression checks (C01–C18) | **18/18** |
| E2E extended (E01–E22): API auth, URL validation, every UI page renders, export, tags, import, scheduler, concurrency, delete, removed URLs return 404, no leftover UI markers | **22/22** |
| E2E persistence (P01–P05): app restarted on the same datastore | **5/5** |
| E2E security (S01–S08): SSRF protection on, password on | **8/8** |
| E2E browser (B01–B08): Playwright driving Microsoft Edge over CDP | **8/8** |
| **E2E total** | **61/61**, 0 unexpected errors in the app logs |
| Upstream unit tests (`tests/unit`) | 430 passed. The 9 failures and 1 error are exactly the 10 that also fail on the **unmodified** upstream code on Windows (symlinks need admin rights, Windows `file://` paths, `fork()`, timing/DNS). **0 new failures** |
| Template syntax check | 32/32 templates parse |
| Import check | 52/52 third-party modules resolve in the fresh venv, `pip check` is clean |
| Upgrade compatibility | A datastore created by the original app loads: 6 watches, price history intact, all pages 200 |

The e2e checks ran after **every phase**. The full history is in the commit messages.

The upstream unit-test count went from 554 to 430 passing because the tests of removed features (LLM, MCP,
Puppeteer, CDP HAR) were deleted.

## 6. Known limitations

1. **The upstream integration tests (`tests/*.py`, about 34.8k lines) cannot run on native Windows.** They use the
   pytest-flask live server, which needs `fork()`; upstream CI is Linux-only. They are kept, and were edited only
   where they referenced removed features (`test_pdf.py`, `test_backend.py`, `test_group.py`,
   `test_socks5_proxy.py`). Those edits are **unverified** locally. `e2e/` is the runnable regression suite on
   Windows.
2. **Branding.** The UI still shows the changedetection.io name and logo. Upstream's `NOTICE` says those brand
   assets are *not* licensed, so give the project its own name and logo before publishing or distributing it.
3. **JavaScript-rendered sites need the browser.** Start with `run.ps1 -Browser`, which uses headless Microsoft
   Edge. Without it, watches set to the Chrome/Javascript fetcher fail with a connection error. Playwright's own
   browser download is not used.
4. **jq filters are unavailable on Windows.** This is an upstream limitation; the `jq` package has no Windows
   wheel. CSS, XPath and JSONPath filters work.
5. **Notifications were tested end to end through a webhook (`json://`).** Email, Discord, Telegram and similar
   channels use the same Apprise path, but need your own (free) accounts or credentials, so they were not tested
   here.
6. Socket.IO runs in `threading` mode only, since `gevent` was removed. That is upstream's default anyway.
7. Datastore migrations `update_31`, `update_32` and `update_34`, which touch legacy LLM/MCP keys, were
   deliberately kept so upstream datastores still load. The plugin hook argument `llm_intent` is kept, always
   `None`, for plugin API compatibility.
8. `styles.css` was rebuilt with sass 1.77.8. The only differences from upstream's build are equivalent colour
   notations (`rgba` instead of `hsla`).
9. The 10 upstream unit tests listed in `e2e/known_windows_unit_failures.txt` fail on Windows with the original
   code too.

## 7. Updated architecture

```
changedetection.py ─► changedetectionio/__init__.py  main(): CLI (-d datastore -p port), signals
   │                    run.ps1: LISTEN_HOST=127.0.0.1, SSRF protection on, optional headless Edge (-Browser)
   ├─► store/ + model/            JSON datastore: changedetection.json + <uuid>/watch.json + snapshot files
   └─► flask_app.changedetection_app()
         ├─ Auth: password login (PBKDF2) · CSRF · API key · SSRF gate (validate_url.is_fetch_url_allowed)
         ├─ REST API  /api/v1/*      api/ (flask_restful + OpenAPI request validation)
         ├─ UI blueprints            watchlist (dashboard) · ui (edit/diff/preview/queue) · settings ·
         │                           tags · imports · backups · add_watch_ui · browser_steps · conditions ·
         │                           price_data_follower
         ├─ realtime/                Flask-SocketIO (threading): live check status on the dashboard
         ├─ Ticker thread            scheduler, every 1 s: due watches ─► RecheckPriorityQueue
         ├─ worker_pool.py           N async workers (FETCH_WORKERS), one asyncio loop per thread
         │     worker.py ─► content_fetchers/
         │                   ├─ html_requests   plain HTTP (requests, brotli, chardet)
         │                   └─ html_webdriver  Playwright ─CDP─► headless Chrome/Edge (PLAYWRIGHT_DRIVER_URL)
         │               ─► processors/
         │                   ├─ text_json_diff  HTML→text, CSS/XPath/JSONPath filters, triggers,
         │                   │                  checksum compare, diff (diff_match_patch)
         │                   └─ restock_diff    JSON-LD/microdata price + stock (extruct, price-parser),
         │                                      price history analytics + charts (pluggy hook)
         │               ─► snapshot saved ─► notification queued
         └─ Notification runner      notification/ ─► Apprise (email, Discord, Telegram, webhooks, ...)
pluggy_interface.py: plugin hooks (fetchers, processor states, charts, conditions operators, UI extras)
```

Compared with upstream, the following are gone: the LLM evaluator in the worker pipeline, the MCP JSON-RPC server
and its OAuth, the RSS output feed endpoints, the PWA endpoints, the proxy checker, the Selenium and Puppeteer
fetchers, and the image-SSIM processor.

---

## 8. WebPulse redesign (Phase 9)

The simplified application was rebranded **WebPulse - Automated Web Monitoring and Price Analytics System**, and
its interface was redesigned. The backend, algorithms and architecture are unchanged (§7). The full change list is
in CHANGES.md, Phase 9, and screenshots are in `docs/screenshots/`.

**Design:**
* **Visual identity:**
  * A clean, light-first, minimal look: slate neutrals, one teal brand colour, and white cards on a soft grey
    page. The full-screen gradient is gone.
  * An original "pulse" logo and favicon set.
  * A full dark mode, and a layout that works down to phone width.
* **Navigation:**
  * A labelled sidebar in two sections. **Monitor:** Dashboard, Visual add, Groups, Search. **Manage:**
    Notifications, Import, Queue, Settings.
  * A live status card shows how many checks are running, with an activity graph.
  * A top bar shows the page title, the Monitoring/Paused and Alerts toggles, dark mode, and sign-out.
* **Settings:** nine plain tabs. The API key is masked, with Reveal and Copy. The About tab carries the
  open-source attribution.
* **Removed clutter:**
  * the GitHub button, donation heart and overlay, language selector and flags, version labels;
  * the "Browsers – soon" item and the Chrome-extension and affiliate promotions;
  * the upstream tutorial links, the CDN-loaded share-as-image feature, and the external "share watch" service.

**Demonstration data:** `demo/seed_demo.py` creates two kinds of watches.
* **Five live watches.** On first start, all five were fetched without errors:

  | Site | What it shows | Result |
  |---|---|---|
  | `books.toscrape.com` | Price via a CSS filter | £51.77 |
  | `webscraper.io` test shop | Price via microdata | $295.99 |
  | `quotes.toscrape.com/js/` | JavaScript-rendered page, fetched through Edge | The quotes were captured |
  | Hacker News | Change detection on a frequently changing page | Fetched |
  | python.org downloads | A CSS-filtered page | Fetched |

  `scrapingcourse.com` was **not** used, because its robots.txt disallows `/ecommerce/*`.
* **Three sample watches** with simulated history, paused and labelled "[Sample data]". Two are price/stock
  histories (24 and 20 points over 60 days, including an out-of-stock period), and one has four text versions.

**Results after the redesign:**

| | Result |
|---|---|
| End-to-end harness | **87/87**: core 40, persistence 5, security 8, browser 8, plus **26/26 browser UI tests** that click through the real interface in Edge |
| UI tests cover | Adding watches, edit/save, recheck, history and diff, preview, price watch, inline and full price charts, groups, search, API key reveal/copy, settings save, notification send-test, import, pause, mute, dark mode, delete with confirmation, queue and backups, the mobile drawer, password sign-in, 51 internal links (none broken), external links limited to attribution and technical references, and no JavaScript errors |
| Upstream unit tests | 430 passed, 0 new failures (the same 10 known Windows-only failures) |
| Templates / imports | 32/32 templates parse, 52/52 third-party imports resolve |
| RAM, same harness | 122.9 MB after the core workload (was 145.7 MB) and 95.4 MB idle (was 119.5 MB), mainly because the old shell scripts and styles are gone |
| Front-end size | `styles.css` 88 KB plus `webpulse.css` 27 KB, versus 106.5 KB before. Templates went from 4,636 to 4,289 lines and JS from 6,377 to 5,460. There are no external scripts or fonts |

**Bugs found while testing, and fixed:**
1. The Settings page threw a JavaScript error when no time zone was set: `toggleVisibility` was missing a null
   check.
2. `scheduler.js` logged an error every 500 ms on pages without the time-zone field.

Both are present in upstream too.

**Additional limitations:**
* The two live e-commerce test pages do not publish machine-readable stock, so their stock shows as unknown. The
  price is tracked.
* The upstream integration tests that assert old notification titles or the upstream avatar URL would need
  updating. They are Linux-only, so they were not run here.

---

## 9. Use-case dashboard, Email/Telegram, job listings and honest demonstrations (Phase 11)

The full change list is in CHANGES.md, Phase 11. The engine, processors, datastore format, scheduler, workers and
API are unchanged.

| Area | Result |
|---|---|
| Navigation | Home, Websites, Products, Job listings, Notifications, Controlled demo, Settings. The "Advanced" menu is removed; its pages are reachable from Settings → "More tools" and Home → "Behind the scenes" |
| Home | Six use-case cards (website, price, stock, jobs, price analytics, notifications), plus one compact "Behind the scenes" row |
| Settings / edit page | Only everyday options are visible; "Show technical settings/options" reveals the rest, and all fields are still saved |
| Notifications | Email and Telegram only, each with "Save and send test". The 150-service Apprise picker is no longer shown. Secrets are never sent back to the browser. A notification history, masked and kept across restarts, is stored in the datastore |
| Job listings | The existing text watcher in the group "Job listings", with a CSS selector and whole-word keywords. No new backend |
| Demonstrations | The "[Sample data]" watches with simulated history were removed. Real Indian shops and public job boards were added, plus a clearly labelled Controlled demo page that changes only the local demo site |
| Security | The demo page only talks to `http://127.0.0.1:<port>` given by `run.ps1`. The demo site cannot be used to forward requests (U34). The demo proxy is never chosen automatically. SSRF protection is unchanged (S06–S08 pass) |
| Bugs fixed (also upstream) | Preview of a watch with no saved version returned HTTP 500; `visual-selector.js` threw an error on edit pages without a screenshot |
| Tests | **95/95** e2e (40 core, 5 persistence, 8 security, 8 browser, 34 UI); unit 430 passed, 0 new failures; templates 35/35; imports 52/52; RAM after the core workload 123.4 MB |

**Real monitoring, first check on 25 Nov 2026:**
* Decathlon India: ₹799, in stock, read both directly and with Edge;
* Sleepy Owl enamel mug: ₹564, out of stock;
* boAt Stone 650: ₹1,999, out of stock;
* HackerRank: 17 technical job titles;
* Meesho: 10 technical job titles;
* python.org job board: 22 jobs.

Amazon.in and Flipkart were not used: their robots.txt and terms forbid automated access.

**Limitations:**
* Shopify shops (boAt, Sleepy Owl) may show a bot check after several requests in a short time. WebPulse does
  not bypass it; that check records an error.
* Delivery of Email and Telegram depends on credentials the user provides. The automated tests check URL building,
  masking and webhook delivery; real delivery is confirmed by the user's own test message.
* Custom SMTP servers log in with the part of the address before the @. Gmail, Outlook, Yahoo and Zoho are
  configured automatically.

---

## 10. Reliability audit (Phase 12)

Measured findings and fixes are listed in CHANGES.md, Phase 12. In short:
* the "444 s" checks were the laptop sleeping in the middle of a request (confirmed by Windows power events);
* network-error retries were cut from 6 to 2 through upstream's own `REQUESTS_RETRY_MAX_COUNT`. A dead site now
  holds a worker for 2–16 s instead of 31–67 s (5 s timeout);
* links to websites with a single saved version no longer bounce;
* the XXE unit tests now really test the XXE protection on Windows.

Scheduling, priority, blocking, failure handling, persistence, price statistics, SSRF, API authentication and
CSRF were all verified, with results recorded.

**Tests:** e2e 96/96; unit 432 passed and 0 new failures.

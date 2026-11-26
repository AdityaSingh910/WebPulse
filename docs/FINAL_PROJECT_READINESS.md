# WebPulse: final project readiness and engineering audit (Phase 15)

**Date:** 26 Nov 2026

**Starting point:** commit `9d994343` (Phase 14)

**How it was tested:**
* the live application at http://127.0.0.1:5000;
* throw-away instances on other ports for anything that changes data;
* Microsoft Edge driven by Playwright for UI checks;
* the local demo site for every failure scenario. **No load or failure test was run against a real website.**

**Companion documents:**
* `docs/SYSTEM_ARCHITECTURE.md` (diagrams);
* `docs/INSTALLATION_GUIDE.md`;
* `docs/DEMONSTRATION_SCRIPT.md`;
* `docs/KNOWN_LIMITATIONS.md`;
* `docs/ORIGINAL_CONTRIBUTIONS.md`.

---

## 1. Summary

| Area | Result |
|---|---|
| Data correctness (live) | **13/13**: every displayed count equals the stored records; 22 unique real products (23 watches), 7 retailers; 171 active openings; no duplicate ids, no stray "New" badges or title artifacts |
| Reliability (controlled) | **20/20**: HTTP 403/404/429/500/503, malformed JSON-LD and HTML, missing price, missing stock, disconnection and reconnection, duplicate watch, restart with queued checks, a 35 s freeze (sleep), hard stop and restart |
| Startup / shutdown | `run.ps1` now refuses a second instance (port or data folder), names the cause, and cleans up Edge and the demo site on exit (3 bugs fixed) |
| Security | SSRF via redirects/JavaScript (**browser gap found and fixed**), XSS (13 pages, 0 script executions), CSRF, API key, 127.0.0.1-only bindings, no secrets in logs, API responses or 6,027 Git commits, dependency audit **0 known vulnerabilities in 119 packages** |
| UI | 76 page × device × theme combinations: 0 horizontal overflow, 0 console errors; the phone layout of the watch list and the empty-state messages fixed |
| Reproducibility | clean virtual environment from `requirements.txt` in 91 s; the **full end-to-end suite passes on it (126/126)** |
| Scalability | measured at 100 and 1,000 watches (local pages); estimates for 10,000 marked as such (§7) |
| Regression | end-to-end **126/126** (Phase 14: 118); unit **457 passed, 0 new failures** (unchanged) |
| Bugs fixed | **9** (§6) |
| Spend | **₹0**: no paid API, LLM or scraping service |

---

## 2. Data correctness audit (live application)

| Check | Result |
|---|---|
| Classification of the 62 watches | real: 23 product watches, 10 websites, 14 job boards. Public scraping test sites: 4 products, 2 websites. Controlled demo: 1 product, 7 websites, 1 job board |
| Unique products | 22 unique real products in 23 watches. The Decathlon gilet is deliberately watched twice (plain HTTP and browser), and both agree: ₹799, in stock |
| Product fields | all 23 real product watches have a name, a positive INR price and a known stock state. Prices were checked against independent sources in Phase 14 (selling price, not MRP) |
| Home "All products (28)" / Products rows | 28 = 28 stored |
| Home stock card | 18 in stock / 6 out of stock / 4 "not shown by the shop" = stored |
| Job listings totals and Home job card | 171 active / 0 new / 0 removed / 0 changed = sum of the 15 stored job states; 15 careers pages |
| Job ids | no duplicate ids; no duplicate (title, location, link); no empty titles; no Greenhouse "New" suffix; every active real opening has an apply link |
| New badges | none on baseline openings; 0 "new" on the real boards (all baselines; no genuine new job has appeared yet) |
| Keyword edits | no misleading events on the live boards. Covered by e2e J14 (a new baseline, no alert, nothing new or removed) |
| Failed extraction | keeps previous data: products (R01–R04, reliability §4), jobs (J12, demo "Block the careers page") |

---

## 3. UI and usability

* **Responsive and dark mode:** 13 live pages and 6 empty-instance pages, each at 390 px and 1366 px in light and
  dark mode (76 checks). Result: 0 horizontal overflow, 0 console errors. The earlier crawl (Phase 14) covered 201
  pages and 319 links.
* **Fixed (phone):**
  * the type badge ("PRODUCT") was overlapped by "In stock", because it sat in the 40 px checkbox column;
  * each watch card was 434 px wide on a 390 px screen.

  The badge and the price now have their own rows and the buttons wrap. Measured after the fix: 0 overlaps in 93
  rows, and the widest card is 377 px at 390 px and 347 px at 360 px.
* **Fixed (empty states):** the empty Websites/Products list said "add a URL in the box above" (there is no box
  there) and used old upstream wording. It now says one of:
  * "No products yet. On Home, paste a product page address…" (Products);
  * "Nothing is being monitored yet…" (Websites);
  * "Nothing matches this search or filter. Show all" (search or filter).
* **Real vs controlled data** is distinguishable everywhere: `[Demo]` titles, the green "Demo site (simulated)"
  tag, the "Demo" chip on Job listings, and the banner on demo job pages.
* **Adding things:** Home has one address box with three buttons (website / product / job listings), plus "More
  options" for a CSS section and job keywords. Each lands on the matching list or Openings page (U-tests U03, U32).

---

## 4. Reliability and edge cases (throw-away instance, local demo site)

| Scenario | Result |
|---|---|
| HTTP 403 / 404 / 429 / 500 / 503 (product, website and job board at once) | each recorded as the watch's error ("Error - 403 (Access denied) received" …); price, stock, text versions and jobs untouched; all cleared on the next 200 with no false change |
| Malformed JSON-LD | error; last price and stock kept; no version |
| **Missing price** (stock still published) | **bug found and fixed**: the stored price was wiped, so a later drop was compared with "no price" and **missed**. Now the last price is kept, and 999 → (missing) → 899 is reported as a drop (R01, R02) |
| **Missing stock data** | **bug found and fixed**: "in stock → unknown → in stock" created two false versions and alerts. Now the last known state is kept (R03) |
| Malformed HTML (unclosed tags, stray end tag) | text still extracted |
| Site unreachable, then back | 3 checks recorded errors (25.6 s for the round, with 2 retries); nothing lost; recovery with no false change |
| Empty career board / incomplete extraction | confirmed-empty boards remove openings with the reason shown; a blocked page keeps every opening (J12, J18) |
| Duplicate watch | warned "already exists"; a second watch is created (upstream behaviour) |
| Concurrent checks of one watch | never in parallel (Phase 14: 5 requests → 2 sequential checks) |
| Restart with **manual** checks queued | 4 were still queued at the hard stop; **0 of 9** ran after the restart. The queue is in memory (`docs/KNOWN_LIMITATIONS.md` 1.2) |
| Restart with **scheduled** watches | 6/6 checked again within 35 s of the restart |
| **Sleep and resume** (process frozen 35 s, like Windows sleep) | the overdue check ran **0.2–0.4 s** after resume, then the normal 10 s rhythm (+0.4, 10.4, 20.4 s), with no burst |
| Hard stop and restart | versions, price state and job history identical |
| Price-threshold semantics | investigated, documented and **not changed** (`docs/KNOWN_LIMITATIONS.md` §1a) |

---

## 5. Startup, shutdown and running in the background

| Check | Before Phase 15 | After |
|---|---|---|
| Second `run.ps1` on the same port | **ran a second WebPulse on the same data folder** (two schedulers; on Windows both processes stayed up) and replaced the first instance's demo site | refused in 1 s: "port 5081 is busy - WebPulse is already running there …"; the first instance untouched |
| Same data folder, different port | not detected | refused: "another WebPulse (PID …) is already using the data folder …" |
| Port used by another program | Python bind error | refused, naming the program and PID |
| Missing Python | PowerShell exception | clear message pointing to the installation guide |
| Edge cleanup on exit | **Edge kept running** (the PID returned by Start-Process belongs to a launcher stub) | stopped via its own per-port profile; 0 Edge processes left, all 3 ports freed |
| Default paths | hard-coded user paths | `%USERPROFILE%` data folder, `<project>\.venv` Python; the same lookup in `run_e2e.ps1` / `run_unit.ps1` |
| Monitoring with the browser tab closed | | the scheduler runs in the server process; every throw-away test ran with no page open |
| Windows PowerShell 5.1 | | pre-flight path verified; full start tested on PowerShell 7 |

Graceful **Ctrl+C** could not be automated: Windows 11 blocked focus changes and console control events from the test
process. The shutdown handler (`sigshutdown_handler`) and the cleanup path were verified separately, but please press
Ctrl+C once by hand (`DEMONSTRATION_SCRIPT` step 10). Running without a visible terminal is documented in
`INSTALLATION_GUIDE.md` §6; the visible-window workflow is unchanged.

---

## 6. Security and privacy

| Check | Result |
|---|---|
| **SSRF via redirect / JavaScript, plain HTTP** | blocked at the hop: "Redirect blocked: … private/reserved" (S09) |
| **SSRF via redirect / JavaScript, browser** | **vulnerability found**: a "public" page that redirects to, or `fetch()`es, a private address had that content **saved** (reproduced with a 302 and with JavaScript). **Fixed** in `content_fetchers/playwright.py`: every browser request goes through the private-address check (cached per host), and a redirect into a private address fails the fetch with nothing saved (S10, S11). Ordinary pages unaffected: S12, and real pages Quotes to Scrape 7.9 s (10 quotes) and Decathlon 8.5 s (₹799) |
| SSRF on the start URL | 127.0.0.1, localhost, 10.0.0.1, 169.254.169.254 blocked; `file://` refused with HTTP 400 (Phase 14) |
| XSS | `<script>` and `<img onerror>` payloads in page text, a product name and job titles: 13 pages opened, **0 script executions**; payload shown as text on 12 |
| CSRF / API key | 400 without a token; 403 with no key or a wrong key (Phase 14); e2e S01–S08 |
| Bindings | 5000, 8199 and 9222 listen on 127.0.0.1 only |
| Secrets in logs / API responses | the API token was found in none |
| Secrets in Git history | 6,027 commits scanned: the live API token never committed; no Telegram, AWS or GitHub token or private key; 10 `mailto` matches are documentation placeholders (`user:password`, `{SECRET}`, `app-password`); the data folder is not tracked |
| Screenshots | the committed settings screenshot shows the API key masked |
| Backups | contain `changedetection.json` and therefore the API token and any notification secrets (documented) |
| Dependencies | `pip-audit 2.10.1` (PyPA, OSV/PyPI database), 119 installed packages: **0 known vulnerabilities** on 26 Nov 2026 |

These are functional checks of the intended protections, not a penetration test.

---

## 7. Scalability assessment

### 7.1 Measured (local fixture pages; one laptop; plain HTTP)

| Watches | Workers | Bulk import | First full round of checks | Throughput | Peak queue | RAM (app) | Home / list / API list | Disk | Restart |
|---|---|---|---|---|---|---|---|---|---|
| 100 | 3 | 0.7 s | 3.1 s | 32 checks/s | 82 | 101 MB | 0.01 / 0.03 / 0.03 s | 0.4 MB | 2.9 s |
| 1,000 | 3 | 0.8 s | 17.3 s | 58 checks/s | 894 | 106 MB | 0.04 / 0.05 / 0.11 s | 3.4 MB | 15.3 s |
| 1,000 | 10 | 0.7 s | 10.3 s | 97 checks/s | 590 | 108 MB | 0.04 / 0.06 / 0.12 s | 3.4 MB | 14.8 s |

**Other measurements:**
* real pages take 1–2.3 s with plain HTTP and 6–11 s in the browser;
* the live data folder is 4.8 MB for 62 watches (median 110 KB per product, 21 KB per website, 41 KB per job board);
* an empty instance uses 96 MB of RAM.

**One observation:** during the 10-worker run, one watch-list API call returned an error payload instead of the
list. It did not happen on the rerun.

### 7.2 What limits real monitoring (analysis)

The load the scheduler must sustain is `checks per second = watches ÷ interval`. Local pages are almost free (about
17 ms of CPU per check at 58/s), so with real websites **network latency and politeness**, not CPU, set the limit.
With 3 workers and about 1.5 s per page, the capacity is about 2 checks/s (about 7,200/hour). A browser check takes
about 8 s, so capacity drops to about 0.4/s.

| Watches | Needed at a 3 h interval | Needed at 1 h | Plain HTTP, 3 workers | Browser checks | Other effects |
|---|---|---|---|---|---|
| **100** | 0.01/s | 0.03/s | ample | ample | restart 3 s (measured) |
| **1,000** | 0.09/s | 0.28/s | ample (≈2/s) | tight at 1 h with all-browser watches (≈0.4/s) | restart 15 s, list pages ~0.05 s (measured); ~100–300 MB data with history (*estimate*) |
| **10,000** (*estimates*) | 0.93/s | 2.8/s | 3 h OK; 1 h needs ~6–10 workers | needs about 7–20 concurrent browsers (several GB of RAM) or mostly plain HTTP | startup about 2.5 min; ~10,000 folders and 50k–100k small files; politeness: hundreds of watches on one shop would need per-host spacing (not implemented) |

### 7.3 When heavier infrastructure would pay off (future work, not needed now)

| Technology | Becomes worthwhile when | Why |
|---|---|---|
| **PostgreSQL** (or SQLite first) | more than ~5–10k watches, multiple users, or queries across history (e.g. "all price drops this week") | the JSON-per-folder store is scanned and loaded at start; a database gives indexes, transactions and concurrent writers |
| **Redis / a durable queue** | queued manual checks must survive restarts, or several processes share the work | the current heap is in memory (0/9 queued manual checks after a restart) |
| **Distributed workers** | the needed rate exceeds one machine's network/browser capacity (≈2/s plain, ≈0.4/s browser per 3 workers) | horizontal scaling of fetches; per-host rate limiting in one place |
| **Cloud deployment** | 24/7 monitoring without a laptop that sleeps; shared access | needs authentication on by default, HTTPS, secret storage (not plain JSON) and outbound rate limits |
| **Browser pool / service** | many JavaScript-only pages | reuse contexts and cap memory |

None of these is required for the project's scope: dozens to a few hundred watches, one user, a laptop.

---

## 8. Code quality and reproducibility

* **Obsolete scripts:** none removed. Every `demo/` script is referenced by README/CHANGES; `persistence_check.py`
  is now documented in INSTALLATION_GUIDE.
* **Unused dependencies:** 10 requirements are never imported directly, and each has a documented reason:
  * `defusedxml` protects the XLSX import;
  * `tzdata` provides time zones on Windows;
  * `greenlet` is needed by Playwright on Python 3.12+;
  * `cryptography`, `jsonschema` and `referencing` are security/compatibility pins;
  * `python-engineio` belongs to Socket.IO;
  * `paho-mqtt` serves Apprise MQTT;
  * `jq` is Linux/macOS only.

  **None removed.**
* **Dead code:** pyflakes on WebPulse's own modules found 1 unused import (`e2e/ui_test.py`), now removed. Upstream
  code was not refactored.
* **Clean install:** a new venv plus `requirements.txt` took 91 s (exit 0), and the full e2e suite on it gave
  **126/126**.
* **Attribution:** `LICENSE` unchanged, `NOTICE` addendum, `README.upstream.md`; modified files carry notice
  headers; `docs/ORIGINAL_CONTRIBUTIONS.md` separates inherited from WebPulse work.

---

## 9. Bugs identified and fixed in Phase 15

| # | Bug | Where | Severity | Test |
|---|---|---|---|---|
| 1 | Browser fetcher followed redirects and page `fetch()` into private addresses, and saved the content (SSRF) | `content_fetchers/playwright.py` (inherited) | high (local services) | S10, S11 (+S12 control) |
| 2 | A reading without a price wiped the stored price, so the next price change was missed | `processors/restock_diff/processor.py` (inherited) | medium | R01, R02 |
| 3 | A reading without stock data produced two false stock-change alerts | same | medium | R03 |
| 4 | A second `run.ps1` started a second instance on the same data folder and replaced the first one's demo site | `run.ps1` | high (data integrity) | manual test (§5) |
| 5 | Edge was left running after WebPulse stopped | `run.ps1` | low | manual test (§5) |
| 6 | An empty `REQUESTS_RETRY_MAX_COUNT` made every plain-HTTP fetch fail | `content_fetchers/requests.py` (inherited) | low | S09 under the e2e runner |
| 7 | Phone layout: the type badge was overlapped by the stock badge; cards wider than the screen | `webpulse.scss` | low | measured 0 overlaps / 93 rows |
| 8 | Misleading empty-list message ("box above"; also shown for empty search results) | `watch-overview.html` | low | throw-away instance |
| 9 | e2e J14 race: an earlier alert arriving late was counted | `e2e/test_e2e.py` | test only | 126/126 twice |

**Also changed:**
* the demo site gained error, malformed, missing-price/stock and SSRF test modes;
* `run_unit.ps1` reports an incomplete run explicitly;
* the test runners locate Python portably;
* one unused import was removed.

---

## 10. Regression results

| Suite | Phase 14 | Phase 15 |
|---|---|---|
| End-to-end (`run_e2e.ps1 -Browser -UI`) | 118/118 | **126/126**: core 64, persist 7, security 8, browser 8, **ssrf 4 (new)**, UI 35; 0 unexpected app-log errors. Also 126/126 on the clean-install environment |
| Unit (`run_unit.ps1`) | 457 passed, 8 known, 0 new | **457 passed**, 7 failed + 1 error = the 8 known Windows-only items, **0 new** |
| Templates / imports | 37 / 52 | 37 / 52 |
| Data audit / reliability / XSS / SSRF harness | n/a | 13/13, 20/20, 0 executions, 3/3 blocked + 1 control |

A background (detached) unit run produced no pytest output, as happened once in Phase 11. The runner exits 1 in
that case and now says the run is invalid. The foreground run above is the valid result.

---

## 11. Network use and cost (Phase 15)

| Traffic | Amount |
|---|---|
| Load and failure tests | local only (127.0.0.1 demo site): **0 requests to real websites** |
| Real websites | 2 browser page loads to verify the SSRF fix (quotes.toscrape.com, one Decathlon product; each with its sub-resources) and the live app's own scheduled checks (7 checks during this phase; 139 since its start) |
| Package index | the clean install (~120 packages from PyPI), `pip-audit` and `pyflakes` in a separate venv, and pip-audit's vulnerability lookups for 119 packages (OSV/PyPI JSON API) |
| Paid APIs, LLMs, scraping services | **none, ₹0** |

---

## 12. Final state

* **Application:** running at http://127.0.0.1:5000 with the updated `run.ps1` (visible backend window, demo site on
  8199, Edge on 9222).
* **Watches:** **62**: 53 real + 9 controlled demo; by processor 28 products, 19 websites, 15 job boards. None in
  error. No watch recreated, no history deleted.
* **Commit:** see the reply that delivered this phase (`git log -1` on branch `simplified`).
* **Files modified in Phase 15:**
  * code: `run.ps1`; `content_fetchers/playwright.py`, `content_fetchers/requests.py`;
    `processors/restock_diff/processor.py`;
  * templates and styles: `blueprint/watchlist/templates/watch-overview.html`, `static/styles/scss/webpulse.scss`,
    `static/styles/webpulse.css`;
  * tests: `e2e/fixture_server.py`, `e2e/test_e2e.py`, `e2e/ssrf_redirect_test.py` (new), `e2e/run_e2e.ps1`,
    `e2e/run_unit.ps1`, `e2e/ui_test.py`;
  * docs: `CHANGES.md`, `README.md`, and the six documents in `docs/` (new).

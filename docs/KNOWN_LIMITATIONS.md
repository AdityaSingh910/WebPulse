# WebPulse: known limitations

Every item was observed or measured during Phases 12–15 unless it is marked *design* (a deliberate limit of the
architecture) or *estimate*. WebPulse is a single-user, local application for a final-year project. It has **not**
been hardened, penetration-tested or load-tested to production standards, and this document does not claim it has.

## 1. Monitoring behaviour

| # | Limitation | Evidence / consequence | Possible future work |
|---|---|---|---|
| 1.1 | **The price % threshold compares with the previous check, not the last alert.** | See §1a | A "compare with the last alerted price" option |
| 1.2 | Checks queued by hand ("Check now") are lost when WebPulse stops before running them | Restart test: 0 of 9 queued manual checks ran after a restart. Scheduled checks are found due again (6/6). The queue (`queue_handlers.RecheckPriorityQueue`) lives in memory (*design*) | A durable queue (§4 of FINAL_PROJECT_READINESS) |
| 1.3 | HTTP 429 "Retry-After" is not honoured specially | The 429 is recorded as the error; the next attempt comes at the normal interval (6–24 h for real sites), which is already longer | Per-host back-off |
| 1.4 | No per-website rate limit beyond the interval | Several watches on one host are checked independently. The real watches use 6–24 h intervals and at most a few pages per site | Per-domain spacing in the scheduler |
| 1.5 | A sleeping laptop pauses monitoring | Freezing the process for 35 s: the overdue check ran 0.2–0.4 s after resume. A check that was in flight reports the sleep time as its duration (Phase 12: "444 s") | Keep the laptop awake for demos |
| 1.6 | Moved lines show as delete + insert in the text diff | inherited `difflib` behaviour | |
| 1.7 | Adding an existing URL is allowed, with a warning | "Warning, URL … already exists"; a second watch is created (inherited) | |

### 1a. The price % threshold, explained (the semantics are unchanged)

The product setting "only alert when the price changes by at least N %" is implemented in
`processors/restock_diff/processor.py`. Each check compares the new price with the **price stored by the previous
check**, and that stored price is updated on every successful check, even when no alert was sent.

* **What you get:** an alert for any single step of at least N % between two consecutive checks. Measured with a
  10 % threshold:

  | Step | Change | Alert |
  |---|---|---|
  | 1000 → 950 | −5 % | none |
  | 950 → 850 | −10.5 % | alert |
  | 850 → 840 | −1.2 % | none |

* **What you do not get:** a slow drift. With 1000 → 950 → 903 → 858, each step is about −5 % and none is alerted,
  although the total fall is 14 %.
* **Why it was not changed:** this is the inherited upstream behaviour and its code comment states it ("against the
  previous check's price"). Changing it silently would alter existing users' alerts. A "since the last alert" mode
  would be a new option. Min/max price limits (alert when the price leaves a band) are unaffected and are the better
  tool for "tell me when it drops below ₹X".

## 2. Data extraction

| # | Limitation | Evidence |
|---|---|---|
| 2.1 | Products need machine-readable price data (JSON-LD, microdata or Open Graph) or a CSS price filter | Noise's Kore and ColorFit smartwatch pages publish **malformed JSON-LD** (extruct `JSONDecodeError`); the result is an error that keeps the last data |
| 2.2 | Stock is only as reliable as the shop's own data | e.g. books.toscrape publishes no stock: "not published" |
| 2.3 | Incomplete readings keep the last known value (fixed in Phase 15): **no price** keeps the last price, **no stock data** keeps the last stock state | Before the fix, a missing price wiped the stored one, so a later drop was missed, and missing stock produced two false alerts. The trade-off: a price removed on purpose stays shown until a new price appears |
| 2.4 | Job keywords match the **title** only | Paytm's "(Frontend)" titles are sales roles, so its keyword list omits "frontend" |
| 2.5 | Boards rendered only with JavaScript and without a public job list are unsupported | Workday (BrowserStack), JavaScript-only careers pages (Postman, PhonePe, Swiggy) |
| 2.6 | An empty board is accepted only on an explicit signal (Lever's no-postings message, Greenhouse "0 jobs", or a "no open positions" text in the selected section); otherwise "no openings" is an error | Safe by design: a bot-check page never removes jobs. A custom careers page that is empty without saying so stays in error |
| 2.7 | A sudden drop to 20 % or less of at least 10 openings needs two identical checks before removals are recorded | Intentional; delays genuine mass removals by one interval |
| 2.8 | Switching a watch's processor starts a separate history | `Watch.history_index_filename` (inherited); the old versions stay on disk |
| 2.9 | Websites blocking automated access are not monitored | Croma: HTTP 403 + bot check. Amazon, Flipkart and Myntra: excluded by their terms of use. Zomato careers: excluded by robots.txt. No CAPTCHA or login bypass is attempted (*design*) |

## 3. Security and privacy (local single-user scope)

| # | Limitation | Notes |
|---|---|---|
| 3.1 | Notification secrets (Gmail app password, Telegram token) and the API token are stored **unencrypted** in `changedetection.json` | protected only by the Windows account's file permissions (inherited) |
| 3.2 | **Backups contain those secrets** (the zip includes `changedetection.json`) | keep backup files private |
| 3.3 | The API token is present in the HTML of the Settings page (masked; "Reveal" shows it) | anyone who can open the local UI can read it. Set a password (Settings) on shared computers |
| 3.4 | No login by default | the app listens on 127.0.0.1 only (verified), so only the local user reaches it |
| 3.5 | Browser-mode SSRF: a redirect into a private address is detected only after the browser has sent that request | Phase 15 fix: the fetch is failed and nothing is saved. JavaScript requests and direct navigations are blocked before sending. The plain-HTTP fetcher checks every hop before sending |
| 3.6 | Dependency audit is a point-in-time result | pip-audit, 26 Nov 2026: 119 packages, 0 known vulnerabilities. New advisories appear over time |
| 3.7 | Not a penetration test | the SSRF, CSRF, XSS, API-key and binding tests are functional checks of the intended protections |

## 4. Operations and scale

| # | Limitation | Notes |
|---|---|---|
| 4.1 | One process, one data folder; JSON files instead of a database (*design*) | `run.ps1` refuses a second instance on the same port or data folder (Phase 15) |
| 4.2 | Ctrl+C was not automatable in the test environment | the cleanup path (stop demo site and Edge when WebPulse exits) was verified; the graceful Ctrl+C itself should be checked by hand (DEMONSTRATION_SCRIPT step 10) |
| 4.3 | Startup time grows with the number of watches | measured 2.9 s (100), 15 s (1,000); about 2.5 min for 10,000 (*estimate*) |
| 4.4 | Browser checks are slow and memory-heavy | 6–11 s per page; a few hundred MB of Edge per concurrent page (*estimate*) |
| 4.5 | One API list call returned an error payload once during the 1,000-watch / 10-worker load test | not reproduced on the rerun; recorded as an observation |

## 5. Testing gaps

* **Email and Telegram:** real delivery was **not tested**, because no credentials were configured, as instructed.
  The URL building, masking and history are tested.
* **Upstream's Linux-only integration tests** (`changedetectionio/tests/*.py`, pytest-flask live server) cannot run
  on native Windows. They are replaced by `e2e/` (126 checks).
* **8 upstream unit tests fail on Windows only:** they are explained in `e2e/known_windows_unit_failures.txt`, and
  none is caused by WebPulse.
* **No genuine real-world change** in price, stock or jobs has been observed yet on the real watches. Wikipedia
  showed genuine hourly text changes. Changes on demand are shown with the Controlled demo.

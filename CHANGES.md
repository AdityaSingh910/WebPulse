# CHANGES — simplified fork of changedetection.io

This file is the modification record that Apache-2.0 §4(b) requires: it lists every file the fork changed.
The fork is based on upstream commit `c74be04` (v0.70.4, 2026-11-24), which this repository tags as
`upstream-baseline-c74be04`. The `master` branch still holds the untouched upstream code, and all work is on the
`simplified` branch, one commit per phase.

* **Modified files:** each one carries this line at the top:
  `Modified 2026 for the simplified (academic) fork of changedetection.io - optional features removed, see CHANGES.md`.
* **Exceptions:** two generated files have no header. `static/styles/styles.css` and `diff.css` are compiled from
  the SCSS, and `docs/api_v1/index.html` is built by Redocly from `docs/api-spec.yaml`. They are listed below instead.
* **Unchanged:** `LICENSE`. **Extended:** `NOTICE`, with an addendum only; the upstream text is untouched.
* **Renamed:** the upstream `README.md` is kept, unchanged, as `README.upstream.md`.

Run `git diff --stat upstream-baseline-c74be04 simplified` for the full diff: 762 files deleted, 77 modified
and 8 added.

---

## Phase 0–1: regression harness and config-only simplification (commit `da5185f1`)

Added files:
* `e2e/fixture_server.py`, `e2e/test_e2e.py` and `e2e/run_e2e.ps1` make up the end-to-end harness. It covers
  the 18 core checks plus extended, persistence, security and browser checks.
* `e2e/run_unit.ps1` and `e2e/known_windows_unit_failures.txt` run the retained upstream unit tests. Any failure
  other than the 10 that already fail on Windows with the unmodified code counts as a regression.
* `run.ps1` is the Windows launcher. It binds to 127.0.0.1, never sets `ALLOW_IANA_RESTRICTED_ADDRESSES`, sets
  `DISABLE_VERSION_CHECK=true`, and has an optional `-Browser` switch.

## Phase 2: files nothing imports (commit `994a93e5`)

| Removed | Files |
|---|---:|
| `changedetectionio/example_plugins/` and its `tests/test_example_*.py` | 26 + 6 |
| 15 non-English translations (`cs de es fr id it ja ko pl pt_BR ru tr uk zh zh_Hant_TW`), `UK-translations.txt`, `messages_test.pot`, `tests/test_i18n.py`, `tests/test_language_selector_anonymous.py` | 34 + 2 |
| Docker and CI: `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh`, `.dockerignore`, `.github/` | 19 |
| `docs/*.png, *.jpg, *.jpeg, *.gif`. Kept: `api-spec.yaml`, `api_v1/`, `THIRD-PARTY-LICENSES.md`, `README.md`, `watch-list-export.md` | 17 |

`languages.py` already falls back to `en_GB` when a translation folder is missing, so no code changes were needed.
`MANIFEST.in` no longer lists `example_plugins` or `translations_overlay`.

## Phase 3a: screenshot comparison and PWA (commit `83ff9ce3`)

* **Removed:**
  * `processors/image_ssim_diff/` (the screenshot/visual SSIM processor), `static/js/comparison-slider.js`,
    `diff-image.scss`, `_diff_image.scss` and `diff-image.css`.
  * `blueprint/pwa/` (web manifest, service worker, install QR code, Android share target) and `_pwa_install.scss`.
  * Their tests.
* **Edited:**
  * `edit.html`: the image-processor selection-mode block.
  * `model/App.py`: the `ssim_threshold` default.
  * `processors/__init__.py`: `DISABLED_PROCESSORS` now defaults to `''`.
  * `templates/base.html`: the manifest link and service-worker registration.
  * `settings.html`: the install-QR blocks.
  * `flask_app.py`: blueprint registration and the PWA login-gate exemption.
  * `watchlist/__init__.py`: the share-target prefill.

## Phase 3b: proxy checker, RSS output feeds, translations overlay (commit `38296df9`)

* **Removed:**
  * `blueprint/check_proxies/` and `recheck-proxy.js`, plus the "Check/Scan all" button and its styles. Proxy
    support itself (per-watch proxy, extra proxies, `HTTP_PROXY`, SOCKS) is kept.
  * `blueprint/rss/` (feedgen output feeds). These were authenticated by a URL token and exempt from the login gate.
  * The RSS access tokens (`store/__init__.py`, `model/App.py`), feed icons and links (`base.html`, `edit.html`,
    `groups-overview.html`, `watch-overview.html`), and the output-feed settings (`forms.py`, `settings.html`).
  * `translations_overlay/`. Its loader in `flask_app.py` is a no-op when the folder is missing.
* **Kept:** reading RSS/Atom feeds as watch content (`rss_tools.py`, the `rss_reader_mode` setting). That is part
  of monitoring.
* **Migration:** `store/updates.py` `update_24` now uses a literal `'text'` instead of the removed import, so
  migrations still run.
* **Tests:**
  * Deleted `tests/test_rss*.py` and `test_translation_overlay.py`.
  * Removed the RSS sections from `test_backend.py` and `test_group.py`, and the checker section from
    `proxy_socks5/test_socks5_proxy.py`.
  * `unit/test_store_after_load.py` no longer expects an RSS token.

## Phase 3c: LLM/AI integrations and the MCP server (commit `004ff049`)

**Deleted:**
* Packages and modules: `llm/`, `blueprint/mcp/` (including OAuth), `blueprint/settings/llm/`,
  `model/LLMSettings.py`, `processors/restock_diff/plugins/llm_restock.py` and `mcp_tools.py`.
* Templates: `templates/_mcp-permissions-grid.html`, `templates/edit/include_llm_intent.html`,
  `templates/_stab.html`, `templates/svgs/ai-mode-icon.svg`.
* JS: `llm-summary.js`, `mcp-tokens.js`, `mcp-note.js`, `sub-tabs.js`.
* SCSS: `_llm.scss`, `_mcp.scss`, `_sub_tabs.scss`.
* Images: `ai-infographic.jpg`, `mcp-infographic.jpg`.
* Tests: `tests/llm/`, `tests/test_llm_*`, `tests/test_mcp*`, `test_csrf_llm_summary.py`, `tests/unit/test_llm*`
  and `tests/unit/test_mcp*`.

**Edited.** Only the references to these features were removed; the core logic is unchanged.

| File | What was removed |
|---|---|
| `worker.py` | The AI intent filter and change-summary steps, plus the summary-cache write |
| `forms.py` | The AI settings forms, the MCP forms, the per-watch `llm_*` fields and the LLM `api_base` validator |
| `blueprint/ui/diff.py` | The `/diff/<uuid>/llm-summary*` endpoints and the litellm error helper |
| `blueprint/ui/edit.py`, `views.py`, `tags/__init__.py`, `tags/form.py`, `watchlist/__init__.py`, `settings/__init__.py`, `add_watch_ui/__init__.py` | AI context, form fields and the settings sub-blueprint |
| `notification/handler.py`, `notification_service.py` | The `{{llm_summary}}` and `{{llm_intent}}` tokens. `{{raw_diff}}` is kept as an alias of `{{diff}}` |
| `processors/restock_diff/processor.py` | No LLM intent is passed to plugins and no token counting is done. The plugin hook `get_itemprop_availability_override` is kept, and its `llm_intent` argument is always `None` so existing plugins still work |
| `processors/text_json_diff/__init__.py`, `difference.py` | The LLM preview extraction, the cached summary and the `llm_all_changes` diff preference |
| `pluggy_interface.py` | The `register_mcp_tools` and `register_mcp_permission_rows` hookspecs, and the LLM restock plugin registration |
| `__init__.py` | The litellm pricing-source setup and the restock LLM plugin registration |
| `model/__init__.py`, `Tag.py`, `App.py`, `Watch.py` | The `llm_*` defaults and the summary-cache methods |
| `realtime/socket_server.py` | The `llm_summary_ready` event |
| `validate_url.py` | `is_llm_api_base_safe`, the SSRF guard for the removed LLM endpoint setting. The fetch-path SSRF gate (`is_fetch_url_allowed` → `is_private_hostname`) is unchanged |
| `api/operations.py` | Comments only |
| `docs/api-spec.yaml` | The `llm_*` watch fields. `docs/api_v1/index.html` was regenerated with Redocly 1.34.5 |
| Templates: `base.html`, `menu.html`, `_common_fields.html`, `edit.html`, `diff.html`, `edit-tag.html`, `settings-tabs.html`, `watch-overview.html`, `watch-overview-single-row.html`, `add-watch-ui.html` | All AI/MCP UI: tabs, modal, AI-mode toggle, summary areas and intent boxes. The dashboard History button keeps the restock price-chart roll-down |
| JS: `watch-overview.js`, `watch-settings.js`, `toggle-theme.js`, `global-settings.js`, `plugins.js`, `click-to-copy.js`, `csrf.js`, `add-watch.js` | AI handlers and dead helpers |
| SCSS: `styles.scss`, `_tabs.scss`, `_variables.scss`, `_watch_table.scss`, `_add-watch.scss`, `_edit.scss`, `_restock_graph.scss` | AI selectors. `styles.css` was rebuilt with the project's own sass build (`sass scss:. --style=compressed`), going from 144.6 KB to 106.5 KB |

**Deliberately kept:** the datastore migrations `update_31`, `update_32` and `update_34`. They only reshuffle dict
keys, and they keep datastores written by upstream loading.

**Tests:** removed the LLM summary-cache class from `unit/test_watch_model.py`, and the LLM/MCP helpers from
`tests/util.py`.

## Phase 5: Playwright verified, Selenium and Puppeteer removed (commit `f1531500`)

**Verified first.** The e2e browser phase (B01–B08) drives the Microsoft Edge that ships with Windows over CDP and
covers:
* JavaScript rendering, with a plain-HTTP control fetch for comparison;
* a price injected by JavaScript;
* screenshots;
* visual-selector element data;
* change detection on a JS-rendered page.

**Changes:**
* **Deleted:** `content_fetchers/puppeteer.py` and `content_fetchers/webdriver_selenium.py`.
* **`content_fetchers/__init__.py`:** `html_webdriver` is now always the Playwright fetcher. Playwright is imported
  lazily.
* **`pluggy_interface.py`:** the two fetchers are no longer registered.
* **`forms.py`:** `WEBDRIVER_URL` was removed.
* **`__init__.py`:** the pyppeteer log tweaks were removed.
* **Help texts** (`settings.html`, `edit.html`, `preview.html`) now refer to `PLAYWRIGHT_DRIVER_URL` /
  `run.ps1 -Browser`. The "Not supported by Selenium" note was removed.
* **Tests:**
  * Deleted `unit/test_puppeteer_*.py`.
  * Removed the Puppeteer cases from `unit/test_bypass_csp.py` and `unit/test_secrets_not_in_logs.py`.
  * `tests/test_pdf.py` fetcher-resolution test now uses Playwright plus a stub fetcher that supports PDFs.
* **Added:** `e2e/check_templates.py`, which syntax-checks every Jinja template.

## Phase 6: frontend (commit `ee89b481`)

Language flag images were pruned to `gb` and `us`, shrinking them from 5.1 MB to 132 KB: 536 files.

## Phase 7: dependencies (commit `1f46bc33`)

* **`requirements.txt`:** went from 70 to 57 entries.
  * Removed `litellm` (together with openai, tokenizers, tiktoken, huggingface-hub, boto3, aiohttp and others),
    `mcp-types`, `authlib`, `rank-bm25`, `selenium`, `pyppeteer-ng`, `pyppeteerstealth`, `gevent`, `feedgen` and
    `segno`.
  * Added `playwright`, now the only browser fetcher, and `pillow`. The app uses Pillow for screenshots, but it only
    ever arrived transitively through the LLM stack.
* **Moved to `requirements-dev.txt`:** `pytest`, `pytest-flask`, `pytest-mock` and `pytest-xdist`.
* **Code:** removed the CDP-event `HarRecorder` class from `content_fetchers/har_recorder.py`; only Puppeteer used
  it. Its unit test, which needed `pyee` from pyppeteer, went with it.
* **Added:** `e2e/check_imports.py`, an AST scan of every import, including lazy ones, against the installed
  packages.

## Phase 8: licence notices and documentation

* **Added:** the per-file modification notices (75 files), the `NOTICE` addendum, this file,
  `docs/SIMPLIFICATION_REPORT.md`, and a new `README.md`.
* **Renamed:** the original README is now `README.upstream.md`.

## Phase 9: WebPulse redesign and rebranding

The project is renamed **WebPulse - Automated Web Monitoring and Price Analytics System**. The backend,
algorithms, data model and architecture are unchanged; this phase changes the presentation layer, removes clutter,
and fixes two small front-end bugs.

### New files

| File | What it is |
|---|---|
| `static/styles/scss/webpulse.scss` → `webpulse.css` | The WebPulse design system: tokens for light and dark mode, the app shell, cards, buttons, forms, tabs, table, badges, modals, the sign-in page and responsive layout. It is linked last in `base.html`, so it defines the final look |
| `static/js/webpulse-ui.js` | The mobile navigation drawer, plus the masked-secret control (API key reveal/copy, with a clipboard fallback) |
| `static/images/webpulse-logo.svg`, `webpulse-mark.svg` | Original logo artwork |
| `branding/make_brand_assets.py` | Regenerates the logo, the mark and every favicon from one geometry |
| `demo/seed_demo.py` | Builds the demonstration datastore: live watches on sites that allow scraping, plus paused, clearly labelled sample watches with simulated history |
| `e2e/ui_test.py` | 26 browser UI tests in Microsoft Edge, run with `run_e2e.ps1 -UI` |
| `docs/screenshots/` | Screenshots for the report and presentation |

### Rewritten

These templates are WebPulse originals:
* `templates/base.html`: the shell (sidebar, top bar, page titles), with the CSRF, i18n and Socket.IO script blocks
  and the tab helper kept verbatim;
* `templates/sidebar-nav.html`, the labelled "Monitor" and "Manage" navigation with a live status card;
* `templates/menu.html`, the top-bar actions;
* `templates/login.html`.

### Replaced

All favicons (`static/favicons/*`) and `static/images/avatar-256x256.png` were replaced with WebPulse artwork.
`browserconfig.xml` now uses the WebPulse tile colour.

### Removed from the interface

* The GitHub button, the donation heart, its "support us" overlay (with social and review links), and the
  "Let us host your instance" link.
* The language selector modal and flag, `flag-icons.min.css`, `static/flags/`, and `language-selector.js`. The
  app is English only.
* Version labels, the "new version available" link, and the upstream logo and links in the sidebar.
* The disabled "Browsers – coming soon" menu item, and the three sidebar modes (`sidebar.js`, `hamburger-menu.js`,
  `menu-pop.js`, and the `sidebar_mode` setting).
* Chrome-extension promotions (settings API tab, overlay), the BrightData/Oxylabs affiliate proxy promotions,
  the "extra browsers" (paid scraping browser) section, and the upstream tutorial/wiki/plugins links. Where a
  link carried help text, the text is kept as plain text.
* The "Share diff as image" feature, which loaded html2canvas and piexifjs from a CDN and offered social sharing
  (`snippet-to-image.js`). No external scripts remain.
* The "share watch" button and its setting (`use_share_watch`). It posted watches to an upstream web service.
* Unused images: `brightdata.svg`, `oxylabs.svg`, `spread*.svg`, `copy.svg`.
* SCSS partials: `_top_menu`, `_action_sidebar`, `_hamburger_menu`, `_love`, `_language`, `_extra_browsers`.

### Settings simplified

* **Tabs:** the settings tabs are General, Fetching, Filters, Time & date, Appearance, API, Proxies, Backups and
  About. The RSS tab was removed; its single option (RSS reader mode) moved to Fetching.
* **API tab:** the key is masked by default, with Reveal and Copy buttons.
* **About tab:** the old Info tab is now About, with the open-source attribution and system information.

### Rebranded text

* **Notifications:**
  * The default title is now "WebPulse - change detected - {{watch_url}}", and the alert titles say "WebPulse".
  * The Apprise application identity is WebPulse.
  * The upstream avatar URL (hosted on upstream's GitHub) is no longer attached to chat notifications.
* **Help texts:** they say Chrome/Javascript (Playwright) instead of WebDriver/Selenium.
* **Fresh-install defaults:** the default second watch is the python.org releases page, instead of
  changedetection.io's changelog.

### Bug fixes, both present in upstream too

* `static/js/plugins.js`: `toggleOpacity` and `toggleVisibility` returned early when their checkbox was absent,
  which removed a page error on Settings.
* `static/js/scheduler.js`: the time-zone clock no longer logs an error every 500 ms on pages without a time-zone
  field.

### Modified with notice headers

`settings.html`, `settings-tabs.html`, `edit.html`, `diff.html`, `diff-offscreen-options.html`,
`watch-overview.html`, `watch-overview-single-row.html`, `_common_fields.html`, `_helpers.html`,
`include_subtract.html`, `apprise.html`, `import.html`, `forms.py`, `store/__init__.py`, `notification/__init__.py`,
`notification/handler.py`, `notification/apprise_plugin/assets.py`, `notification_service.py`, `toggle-theme.js`,
`plugins.js`, `scheduler.js`. `styles.css` was regenerated.

## Phase 10: one Home dashboard, simpler navigation, single start command

This phase changes presentation only. Existing endpoints, forms and helpers are reused; no backend logic changed.

* **Home page (`/`), new `blueprint/home`:** one card per feature. Each card has a plain-language explanation,
  live figures from the datastore, worker pool and queue, and direct buttons. The cards are: Website Monitoring,
  Change Detection, Product Price Tracking, Stock Availability, Historical Price Analytics (reuses
  `compute_price_summary`), Static and Dynamic Scraping, Task Scheduling, Workers and Queue, Notifications,
  REST API and Data History.
* **Quick add on Home:** the **Add Website** and **Track Product** buttons post to the existing quick-add
  endpoint, with an optional "needs JavaScript" checkbox that sets `fetch_backend`.
* **Website list:** moved to `/watches/`. `url_for('watchlist.index')` links follow automatically. The duplicate
  quick-add form on the list was replaced with one "Add Website / Track Product" button.
* **Plain labels:**
  * Recheck → Check now, History → View changes / Price history, Preview → View page, and Recheck all → Check
    all now.
  * The processor names and badges are now "Website" and "Product", and "Restock & Price Detection" is now
    "Price & stock".
* **Navigation:**
  * The sidebar is Home, Websites, Products, Notifications, Queue & workers, then Settings.
  * A collapsible **Advanced** group holds Advanced settings, Groups, Import, Visual add, Backups and About.
  * Search moved to the top bar.
* **Settings and edit tabs:** everyday tabs come first, then an "Advanced" label and the technical tabs.
* **Single application:** `run.ps1` starts headless Edge, the internal demo site and WebPulse on port 5000. Ctrl+C
  stops the helpers it started. The separate lab instance on port 5001 is retired.
* **Controlled demo with SSRF protection on:** `demo/add_demo_site.py` works as follows.
  * The `[Demo]` watches use reserved `.test` hostnames and go through one named proxy, "WebPulse demo site
    (simulated)", which is the fixture on 127.0.0.1:8199. It never forwards; it only serves its own canned pages.
    This was verified: requests for WebPulse's own API or 169.254.169.254 through it return the fixture's 404.
  * The system default proxy is "No proxy", so every other watch connects directly.
  * `ALLOW_IANA_RESTRICTED_ADDRESSES` stays off.
* **JS fix:** `watch-overview.js` no longer errors when the list page has no URL field, and URL normalisation
  (example.com → https://example.com) now runs for the Home form in `webpulse-ui.js`.
* **Tests:** `e2e/ui_test.py` was updated for the new layout and gained U27 (11 feature cards) and U28 (every
  card button opens a working page). **89/89** end-to-end checks pass.

## Phase 11: use-case dashboard, Email/Telegram notifications, job listings, real and controlled demos

The goal of this phase is a smaller, plainer interface organised around what people actually monitor, plus honest
demonstration data. The monitoring engine, the processors, the datastore format, the scheduler, the workers and the
REST API are unchanged.

### Interface

* **Navigation.** The sidebar is Home, Websites, Products, Job listings, Notifications, Controlled demo (only when
  the local demo site runs) and Settings. The collapsible "Advanced" menu and the "Queue & workers" item are gone.
  Their pages still exist and are linked from Settings → "More tools" and from Home → "Behind the scenes".
* **Home (`blueprint/home`)** is rebuilt around six use cases:
  * Website Monitoring
  * Product Price Tracking
  * Stock Availability
  * Job Listing Monitoring
  * Historical Price Analytics
  * Notifications

  The scheduler, workers and queue, page reading (plain HTTP or browser), REST API and saved data are now one
  compact "Behind the scenes" row. Items from the controlled demo site carry a "Demo" chip. The analytics card
  prefers a real product to a demo one.
* **Add form on Home:** three buttons, "Watch website", "Track product" and "Track jobs". The optional "More
  options" holds a CSS selector for one part of the page, keywords for job listings and the "needs JavaScript"
  checkbox.
* **Settings.** General holds the check interval, the number of versions kept and the password, plus a "More tools"
  list: Notifications, Groups, Import, Check queue and workers, Backups, Add by pointing, and Delete all history.
  The technical tabs only appear after **"Show technical settings"** (`webpulse-ui.js`; the choice is remembered):
  * Alerts & access: the filter-missing alert, shared history, empty pages and the default proxy;
  * Page reading;
  * Text filters;
  * Time zone;
  * Appearance;
  * Proxies;
  * Backups.

  Every field is still in the form, so nothing is lost when saving.
* **Website edit page.** The tabs are General, Alerts and Check history, plus "Show technical options" for:
  * Page section & filters;
  * Page reading;
  * Pick on the page;
  * Browser steps;
  * Conditions.

  The history length moved into "More options". The per-website notification addresses are an "Advanced"
  section in Alerts.
* **Plain labels** (`forms.py` and the two fetchers):

  | Before | After |
  |---|---|
  | Web Page URL | Web address |
  | Group Tag | Group |
  | Processor - What do you want to achieve? | What should WebPulse look for? |
  | Fetch Method | How to read the page |
  | Basic fast Plaintext/HTTP Client | Read the page directly - fast, for normal pages |
  | Playwright Chromium/Javascript via '…' | Open the page in a real browser - for pages built with JavaScript |
  | Time Between Check | Check every |
  | CSS/JSONPath/JQ/XPath Filters | Only watch this part of the page (CSS, XPath or JSONPath) |
  | Number of fetch workers | Pages checked at the same time (workers) |

  On the list, "Deals" is now "Price drops" and "Healthy" is now "Working". Job-listing monitors get a "Jobs" badge.
* **Bug fixes, all present in upstream too:**
  * `visual-selector.js` no longer throws `getBoundingClientRect` of undefined on edit pages without a screenshot.
  * `blueprint/ui/preview.py`: "View page" for a website with no saved version yet returned HTTP 500
    (IndexError). It now shows "Preview unavailable".
* **Proxy safety (`store/__init__.py`, `get_preferred_proxy_for_watch`).** Upstream falls back to the first proxy
  in the list when no default is set. The demo proxy is now never chosen automatically, so a datastore with the
  demo site configured can never route real websites to it.

### Notifications: Email, Telegram and a kept history

* **New `notification/simple_setup.py`.** It turns a few form fields into the existing Apprise notification URLs,
  and reads them back for display:
  * `mailtos://user:app-password@gmail.com/?to=…`, or a custom SMTP server;
  * `tgram://bot-token/chat-id`.

  "Find my chat ID" asks Telegram's `getUpdates` for the chats that messaged the bot. The host is fixed and the
  token is checked against a strict pattern first. The stored password and bot token are never sent back to the
  browser: a blank field keeps the saved value.
* **New Notifications page (`/settings/notifications/`, `notifications-simple.html`).** It has three parts:
  * Email and Telegram panels, each with "Save and send test", step-by-step help and "Turn off";
  * the notification history;
  * a collapsed "Technical" section with webhook addresses (used by the automated tests) and a link to the message
    wording page.

  The old page at `/settings/notifications/apprise` is kept as "Advanced notification settings".
* **Service picker removed.** The Apprise "add a service" picker (Discord, Slack, Matrix, Pushover, Teams, Home
  Assistant and 140 more) is no longer shown anywhere (`_common_fields.html`). The JSON endpoints behind it and
  Apprise itself are unchanged, so any Apprise URL still works when typed into the advanced address list.
* **New `notification/history.py`.** Every send, whether a change alert or a test, is appended to
  `<datastore>/notification-history.jsonl`, keeping the last 500. Each entry holds:
  * the time;
  * the website;
  * the channel, with the masked destination;
  * the title;
  * delivered or failed, plus the reason.

  Error text is reduced to its warning and error lines. The passwords, bot tokens and URL secrets of the
  notification URLs are replaced by `****`. The in-memory "notification debug log" now gets the same masking.
  Hooks: `flask_app.notification_runner` and `blueprint/ui/notification.py` (test sends).
* **New `format_unix_ts` template filter** for exact local times in the history.

### Job listing monitoring (no new backend)

A job-listing monitor is the normal text watcher (`text_json_diff`) in the group **"Job listings"**. "Track jobs"
(`blueprint/ui/views.py`) puts the new watch in that group and turns on added, removed and changed lines. It then
applies two filters:
* the optional CSS selector, as the existing include filter;
* the optional keywords, as one rule of the existing "Extract text" filter. `job_keywords_rule()` matches whole
  words, so "intern" keeps "Internship" but not "Internal Audit".

The group is created on start-up so the Job listings page is never "everything".

### Controlled demo (`blueprint/demo_lab`, `/demo/`)

* **What it does.** Buttons change the local demo site and then queue an immediate check of the matching demo
  watches:
  * a price drop or price rise;
  * sold out or restocked;
  * publish, change or remove a job;
  * publish a non-technical job, which the keyword filter should ignore;
  * change the news text;
  * reset.
* **What it is.** The page is clearly labelled as a controlled demonstration. It only exists when `run.ps1` sets
  `WEBPULSE_DEMO_SITE`, which must be exactly `http://127.0.0.1:<port>`. Its only outgoing requests are to that
  address (`/set`, `/reset` and `/state.json`). No user input becomes a URL, every action is a CSRF-protected
  POST, and SSRF protection stays on.
* **Demo site (`e2e/fixture_server.py`).** These changes also serve the tests:
  * a careers page, `/jobs.html`, whose visitor counter and clock change on every request to show that a CSS
    filter ignores page noise;
  * a product name and `/state.json`;
  * `/reset`;
  * HTML-escaped output.

  Hardening:
  * `/set` accepts only known keys with bounded, validated values;
  * `slow.html` delays are capped at 10 s;
  * unknown paths get a 404 that names the demo site.

  It still never forwards: CONNECT is unsupported (501), and any host asked for is answered with its own pages.
  New test U34 checks this.
* **`run.ps1`** sets `WEBPULSE_DEMO_SITE` and replaces a demo site left over from an earlier run, so the current
  version always runs.

### Demonstration data, honestly labelled

* **`demo/setup_presentation.py` (new).** It runs while WebPulse is stopped, backs up the datastore first, and is
  safe to run again. It:
  * deletes the "[Sample data]" watches. Their price history was simulated, and the presentation must show only
    history that WebPulse really recorded;
  * removes the once-a-minute demo "clock" page, mutes the concurrency-test pages, and points the demo watches at
    the normal alerts;
  * adds real examples:
    * Indian shops with INR prices, whose robots.txt allows product pages: Decathlon India (plain HTTP and real
      browser), Sleepy Owl and boAt;
    * public job boards: HackerRank on Greenhouse, Meesho on Lever, and the python.org job board, each limited to
      the job list and to technical roles;
    * the demo careers page;
  * sets clear alert wording.
* **`demo/seed_demo.py`** no longer creates simulated history.
* **`demo/add_demo_site.py`** adds the demo careers page, drops the clock page and the blocked `json://` receiver,
  and mutes the concurrency-test pages.
* **Removed:** `demo/lab.ps1`, `lab_control.ps1` and `lab_demo.py`, which drove the retired second instance on
  port 5001. The Controlled demo page replaces them.

### Tests

**Result: 95/95 end-to-end checks** (core 40, persistence 5, security 8, browser 8, UI 34), with 0 errors in the
app logs. Upstream unit tests: 430 passed, 0 new failures. Templates 35/35, imports 52/52.


`e2e/ui_test.py` now covers:

| Test | What it checks |
|---|---|
| U15 | Webhook test from the new Notifications page |
| U23 | Link check over the new pages |
| U27 | The six use-case cards, the "Behind the scenes" row, and no Advanced menu |
| U28 | Every Home button, including the "Behind the scenes" tiles, opens a working page |
| U29 (new) | Technical settings are hidden by default, shown on request and still saved |
| U30 (new) | The notification history is stored in the datastore and shown |
| U31 (new) | The Email/Telegram form builds the right Apprise URLs, never echoes the password or token, keeps the webhook, and can be turned off |
| U32 (new) | "Track jobs": a new job is detected, while a non-technical job and the page's changing counter/clock are ignored; the watch shows under Job listings with its badge |
| U33 (new) | "Drop the price" on the Controlled demo page is detected by WebPulse through the demo proxy |
| U34 (new) | The demo site used as a proxy does not forward to 169.254.169.254 or to WebPulse's API, refuses HTTPS tunnels, and rejects unknown settings |

`run_e2e.ps1` gives the UI instance the demo proxy and `WEBPULSE_DEMO_SITE`, as `run.ps1` does. It also now has
default lists for E19 (8 removed URLs must return 404) and E20 (18 markers of removed UI must be absent, including
the Apprise service picker), so all 40 core checks run without extra arguments. S06 waits until the worker has
recorded the blocked fetch's error; the check could previously race the worker.

### Files

* **Added:**
  * `blueprint/demo_lab/__init__.py` and `blueprint/demo_lab/templates/demo-lab.html`;
  * `notification/history.py` and `notification/simple_setup.py`;
  * `blueprint/settings/notifications/templates/notifications-simple.html`;
  * `demo/setup_presentation.py`;
  * `docs/PRESENTATION_GUIDE.md`.
* **Modified, with notice headers:**
  * Python: `flask_app.py`, `forms.py`, `store/__init__.py`, `blueprint/ui/preview.py`, `blueprint/ui/views.py`, `blueprint/ui/notification.py`,
    `blueprint/home/__init__.py`, `blueprint/settings/notifications/__init__.py`,
    `content_fetchers/requests.py` and `content_fetchers/playwright.py`;
  * templates: `home.html`, `sidebar-nav.html`, `base.html`, `settings.html`, `settings-tabs.html`, `apprise.html`,
    `edit.html`, `_common_fields.html`, `watch-overview.html` and `watch-overview-single-row.html`;
  * JS and SCSS: `visual-selector.js`, `webpulse-ui.js` and `webpulse.scss`. `webpulse.css` was rebuilt with
    sass 1.77.8;
  * scripts: `run.ps1`, `e2e/fixture_server.py`, `e2e/run_e2e.ps1`, `e2e/test_e2e.py`, `e2e/ui_test.py`, `demo/seed_demo.py` and
    `demo/add_demo_site.py`.

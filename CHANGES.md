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

## Phase 12: reliability audit (measured), small fixes

An audit of the running application. Each finding below was measured; nothing was changed on speculation.

### Findings that needed no code change

* **"Checks taking ~444 s".** All three happened at once, on three different workers, and finished within 2 s of
  each other at 10:48:42–44. The Windows System log shows why: the laptop **woke from Modern Standby at 10:41:17
  and went to sleep again at 10:41:20** (Kernel-Power events 507 and 42), then returned at 10:48:41
  (Power-Troubleshooter event 1). The three HTTP requests had started at 10:41:19–20. The process was frozen for
  7 min 20 s, so the reported duration is wall-clock time across the sleep; no timeout could fire while frozen.
  Without sleep, the median check in the same log took 1.7 s. Two more checks of 25–36 s ran during Modern Standby,
  when CPU and network are throttled. Advice: keep the laptop plugged in and stop it sleeping while WebPulse is
  running for a demonstration.
* **Scheduling.** A 10 s interval produced checks exactly 10 s apart (4 gaps, all 10 s).
* **Priority queue.** A manual "Check now" (priority 1) finished in 0.3–0.7 s while six scheduled checks (priority
  = epoch time) kept all three workers busy.
* **Blocking.** Slow pages delay others only while every worker is busy, and only for as long as those pages take.
* **Failure handling.** DNS failure, connection refused, HTTP 404 and timeouts are each recorded as the watch's
  error, and the app keeps serving pages.
* **Persistence.** After a restart, 21 of 21 watches kept the same number of versions, and the price state
  (current, previous, stock) is unchanged.
* **Price statistics.** `compute_price_summary()` matches a hand calculation: mean, quartiles, "cheaper than %" and
  all-time low. Limitation: statistics are per saved version (a version is saved only when the price or stock
  changes), not weighted by time.
* **Security on the live instance.**
  * The API answers 403 without a key or with a wrong key.
  * Pages and API calls that change something need the CSRF token (400 without it).
  * All three services listen on 127.0.0.1 only.
  * Private addresses (127.0.0.1, localhost, 169.254.169.254 and 10.0.0.1) are refused **at fetch time**, as
    upstream designed (the address is re-resolved when fetched). `file://` is refused when the watch is added.
* **Notification credentials.** No password or token appears in the log or the history. Like upstream, they are
  stored unencrypted in `changedetection.json`, protected by the Windows account's file permissions.

### Fixes

* **Network-error retries (`run.ps1` and `e2e/run_e2e.ps1`: `REQUESTS_RETRY_MAX_COUNT=2`).** The plain-HTTP fetcher
  retries network errors 6 times by default, with about 31 s of exponential back-off. Its own comment says 3. A dead
  website therefore held a worker far longer than the request timeout. Measured on a throw-away instance with a 5 s
  timeout:

  | Failure | 6 retries (upstream default) | 2 retries |
  |---|---|---|
  | DNS name does not exist | 31.2 s | 2.0 s |
  | Connection refused | 45.5 s | 8.1 s |
  | Site slower than the timeout | 66.5 s | 16.2 s |

  With the default 45 s timeout, the worst case falls from about 346 s to 136 s per dead site. This uses upstream's
  own setting, so the fetcher code is unchanged. A failed check is retried at the next scheduled interval anyway.
* **Links to websites with one saved version** (`home.html`, `demo-lab.html`, `notifications-simple.html`). The
  change-history page needs two versions and otherwise redirects to the list with "Not enough history". Links now
  open the change page when there are 2 or more versions, and the current snapshot ("View page") before that. New
  UI test U35 checks that every such link answers 200 without a redirect.
* **XXE unit tests (`tests/unit/test_xml_security.py`).** On Windows the payload URI was `file://C:\…`, which lxml
  rejects as invalid, so the XXE protection was never exercised. It now uses `Path.as_uri()`. A control experiment
  confirms that a parser with entity resolution does read the file through the new payload, while WebPulse's
  `xpath_filter` and `xpath1_filter` do not. Both tests now pass, so 8 known Windows failures remain, down from 10.
* **`e2e/known_windows_unit_failures.txt`** now records the verified causes:
  * 5 symlink tests need administrator rights or Windows Developer Mode;
  * 2 tests use the pytest-flask live server, which needs `fork()`;
  * 2 socket-stats tests are outdated **upstream** tests that fail on Linux too: upstream moved the "no browser
    connected" check into `SignalHandler`.

  The old note calling the socket-stats tests "timing dependent" was wrong.

### Result

**96/96 end-to-end checks:**
* core 40;
* persistence 5;
* security 8;
* browser 8;
* UI 35, including the new U35.

There were 0 errors in the app logs. Upstream unit tests: **432 passed** (2 more than before) and 0 new failures;
the 8 remaining Windows failures are listed with their verified causes. Templates 35/35, imports 52/52.

Files: `run.ps1`, `e2e/run_e2e.ps1`, `e2e/ui_test.py`, `e2e/known_windows_unit_failures.txt`,
`changedetectionio/tests/unit/test_xml_security.py`, `blueprint/home/templates/home.html`,
`blueprint/demo_lab/templates/demo-lab.html`, `blueprint/settings/notifications/__init__.py` and
`notifications-simple.html`, `docs/PRESENTATION_GUIDE.md`, and `docs/SIMPLIFICATION_REPORT.md`.


## Phase 13: structured job-listing monitoring

Job monitoring used to be the website watcher with a CSS selector and keywords, so it reported lines of page text.
It is now a dedicated processor, comparable to product price and stock monitoring. Each opening is read on its own
and compared by its job link. The inherited scheduler, queue, workers, fetchers (plain HTTP and Edge, proxies, SSRF
checks), datastore and notifications are reused unchanged.

### The Hevo Data watch

**Symptom:** `https://jobs.lever.co/hevodata` showed the whole page although `.posting-title` was set.

**Measured:** replaying the stored page through the real filter code gave 42 postings and, after the keyword rule, 18
technical roles, so the selector and keywords worked.

**Cause:** the watch's **Trigger text** held `engineer, developer, intern, data, software` as **one line**. A trigger
line has to appear on the page exactly, and that sentence never does. `RuleEngine.evaluate_trigger_text()`
therefore blocked every check. No version after the first was saved, and the first had been taken before the
selector was set, so it was the whole page.

**Fix:**
* the job monitor does not use trigger text;
* the line was removed from that watch after a backup;
* keywords belong in "Only track jobs mentioning…", which splits on commas.

### New: `processors/job_listings`

* **`extract.py`** reads the openings (title, company, location, employment type, team, apply URL). The first
  strategy that matches is used:
  1. Lever;
  2. Greenhouse (current and old boards);
  3. the user's page section (CSS or XPath; a match is a job card, a job link, or a list of jobs);
  4. schema.org `JobPosting` JSON-LD;
  5. automatic job links outside the navigation and footer.

  The id is the canonical job URL (no fragment; tracking parameters removed; job-id parameters kept). The keyword
  rule created by Track jobs is applied to job titles.
* **`tracker.py`** compares and stores the openings:
  * comparisons are set-based, so reordering is not a change and duplicates count once;
  * new / removed / modified (field-level old → new) / re-opened;
  * the first read is the baseline, and changing the selector or keywords starts a new baseline with no alert;
  * the state file is `jobs.json` (atomic writes, bounded size), with a history of events.
* **`processor.py`** ties these into the normal life cycle:
  * a page section that matches nothing, or a page with no openings, becomes the watch's error and never removes
    jobs;
  * a drop to 20 % or less must be seen twice in a row before openings are marked as removed;
  * the saved version is one sorted line per opening, so alerts list new and removed openings with their links.
* **`worker.py`** (inherited, one hook): a baseline version is saved without sending an alert.

### New pages: `blueprint/jobs`

* **`/jobs/`:** one card per careers page, with active / new / removed / changed counts, totals and a
  7-day / 30-day / all-time period.
* **`/jobs/<uuid>`:**
  * openings with the filters All / New / Active / Removed / Modified, a New badge, First detected, Last seen and
    Apply;
  * a step chart of active openings over time (hover for details) and a per-day additions/removals table;
  * the job history in plain words, and a plain-words keyword editor.
* "View changes" on a job watch opens this page; `?raw=1` keeps the inherited text diff.

### Changed

* **Navigation:** the sidebar "Job listings" item and the Home card (now active openings and "new this week") point
  to the new pages; the watch list shows a "Jobs" badge and an "Openings" button.
* **Track jobs** (`blueprint/ui/views.py`) creates a `job_listings` watch and opens its Openings page.
* **Controlled demo:**
  * the demo careers page renders job cards with their own links, locations and types, so "Change a job" is a
    genuine *modified* opening;
  * a new **Reorder the jobs** button shows that reordering is not a change.
* **`demo/setup_presentation.py`:** creates job watches with the new processor and converts older careers-page
  watches.

### Tests

* **Unit:** `tests/unit/test_job_listings.py`, 21 tests.
* **e2e core J01–J17:**
  * the real Track jobs form, baseline, fields and the Openings page;
  * new opening and alert; reordering; a duplicate and a non-technical job;
  * modified, removed, an empty-list failure and its recovery;
  * keyword re-baseline; the redirects; bad parameters.
* **e2e persist P06–P07:** after a restart.
* **U32:** updated for the Openings page; `/jobs/` was added to the broken-link crawl.
* **Results:** e2e **115/115**, 0 unexpected app-log errors (one run had a one-off Socket.IO "data frame after close"
  console message on `/demo/`, not reproduced in the next full run). Unit tests: 453 passed, 0 new failures.

**Real boards, first structured read (26 Nov, 15:59):**

| Board | Read as | Openings on the page → kept by keywords |
|---|---|---|
| Hevo Data | Lever | 42 → 18 |
| Meesho | Lever | 49 → 10 |
| HackerRank | Greenhouse | 32 → 17 |
| python.org | page section | 22 → 22 |

**Live data:** the five careers-page watches were converted with WebPulse stopped, after a backup. Upstream keeps a
separate version index per processor, so their old text versions remain on disk (`history.txt`) but are not shown
while the watch is a job monitor.

**Files:**
* new:
  * `processors/job_listings/{__init__,extract,tracker,processor}.py`;
  * `blueprint/jobs/__init__.py` and its templates `jobs-overview.html` and `jobs-detail.html`;
  * `tests/unit/test_job_listings.py`;
* changed:
  * `worker.py`, `flask_app.py`, `blueprint/ui/diff.py`, `blueprint/ui/views.py`;
  * `blueprint/home/__init__.py` and `home.html`;
  * `blueprint/demo_lab/__init__.py` and `demo-lab.html`;
  * `watch-overview-single-row.html`, `templates/base.html`, `templates/sidebar-nav.html`;
  * `static/styles/scss/webpulse.scss` and `webpulse.css`;
  * `e2e/fixture_server.py`, `e2e/test_e2e.py`, `e2e/ui_test.py`, `demo/setup_presentation.py`;
  * the docs.

## Phase 14: complete functional audit and real-world data expansion

Every feature was re-verified by running it (live app, throw-away instances, browser automation). The full report is
`docs/COMPLETE_FUNCTIONAL_AUDIT.md`.

### Bugs found and fixed

* **Greenhouse "New" tag inside job titles** (`processors/job_listings/extract.py`). Greenhouse boards put a
  temporary `<span class="tag-container">New</span>` inside the title, so "Lead Software Development Engineer" was
  read as "... Engineer New". When Greenhouse later drops the tag, the title would have looked *modified* (a false
  change). The tag is now excluded. One stored HackerRank title from Phase 13 had the suffix and was repaired.
* **A Lever board with no openings read as one fake opening.** Its `.postings-wrapper` was not recognised as Lever,
  so automatic mode turned the page text into an "opening". Lever is now recognised by `.postings-wrapper` too, and
  automatic mode only accepts real job links.
* **Uncaught "Transport not open" JavaScript error on every page navigation** (`static/js/realtime.js`, inherited).
  `socket.disconnect()` in `beforeunload` throws when the Socket.IO connection is still being set up; it is now
  guarded.
* **Controlled demo:** removing the last demo job did nothing (the demo site ignores an empty value); it now sends
  an explicit empty list.

### Improved (from the Phase 13 known limitation)

* **Confirmed empty job boards** (`extract.confirmed_empty`, processor): zero openings are accepted only on an
  explicit signal:
  * Lever's `.no-postings-message`, seen on a real board ("No job postings currently open. Check back later!");
  * Greenhouse's count header "0 jobs";
  * or a "no open positions" message inside the selected page section.

  Anything else is still an error that keeps every opening, and the two-checks rule for big drops still applies.
  The board's own stated total (Greenhouse "N jobs") is recorded and shown next to the number read.
* **SmartRecruiters boards** (e.g. Freshworks) are read with location, employment type and canonical job links.
* **Controlled demo:**
  * a **Block the careers page / Unblock** button shows that a failed read removes nothing;
  * the demo careers page shows "No open positions" when it is empty;
  * the demo product page has a `product_page=broken` test mode.

### Tests

* **Unit:** 4 new tests (Greenhouse tag, SmartRecruiters, confirmed-empty signals, empty-board drop rules).
* **e2e:**
  * J12 now uses a blocked page;
  * new **J18** (confirmed empty board), **J19** (re-opened openings) and **J20** (last-seen timestamps and chart
    counts).
* **Results:** e2e **118/118**; unit **457 passed**, 0 new failures. The 8 known Windows-only failures were
  re-checked against the actual output, and the recorded causes were corrected in
  `e2e/known_windows_unit_failures.txt`: 4 symlink tests, not 5, and the fetch-gate test is a Linux-only SSRF
  exception, not the live server.

### Real-world data (live instance, after backups)

33 real watches were added after discovery and validation (robots.txt honoured, no CAPTCHA bypass, no paid service):
* **4 websites:** UGC notices (XPath), GitHub Changelog, Python Insider (CSS + regex), The Hindu technology;
* **19 products** from Decathlon, IKEA India, boAt, Sleepy Owl, Mokobara, Bombay Shaving Company and Noise;
* **10 career boards:** HighLevel, Zeta, Mindtickle, CRED, Paytm, Razorpay, Groww, InMobi, Zenoti and Freshworks.

**Files:**
* `processors/job_listings/{extract,processor,tracker}.py`;
* `blueprint/jobs/templates/jobs-detail.html`;
* `blueprint/demo_lab/__init__.py` and `templates/demo-lab.html`;
* `static/js/realtime.js`;
* `e2e/fixture_server.py`, `e2e/test_e2e.py`, `e2e/known_windows_unit_failures.txt`;
* `tests/unit/test_job_listings.py`;
* `docs/COMPLETE_WALKTHROUGH.md`, `docs/COMPLETE_FUNCTIONAL_AUDIT.md`.

## Phase 15: final readiness and engineering audit

The full report is `docs/FINAL_PROJECT_READINESS.md`. New documents:
* `SYSTEM_ARCHITECTURE.md` (9 Mermaid diagrams);
* `INSTALLATION_GUIDE.md`;
* `DEMONSTRATION_SCRIPT.md`;
* `KNOWN_LIMITATIONS.md`;
* `ORIGINAL_CONTRIBUTIONS.md`.

### Fixes

* **Browser SSRF** (`content_fetchers/playwright.py`, inherited). Only the start URL was checked, so a page that
  redirected to, or `fetch()`ed, a private address (127.0.0.1, 10.x, 169.254.169.254) had that content saved.
  * Every browser request now goes through the private-address check (`_install_private_address_guard`, cached per
    host).
  * A redirect hop into a private address fails the fetch, and nothing is saved.
  * New check `e2e/ssrf_redirect_test.py` (S09–S12), run with `-Browser`.
* **Incomplete product readings** (`processors/restock_diff/processor.py`, inherited):
  * a check without a price no longer wipes the stored price (that made the next price change be missed);
  * a check without stock data is no longer a stock change (that produced two false alerts).

  New e2e checks R01–R04.
* **`run.ps1`:**
  * refuses a second instance on the same port or data folder, with clear messages (before, a second copy ran on the
    same data folder and replaced the first one's demo site);
  * clear errors for a missing Python, Edge or a busy demo port;
  * stops headless Edge by its per-port profile on exit (it was left running);
  * portable defaults (`%USERPROFILE%` data folder, `<project>\.venv` Python).
* **Retry setting** (`content_fetchers/requests.py`): an empty `REQUESTS_RETRY_MAX_COUNT` no longer breaks every
  plain-HTTP fetch.
* **Phones** (`webpulse.scss`): the watch-type badge is no longer overlapped by the stock badge, and cards fit the
  screen.
* **Empty lists** (`watch-overview.html`): the messages now point to Home and distinguish "nothing matches this
  filter" from "nothing monitored yet".
* **Tests:**
  * a J14 race (a late alert from the previous step was counted) is fixed;
  * `run_unit.ps1` says when pytest produced no summary;
  * the test runners locate Python like `run.ps1`;
  * an unused import is removed.

### Demo site (`e2e/fixture_server.py`)

New test modes:
* `http_status=403|404|429|500|503`;
* `product_page=malformed|noprice|nostock|broken`;
* `/redirect` and `/fetch-private.html` (SSRF tests; only 127.0.0.1 targets accepted).

### Results

* e2e **126/126** (Phase 14: 118), also 126/126 on a clean venv installed from `requirements.txt` (91 s);
* unit 457 passed, 0 new failures;
* data audit 13/13; reliability 20/20; XSS 0 executions on 13 pages;
* pip-audit: 0 known vulnerabilities in 119 packages;
* load: 1,000 local watches in 17.3 s (3 workers) / 10.3 s (10 workers), 106 MB.

No watch was recreated and no history was deleted.

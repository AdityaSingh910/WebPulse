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

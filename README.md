<p align="center"><img src="changedetectionio/static/images/webpulse-logo.svg" alt="WebPulse" width="236" height="64"></p>

# WebPulse: Automated Web Monitoring and Price Analytics System

WebPulse is a final-year engineering project. It watches web pages for changes, tracks product prices and stock,
keeps a price history with analytics and charts, checks pages on a schedule with concurrent workers, sends
notifications, and exposes a REST API. Everything runs locally on Windows, with no Docker, no WSL and no paid
services.

![WebPulse dashboard](docs/screenshots/01-dashboard.png)

## Based on changedetection.io

WebPulse is a modified and simplified version of the open-source
**[changedetection.io](https://github.com/dgtlmoon/changedetection.io)**, by Leigh Morresi and the changedetection.io
contributors, version 0.70.4, used under the Apache License 2.0.

* [LICENSE](LICENSE) is unchanged.
* [NOTICE](NOTICE) contains the upstream notice plus an addendum for this project.
* Every change is recorded in [CHANGES.md](CHANGES.md), and modified files carry a notice at the top.
* The original README is kept as [README.upstream.md](README.upstream.md).
* The WebPulse name, logo and interface design are original to this project. WebPulse is not affiliated with or
  endorsed by the changedetection.io project.

## Features

| Feature | What you get |
|---|---|
| Website monitoring and change detection | Text and JSON change detection, side-by-side differences, and CSS/XPath/JSONPath filters, triggers and ignore rules |
| Web scraping | A fast plain-HTTP fetcher, plus a JavaScript browser fetcher (Playwright driving the Microsoft Edge that ships with Windows) |
| Price and stock monitoring | Prices and availability from schema.org JSON-LD, microdata or a CSS selector, with price-change thresholds |
| Historical price analytics | A price/stock chart, average, all-time low, "cheaper than N % of tracked prices", and XLSX export |
| Scheduling and concurrency | Per-watch intervals, weekly time windows, and parallel async workers with a live activity graph |
| Notifications | Email, Discord, Telegram, Slack, webhooks and 140+ more through Apprise (all free) |
| REST API | `/api/v1/*` with an API key (masked in Settings, with reveal and copy) and OpenAPI validation |
| Data persistence | A plain-file datastore, backups, and import of URL lists |
| Interface | Responsive light and dark design, groups, search, and password protection |

## Run it (Windows)

```powershell
# one-time setup (Python 3.11+)
py -3.12 -m venv C:\Users\<you>\venvs\cdio-simplified
C:\Users\<you>\venvs\cdio-simplified\Scripts\python.exe -m pip install -r requirements.txt

# optional demo data (run once, while WebPulse is stopped)
C:\Users\<you>\venvs\cdio-simplified\Scripts\python.exe demo\seed_demo.py C:\Users\<you>\cdio-data\webpulse-demo
C:\Users\<you>\venvs\cdio-simplified\Scripts\python.exe demo\add_demo_site.py C:\Users\<you>\cdio-data\webpulse-demo

# ONE command starts everything: headless Edge, the internal demo site and WebPulse
.\run.ps1                   # then open http://127.0.0.1:5000  (Ctrl+C stops everything it started)
.\run.ps1 -NoBrowser -NoDemoSite -Datastore D:\data\webpulse -Port 5001
```

Open **http://127.0.0.1:5000**. The Home page has one card per feature, with buttons to try each one.
Everything binds to `127.0.0.1` only, and SSRF protection stays on.

### Demonstration data, clearly labelled

| In the list | What it is |
|---|---|
| Normal titles, groups ending in "(live)" | **Real websites**: scraping sandboxes (`books.toscrape.com`, `quotes.toscrape.com`, `webscraper.io/test-sites`), Hacker News and python.org, checked every 6–12 hours |
| `[Demo] …`, group "Demo site (simulated)" | **Controlled local demo site.** Price, stock and text can be changed on purpose. Reached only through the "WebPulse demo site" proxy, which never forwards |
| `[Sample data] …`, group "Sample data (simulated)" | **Simulated history** so the charts have data on day one. Paused, and pointing at `example.com` |

## Tests

```powershell
.\e2e\run_unit.ps1               # upstream unit tests + template syntax + dependency/import checks
.\e2e\run_e2e.ps1 -Browser -UI   # 89 end-to-end checks
```

The 89 end-to-end checks are:
* 40 core and extended API checks;
* 5 persistence checks;
* 8 security checks: SSRF, password, CSRF;
* 8 checks of the JavaScript browser fetcher;
* 28 interface tests that click through the real UI in Microsoft Edge.

The harness starts its own local fixture site and throw-away instances. More detail is in
[docs/SIMPLIFICATION_REPORT.md](docs/SIMPLIFICATION_REPORT.md), and screenshots are in
[docs/screenshots](docs/screenshots).

# Website Change & Price Monitor (simplified fork of changedetection.io)

This is a simplified version of the open-source **[changedetection.io](https://github.com/dgtlmoon/changedetection.io)**
by Leigh Morresi and the changedetection.io contributors, licensed under the Apache License 2.0. It was made for a
final-year engineering project.

The fork keeps the core monitoring application and removes optional, advanced features: LLM/AI, the MCP server,
screenshot comparison, PWA, RSS output feeds, the proxy checker, the Selenium/Puppeteer fetchers, and extra
translations. No replacement features were written. See [CHANGES.md](CHANGES.md) for every modification, and
[docs/SIMPLIFICATION_REPORT.md](docs/SIMPLIFICATION_REPORT.md) for before/after measurements, test results,
known limitations and the architecture.

* **Licence:** [LICENSE](LICENSE) (Apache-2.0, unchanged) and [NOTICE](NOTICE) (upstream notice plus a fork
  addendum).
* **Upstream README:** kept as [README.upstream.md](README.upstream.md).
* **Branding:** the changedetection.io name and logo belong to the upstream project and are not licensed.

## Features kept

* **Website monitoring and change detection:** text and JSON diffs, CSS/XPath/JSONPath filters, trigger and ignore
  text, and conditions.
* **Web scraping:** a fast plain-HTTP fetcher, plus a JavaScript browser fetcher (Playwright driving the Microsoft
  Edge that ships with Windows).
* **Product price and stock monitoring:** read from schema.org JSON-LD and microdata, with price-change thresholds.
* **Price history:** a price/stock chart, average, all-time low, "cheaper than N % of tracked prices", and XLSX
  export.
* **Scheduling and concurrency:** per-watch intervals, weekly time windows, and parallel async workers.
* **REST API:** `/api/v1/*` with an API key, OpenAPI-validated.
* **Dashboard:** groups/tags, history, preview, queue view, and live status over Socket.IO.
* **Notifications:** through Apprise (email, Discord, Telegram, Slack, webhooks and more; all free).
* **Data persistence:** a plain-file datastore with backups and import.

## Run it (Windows, no Docker)

```powershell
# one-time setup (Python 3.11+)
py -3.12 -m venv C:\Users\<you>\venvs\cdio-simplified
C:\Users\<you>\venvs\cdio-simplified\Scripts\python.exe -m pip install -r requirements.txt

# start: http://127.0.0.1:5000
.\run.ps1                    # plain HTTP fetcher
.\run.ps1 -Browser           # + headless Microsoft Edge for JavaScript-heavy pages
.\run.ps1 -Port 5001 -Datastore D:\data\monitor -Python <path to venv python.exe>
```

`run.ps1` binds to `127.0.0.1` only and keeps SSRF protection on. The datastore defaults to a folder outside
OneDrive. The API key is in **Settings → API**.

## Tests

```powershell
.\e2e\run_unit.ps1           # upstream unit tests + template syntax + import checks
.\e2e\run_e2e.ps1 -Browser   # 61 end-to-end checks: core, extended, persistence, security, browser
```

The e2e harness starts its own local fixture site and throw-away app instances on ports 5055–5057 and 8099. Only
those throw-away instances use `ALLOW_IANA_RESTRICTED_ADDRESSES=true`, so they can reach the fixture on
127.0.0.1. The upstream integration tests in `changedetectionio/tests/*.py` need Linux (`fork()`); see the report.

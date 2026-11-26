# WebPulse: demonstration script (about 15 minutes)

## Before you start (the day before)

* Keep the laptop **plugged in** and set sleep to "Never". A sleeping laptop pauses monitoring.
* Start WebPulse with `.\run.ps1` and leave it running, so genuine changes can accumulate. Put the backend window
  beside the browser.
* Optional: set up Email or Telegram on **Notifications** (your own Gmail app password / bot token) and press
  **Save and send test**. Real delivery has not been verified in testing.
* Know which data is which:

  | Data | How to recognise it | What it shows |
  |---|---|---|
  | **Real** | normal titles, groups "… (live)" and "Job listings" | genuine sites, genuine history |
  | **Controlled** | `[Demo]` titles, green "Demo site (simulated)" tag, "Demo" chip | changes made on demand by the Controlled demo page |
  | **Public test sites** | books.toscrape, quotes.toscrape, webscraper.io | sites built for scraping practice |

  Never present a controlled change as a real one.

## The script

| # | Time | Where | What to do | What to point out |
|---|---|---|---|---|
| 1 | 1 min | **Home** | scroll the six use-case cards | live counts: careers pages, **171** active openings, products in/out of stock; "Behind the scenes" row |
| 2 | 2 min | **Websites** → *The Hindu – technology headlines* → **View page**; *UGC*; *Python Insider* | show the extracted text | CSS (`h3.title a`, 20 headlines), **XPath** (UGC, 40 notices), **CSS + regex** (Python Insider, only release posts) |
| 3 | 1 min | same row → **Check now** | watch the backend window | `Previous MD5: X, Fetched MD5 X`: identical, so **no new version** is stored (MD5 change detection) |
| 4 | 1.5 min | **Websites** → *Hacker News – front page headlines* → **View changes**; *Wikipedia* | genuine history | red = removed, green = added; the versions have real timestamps (Wikipedia changes hourly) |
| 5 | 2 min | **Products** | pick *Decathlon – Battery Head Torch* (₹799, in stock) and *boAt Aavante Bar Plus* (₹9,999, out of stock) | open the shop with the link icon: the **selling price**, not the MRP; stock comes from the shop's own data. 22 products from 7 retailers. The Decathlon gilet is watched twice (plain HTTP 1.1 s vs browser 9.6 s, same ₹799) |
| 6 | 2 min | **Controlled demo** → **Drop the price**, **Sell out**, **Restock** | then open *[Demo] Wireless earbuds* → **Price history** | new points on the chart; min / max / average / median, "cheaper than N %"; **Download as XLSX**. Say clearly: *this is the demo site* |
| 7 | 2 min | **Job listings** → *HighLevel* or *Hevo Data* | filters All / New / Active / Removed / Modified; **Apply** | each opening is read separately (title, location, type, link); identity = job link; first read = starting point (no fake "new"); the Greenhouse boards show "the board itself says N" next to the number read |
| 8 | 2 min | **Controlled demo** → job buttons | **Publish a new job** → Openings shows **New**; **Reorder** → nothing; **Non-technical job** → ignored; **Change a job** → Modified (old → new location); **Remove a job** → Removed; **Block the careers page** → error, every job kept → **Unblock** | the five rules: reorder ≠ change, keywords filter, field-level modifications, removals recorded with time, failed reads never remove jobs |
| 9 | 1 min | **Home → Workers and queue**, then **Websites → Check all now** | watch the queue drain live | 3 workers, priority queue (manual checks first), Socket.IO live updates with no reload |
| 10 | 1 min | backend window: **Ctrl+C**, then `.\run.ps1` | reload the browser | everything is still there (atomic JSON + Brotli files); `run.ps1` stopped Edge and the demo site too. A second `.\run.ps1` while one is running is refused with a clear message |
| 11 | 0.5 min | **Settings → API**, then in a terminal: `curl.exe -H "x-api-key: <key>" http://127.0.0.1:5000/api/v1/systeminfo` | | 200 with the key; 403 without it |
| 12 | 0.5 min | the moon/sun button; resize the browser to phone width | | dark mode; the phone layout |

## Questions you may be asked (and the honest answers)

* **"Did a real price drop happen?"** Only if one happened while it was running. Show the history timestamps.
  Otherwise say the change on screen comes from the controlled demo.
* **"What if the shop blocks you?"** The check records the error (403/429/500) and keeps the last valid price and
  stock (tested). There is no CAPTCHA bypass.
* **"Is it secure?"**
  * everything listens on 127.0.0.1 only;
  * SSRF protection checks every redirect hop, including in the browser (fixed in Phase 15);
  * CSRF tokens; the API key; Jinja escaping (XSS tested);
  * dependency audit: 0 known vulnerabilities on 26 Nov 2026.

  This is not a production penetration test.
* **"How far does it scale?"** Measured: 1,000 local watches checked in 17 s with 3 workers, 106 MB of RAM.
  Real websites are limited by network latency and politeness, not by CPU (`docs/FINAL_PROJECT_READINESS.md` §7).
* **"What did you build yourself?"** `docs/ORIGINAL_CONTRIBUTIONS.md`.

## If something goes wrong

| Problem | Fallback |
|---|---|
| Internet down | the Controlled demo works fully offline; show the recorded history |
| A real site shows an error | it is real-world behaviour: show the error text and that the last data was kept |
| WebPulse window closed | run `.\run.ps1` again; it refuses to start twice and explains why |

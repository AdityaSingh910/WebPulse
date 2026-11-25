# WebPulse: walkthrough and presentation guide

This guide is for the person presenting WebPulse. It covers what each example monitors and why it was chosen,
what to click, and how to show genuine changes as well as on-demand changes during a live presentation.

## 1. Start

```powershell
cd C:\Users\adity\OneDrive\Desktop\Solo_College_Project\changedetection.io
.\run.ps1
```

Open **http://127.0.0.1:5000**. One command starts three things:
* WebPulse;
* a hidden Microsoft Edge, for pages built with JavaScript;
* the local demo site.

Press Ctrl+C in that window to stop all three.

Leave WebPulse running in the days before the presentation. Every real change it detects in that time is saved
with its date and time, and you can show it immediately.

## 2. Two kinds of demonstration, never mixed up

| | Real websites | Controlled demonstration |
|---|---|---|
| What | Public shops, careers pages and job boards on the internet | WebPulse's own small demo site on this computer |
| Changes happen | When the website changes, which you can't predict | When you press a button on the **Controlled demo** page |
| How to recognise it | Normal titles; groups "Indian shops (live)", "Job listings", "… (live)" | Title starts with `[Demo]`, a **Demo** chip, and the group "Demo site (simulated)" |
| History | Only what WebPulse really recorded, with timestamps | Recorded the same way, but the changes were made on purpose |

No history is invented. The old "[Sample data]" watches with simulated price history were deleted
(`demo/setup_presentation.py` made a backup first).

## 3. The real examples

First real check by WebPulse on 25 Nov 2026. The values are what the sites published at that moment.

**Products (Indian shops, INR)**

| Website and product | Why it was chosen | Extracted on the first check | How it is read | Checked every |
|---|---|---|---|---|
| Decathlon India: Forclaz 200 men's hiking fleece gilet<br>`https://www.decathlon.in/p/8189216/men-mountain-hiking-warm-fleece-gilet-jacket-black` | A large Indian retailer. robots.txt allows `/p/` product pages (without `?`). The page publishes schema.org price and stock | Name "Forclaz 200 Men Hiking Gilet Black", **₹799**, **in stock** | Directly (plain HTTP) | 12 hours |
| The same Decathlon product, a second watch | Shows that the real browser (Edge) reads the same data | **₹799**, **in stock** | Real browser (JavaScript) | 24 hours |
| Sleepy Owl Coffee: enamel mug<br>`https://sleepyowl.co/products/enamel-mug` | An Indian D2C brand on Shopify. robots.txt allows `/products/` | Name "Coffee Enamel Mug 350ML", **₹564**, **out of stock** (the shop's own data says `OutOfStock`), so a genuine restock alert is possible | Directly | 24 hours |
| boAt Stone 650 Bluetooth speaker<br>`https://www.boat-lifestyle.com/products/stone-650` | A popular Indian electronics brand on Shopify. robots.txt allows `/products/` | Name "boAt Stone 650", **₹1,999**, **out of stock** per the shop's data | Directly | 24 hours |

boAt sometimes shows a "verify your connection" bot check when it gets several requests in a short time. WebPulse
does not try to get past it: that check simply records an error, and the next one tries again a day later. The
sandbox shops `books.toscrape.com` (GBP) and `webscraper.io` (USD), which explicitly allow scraping, are still
watched too.

**Job listings (group "Job listings")**

| Source | Why it was chosen | What is extracted | Filters | Checked every |
|---|---|---|---|---|
| HackerRank careers on the Greenhouse public job board<br>`https://job-boards.greenhouse.io/hackerrank` | Bangalore tech roles. A public job board meant to be read; robots.txt allows it | 17 job titles on the first check, e.g. "Senior Backend Engineer", "Lead Data Engineer", "DevOps Engineer II" | Only `.job-post` (the job list); only lines with engineer / developer / software / backend / data / python / intern / sde | 12 hours |
| Meesho careers on the Lever public job board<br>`https://jobs.lever.co/meesho` | A large Indian e-commerce company. robots.txt allows `User-agent: *` | 10 technical titles out of about 48 jobs, e.g. "Data Scientist III", "Engineering Manager - Platform" | Only `.posting-title`; same keywords | 12 hours |
| Python.org job board<br>`https://www.python.org/jobs/` | Python/backend jobs worldwide, updated several times a week. robots.txt allows it | 22 jobs (title and location), e.g. "Senior Image Analysis Software Engineer - Detroit" | Only the job list (`.list-recent-jobs h2 a`) | 6 hours |

**Other real pages:**
* Python releases page;
* Hacker News, which changes many times an hour, so its alerts are muted;
* "Quotes to Scrape", watched twice: plain HTTP versus browser.

**Where to click:**
* **Products** → a row: price, stock and "Price history" (the chart);
* **Job listings** → a row: "View page" (the current jobs) and "View changes" (what changed and when);
* **Notifications** → **Notification history**.

**How changes are detected.** On every check WebPulse fetches the page, either directly or through Edge.
* **Products:** the price and availability are read from the schema.org data the shop publishes for search
  engines. A different price or stock state saves a new version, adds a point to the price chart, and sends an
  alert.
* **Websites and job lists:** WebPulse first applies the filters:
  * the CSS selector keeps only one part of the page, for example the job list;
  * the keyword rule keeps only technical roles.

  It then compares the remaining text with the previous version. Added, removed or changed lines save a new
  version and send an alert.

**How alerts are sent.** Each new version queues an alert to the Email and Telegram set up on the Notifications
page. The result, delivered or failed, is added to **Notifications → Notification history**.

**Being a good citizen.**
* Each page is checked at most every 6–24 hours.
* Only pages that robots.txt allows are used.
* Nothing logs in.
* Nothing tries to get around CAPTCHAs or bot checks. If a shop shows a "verify you are human" page, WebPulse
  records an error for that check, and the next scheduled check tries again.
* Amazon.in and Flipkart were not used, because their robots.txt and terms forbid automated access.

## 4. Notifications (do this once, before the presentation)

### Email (Gmail)

1. In your Google account, open **Security** and turn on **2-Step Verification**.
2. Open **myaccount.google.com/apppasswords**, type "WebPulse" and press **Create**. Copy the 16-letter password.
3. In WebPulse, open **Notifications**. Enter your Gmail address and the app password, then press
   **Save and send test**. Leave "Send alerts to" empty to send to yourself.
4. Check your inbox and the spam folder. The history shows "Delivered to the service".

### Telegram

1. In Telegram, search for **@BotFather** (blue tick), press Start, and send `/newbot`. Choose a name and a
   username that ends in "bot". Copy the token.
2. Open your new bot, press **Start** and send "hi".
3. In WebPulse, open **Notifications**. Paste the token, press **Find my chat ID**, then press
   **Save and send test**.

Both are free. The password and the token are stored only in the WebPulse data folder on this computer, and they
are never shown again or written to a log. Do not paste them into chats or documents. If one leaks, delete the app
password at Google, or send `/revoke` to BotFather.

## 5. Suggested presentation order (about 10 minutes)

1. **Home.** Show the six cards, each of which is one use case, and point out "Behind the scenes" (scheduler,
   workers, page reading, API, saved data).
2. **Real price tracking.** Open **Products** and click a Decathlon / Sleepy Owl / boAt row. Show the price, the
   stock state, "Last checked", and the price chart once there are two or more points.
3. **Static and JavaScript reading.** The same Decathlon product is watched twice: once read directly and once with
   a real browser. Both give the same price. For a page that only a browser can read, open "Quotes to Scrape -
   JavaScript page via plain HTTP" (no quotes) next to "… JavaScript-rendered page" (quotes visible).
4. **Real job listings.** Open **Job listings** and then a careers page. "View page" shows the extracted job list
   (titles only, technical roles only). If a real change was recorded in the past days, show it in
   **View changes**, with its date and time.
5. **Controlled demo, live.** Open **Controlled demo**:
   1. Press **Drop the price**. A few seconds later the new price appears, and an email/Telegram message arrives.
      Open "Price history" to show the new point in the chart.
   2. Press **Sell out**, then **Restock**. Each one sends an alert.
   3. Press **Publish a new job**. The new job appears in "View changes" (green) and an alert is sent.
   4. Press **Publish a non-technical job**. No alert is sent, because the keyword filter ignores it. The careers
      page's visitor counter and clock change on every visit, and WebPulse ignores those too.
   5. Press **Remove a job** or **Change a job**. These show up in red, or red and green.
6. **Notifications → Notification history.** Every message sent is listed, with time, website, channel and result.
7. **Settings.** Point out how little is visible, and that "Show technical settings" reveals the rest: page
   reading, proxies, filters, REST API and backups.

**If the internet fails during the presentation:**
* the Controlled demo still works fully, because it runs on this computer, except that alerts need the internet
  to reach Gmail/Telegram;
* all previously recorded real history can still be shown.

## 6. Commands

```powershell
.\run.ps1                                              # start everything
.\e2e\run_e2e.ps1 -Browser -UI                         # all end-to-end tests (throw-away instances)
.\e2e\run_unit.ps1                                     # upstream unit tests + template/import checks
# re-run the presentation set-up (WebPulse stopped; makes a backup first)
C:\Users\adity\venvs\cdio-simplified\Scripts\python.exe demo\setup_presentation.py C:\Users\adity\cdio-data\webpulse-demo
```

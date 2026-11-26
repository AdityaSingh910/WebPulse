# WebPulse: complete functional audit and real-world data expansion

**Date:** 26 Nov 2026 (IST)

**Starting point:** commit `bb209b8f` (Phase 13)

**Scope:** every feature, verified by running it:
* the live app at http://127.0.0.1:5000;
* throw-away instances on other ports for anything that changes data or needs controlled conditions;
* Microsoft Edge driven by Playwright for the browser checks.

Nothing on this page is copied from earlier reports without being re-run, except where the text says so explicitly.

> **Genuine versus controlled.**
> * **Baseline:** the first real reading of a site.
> * **Controlled test:** a change WebPulse's own demo site makes on demand.
> * **Genuine change:** a real site changing by itself.
>
> These three are always reported separately. During the audit the only genuine change observed was the Wikipedia
> main page (a new version at 16:04:43). **No genuine retailer price or stock change, and no genuine new, removed or
> changed job opening, was observed.** All price, stock and job changes below come from controlled tests.

---

## 1. Executive summary

| Item | Result |
|---|---|
| Real watches now monitored | **53**: 12 websites, 27 product watches (22 distinct real Indian products, 7 retailers, plus 4 sandbox products and 1 product read two ways), 14 real career boards |
| Controlled demo watches | 9 (labelled "[Demo]", group "Demo site (simulated)") |
| Total watches | **62**: 28 `restock_diff`, 19 `text_json_diff`, 15 `job_listings` |
| Real-site baselines | all 53 real watches checked successfully: HTTP 200, no error |
| Product prices independently checked | 22/22. Shopify stores against the store's own product JSON; Decathlon and IKEA against the price displayed on the page. Always the **selling price, not the MRP** |
| Job openings tracked | **171** active relevant openings; 13/13 sampled apply links open the right job |
| Controlled product tests | **17/17** (decrease, increase, out of stock, restock, min/max, % threshold, statistics against an independent calculation, broken page, Excel) |
| Backend measurements | **11/11** (workers, duplicates, scheduler, priority, static/dynamic, Socket.IO, API, CSRF, restart, failures, SSRF) + backup/restore + Brotli |
| UI crawl of the live app | 201 pages + 319 links + 19 dark-mode pages: **0 HTTP errors, 0 console errors** (after one fix), 0 backend tracebacks |
| End-to-end suite | **118/118** (Phase 13: 115; +3 new job checks) |
| Unit tests | **457 passed**, 8 known Windows-only, **0 new failures** (Phase 13: 453) |
| Bugs found / fixed | 4 fixed (§9); 1 data artifact repaired |
| Network use | 260 discovery/validation requests by the audit scripts (robots.txt honoured, ≥2 s between requests to the same host), plus 45 checks of real sites by WebPulse itself; **₹0 spent, no paid APIs**, no CAPTCHA or login bypass |
| Email / Telegram delivery | **NOT TESTED**, as instructed (no credentials configured) |

---

## 2. Feature status

PASS = verified by running it in this audit. PARTIAL = works, with a stated limitation. NOT TESTED = not run in this
audit.

| Area | Feature | Status | Evidence (this audit) |
|---|---|---|---|
| Websites | Real scraping (static) | PASS | 12 real sites, HTTP 200, meaningful lines (§3) |
| | Automatic periodic checks | PASS | scheduler gaps 10/10/10/10 s (§7); live Wikipedia hourly versions 11:55 → 16:04 |
| | Manual check | PASS | 4 new sites re-checked; check_count 1 → 2 |
| | MD5 change detection / no duplicate snapshots | PASS | the 4 manual re-checks: fetched MD5 = previous MD5, versions stayed at 1 (backend log) |
| | Snapshots and red/green diff | PASS | Hacker News: 5 genuine versions; the API difference shows "(changed) … (into) …"; the history page renders 24 change spans |
| | CSS / XPath / regex filters | PASS | UGC XPath → 40 notices; GitHub CSS → 76 titles; Python Insider CSS 10 → regex 7 |
| Products | Name, price, currency, stock | PASS | 22 distinct real products (§4) |
| | Selling price vs MRP / variants | PASS | 22/22 match the independent source; single-price products chosen |
| | Price decrease / increase | PASS | controlled 1000 → 900 → 1100 |
| | Out of stock / restock | PASS | controlled transitions, a new version each |
| | Min / max price filter | PASS | 900 inside 500–2000: no alert; 450 and 2500: alert |
| | % threshold | PASS | 10 %: −5 % ignored, −10.5 % alerted, −1.2 % ignored |
| | Price history and statistics | PASS | count/min/max/mean/median/quartiles/"cheaper than"/class equal to an independent calculation |
| | Excel export | PASS | one row per version, numeric prices identical |
| | Failed extraction keeps the last price and stock | PASS | a broken page gives an error; ₹950 and in stock are kept, no new version |
| | Genuine retailer price change | NOT OBSERVED | none happened during the audit (baselines only) |
| Jobs | Structured extraction: Lever / Greenhouse / SmartRecruiters / CSS / JSON-LD | PASS | 14 real boards (§5); Greenhouse counts equal the boards' own "N jobs" |
| | Baseline, New badge, removed, modified, re-opened | PASS | e2e J02, J05, J09, J10, J19; demo buttons |
| | Reordering, duplicates, irrelevant jobs | PASS | J07, J08; demo "Reorder" and "non-technical job" buttons |
| | Apply links | PASS | 13/13 real links HTTP 200 with the job title on the page |
| | Filters All/New/Active/Removed/Modified | PASS | J05, J11, UI crawl (45 job filter pages, 0 errors) |
| | First detected / last seen | PASS | J20: last seen within 5 s of the check time; J19: first detected kept on re-open |
| | Historical counts | PASS | J20: chart counts equal 3, 4, 4, 3, 0, 3 after each change |
| | Persistence after restart | PASS | P06–P07; backend restart test |
| | Failed extraction | PASS | J12 (blocked page): an error, 0 removed; demo "Block the careers page" |
| | Keyword edits are not job changes | PASS | J14: new starting point, no alert |
| | Confirmed empty board | PASS (new) | real empty Lever board recognised (§5.3); J18 |
| | Genuine new / removed real job | NOT OBSERVED | baselines only |
| Backend | 3 workers, duplicate prevention, priority, scheduler | PASS | §7 |
| | Requests vs Playwright | PASS | §7 |
| | Socket.IO | PASS | 4 pushes for the watch reached the open page, row updated without a reload |
| | REST API and authentication | PASS | 11 endpoints; no key / wrong key → 403 |
| | Datastore persistence, restart | PASS | 23/23 watches after a restart, up in 1.6 s |
| | Brotli | PASS | 86 files, 33.6 MB → 3.8 MB (−88.6 %) |
| | Backup / restore (isolated) | PASS | zip 37,531 B, 23 files; same UUID, versions, timestamps and price state |
| | Timeouts, retries, network failures | PASS | §7 |
| | SSRF, CSRF | PASS | §7 |
| UI | All main pages, buttons and links, dark mode, search | PASS | §8 |
| Notifications | Email / Telegram delivery | NOT TESTED | not configured, as instructed |
| | Notification history page | PASS | page loads (crawl); entries recorded in the e2e suite |

---

## 3. Real websites (12)

All were checked by WebPulse during the audit with HTTP 200 and no error. "Lines" is the text kept after the filters.
Watches 2, 4, 5 and 7 were created by you in earlier sessions; 5 is your Feature 3 test (a keyword regex without a
CSS selector), and 4 and 7 duplicate the main Hacker News watch. They were left untouched.

| # | Website | URL | Filter | Lines extracted | Versions | Interval | HTTP | Fetch |
|---|---|---|---|---|---|---|---|---|
| 1 | Python Insider - release announcements (CSS + regex) | `https://blog.python.org/` | `h3 + regex /^Python \d+\.\d+.*$/m` | 7 | 1 | 12 h | 200 | 0.822 s (html_requests) |
| 2 | https://en.wikipedia.org/wiki/Main_Page | `https://en.wikipedia.org/wiki/Main_Page` | `— (whole page)` | 642 | 5 | 1 h | 200 | 0.706 s (system) |
| 3 | GitHub Changelog - product announcements | `https://github.blog/changelog/` | `a.ChangelogItem-title` | 76 | 1 | 6 h | 200 | 0.599 s (html_requests) |
| 4 | https://news.ycombinator.com/ | `https://news.ycombinator.com/` | `— (whole page)` | 64 | 2 | default (3 h) | 200 | 1.319 s (system) |
| 5 | https://news.ycombinator.com/ | `https://news.ycombinator.com/` | `— (whole page) + regex /.*\b(?:AI\|LLM\|security\|Linux\|Python\|open source)(?:s\|es\|ing)?\b.*/i` | 6 | 4 | default (3 h) | 200 | 1.747 s (system) |
| 6 | Hacker News - front page headlines | `https://news.ycombinator.com/` | `.titleline > a` | 30 | 5 | 6 h | 200 | 1.293 s (html_requests) |
| 7 | https://news.ycombinator.com/. | `https://news.ycombinator.com/.` | `— (whole page)` | 64 | 2 | default (3 h) | 200 | 1.45 s (system) |
| 8 | Quotes to Scrape - JavaScript-rendered page | `https://quotes.toscrape.com/js/` | `— (whole page)` | 25 | 1 | 12 h | 200 | 11.558 s (html_webdriver) |
| 9 | Quotes to Scrape - JavaScript page via plain HTTP (static) | `https://quotes.toscrape.com/js/?fetched-with=requests` | `— (whole page)` | 5 | 1 | 12 h | 200 | 1.326 s (html_requests) |
| 10 | Python - latest releases | `https://www.python.org/downloads/` | `.download-list-widget` | 278 | 1 | 12 h | 200 | 0.641 s (html_requests) |
| 11 | The Hindu - technology headlines | `https://www.thehindu.com/sci-tech/technology/` | `h3.title a` | 20 | 1 | 6 h | 200 | 0.868 s (html_requests) |
| 12 | UGC - notices for universities (XPath filter) | `https://www.ugc.gov.in/` | `xpath://div[contains(@class,'scroll-marquee')]//a` | 40 | 1 | 12 h | 200 | 1.173 s (html_requests) |

**Added in this audit:**
* UGC (university notices, **XPath**);
* GitHub Changelog (technology announcements);
* Python Insider (release announcements, **CSS + regex**);
* The Hindu technology (news).

Considered and not used:
* **VTU circulars:** the URL tried returned 404.
* **University of Delhi:** only a banner line on the home page.
* **Node.js blog:** rendered with JavaScript (68 lines).
* **PIB:** redirected to the Hindi edition.

---

## 4. Real products (22 distinct products, 7 retailers, plus sandboxes)

**Independent check, per retailer:**
* **Shopify stores** (boAt, Sleepy Owl, Mokobara, Bombay Shaving Co, Noise): WebPulse's price and stock were compared
  with the store's own public product JSON, including the **MRP** (`compare_at_price`). In every case WebPulse
  reported the selling price.
* **Decathlon and IKEA:** compared with the price shown on the stored page. Decathlon's page also shows MRPs (e.g.
  ₹1,299 for the ₹799 gilet), and WebPulse did not take them.

**Product selection:** only products with one price across all variants, so the wrong variant can never be read.
Free gifts and hidden "secret link" pages were excluded.

**Check settings:** each product is checked every 24 h with "any stock change".

| # | Retailer | Product | Price (WebPulse) | Stock | Independent check | Method | Fetch | HTTP |
|---|---|---|---|---|---|---|---|---|
| 1 | books.toscrape.com | [Books to Scrape - "A Light in the Attic" (price & stock)](https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html) | 51.77 £ | not published | scraping sandbox (not an Indian retailer) | html_requests | 1.422 s | 200 |
| 2 | books.toscrape.com | [Books to Scrape - "Tipping the Velvet" (price & stock)](https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html) | 53.74 £ | not published | scraping sandbox (not an Indian retailer) | html_requests | 2.092 s | 200 |
| 3 | mokobara.com | [Mokobara - Bliss Shoulder Bag](https://mokobara.com/products/bliss-shoulder-bag) | 4,499.00 INR | In stock | store JSON ₹4,499 (MRP ₹6,499), available=True | html_requests | 1.479 s | 200 |
| 4 | mokobara.com | [Mokobara - Studio Crossbody](https://mokobara.com/products/studio-crossbody) | 4,999.00 INR | In stock | store JSON ₹4,999 (MRP ₹6,999), available=True | html_requests | 1.474 s | 200 |
| 5 | mokobara.com | [Mokobara - Take-Out Lunch Bag](https://mokobara.com/products/the-take-out-lunch-bag) | 2,999.00 INR | Out of stock | store JSON ₹2,999 (MRP ₹4,999), available=False | html_requests | 1.443 s | 200 |
| 6 | sleepyowl.co | [Sleepy Owl Coffee - enamel mug](https://sleepyowl.co/products/enamel-mug) | 564.00 INR | Out of stock | earlier phases (live) | html_requests | 1.447 s | 200 |
| 7 | sleepyowl.co | [Sleepy Owl - Hazelnut Protein Cold Coffee Powder Pack of 2](https://sleepyowl.co/products/hazelnut-protein-cold-coffee-powder-pack-of-2) | 999.00 INR | In stock | store JSON ₹999 (MRP ₹2,000), available=True | html_requests | 1.045 s | 200 |
| 8 | sleepyowl.co | [Sleepy Owl - Whisk & Whip Frother – Black](https://sleepyowl.co/products/whisk-whip-frother-black) | 1,199.00 INR | In stock | store JSON ₹1,199 (MRP ₹1,499), available=True | html_requests | 1.082 s | 200 |
| 9 | webscraper.io | [Web Scraper test shop - laptop (price from microdata)](https://webscraper.io/test-sites/e-commerce/static/product/60) | 295.99 USD | not published | scraping sandbox (not an Indian retailer) | html_requests | 0.62 s | 200 |
| 10 | webscraper.io | [Web Scraper test shop - product 61 (price from microdata)](https://webscraper.io/test-sites/e-commerce/static/product/61) | 299.00 USD | not published | scraping sandbox (not an Indian retailer) | html_requests | 1.96 s | 200 |
| 11 | boat-lifestyle.com | [boAt - boAt Aavante Bar Plus SoniQ-D \| 240W 2.1 Channel Dolby Audio S](https://www.boat-lifestyle.com/products/boat-aavante-bar-plus-soniq-d-bluetooth-soundbar) | 9,999.00 INR | Out of stock | store JSON ₹9,999 (MRP ₹27,900), available=False | html_requests | 1.176 s | 200 |
| 12 | boat-lifestyle.com | [boAt - boAt Aavante Prime Studio DA \| 550W 5.1 Channel Soundbar with ](https://www.boat-lifestyle.com/products/boat-aavante-prime-studio-da-bluetooth-soundbar) | 16,999.00 INR | In stock | store JSON ₹16,999 (MRP ₹39,990), available=True | html_requests | 1.467 s | 200 |
| 13 | boat-lifestyle.com | [boAt Stone 650 Bluetooth speaker](https://www.boat-lifestyle.com/products/stone-650) | 1,999.00 INR | Out of stock | earlier phases (live) | html_requests | 1.278 s | 200 |
| 14 | bombayshavingcompany.com | [Bombay Shaving Co - 10in1 Luxury Grooming Kit](https://www.bombayshavingcompany.com/products/10in1-luxury-grooming-kit) | 799.00 INR | Out of stock | store JSON ₹799 (MRP ₹799), available=False | html_requests | 1.177 s | 200 |
| 15 | bombayshavingcompany.com | [Bombay Shaving Co - Ultra Groomer](https://www.bombayshavingcompany.com/products/ultra-groomer) | 850.00 INR | Out of stock | store JSON ₹850 (MRP ₹2,000), available=False | html_requests | 1.193 s | 200 |
| 16 | decathlon.in | [Decathlon India - same gilet, read with a real browser (JavaScript)](https://www.decathlon.in/p/8189216/men-mountain-hiking-warm-fleece-gilet-jacket-black) | 799.00 INR | In stock | displayed selling price matches; MRP not taken | html_webdriver | 9.634 s | 200 |
| 17 | decathlon.in | [Decathlon India - Forclaz men's hiking fleece gilet](https://www.decathlon.in/p/8189216/men-mountain-hiking-warm-fleece-gilet-jacket-black) | 799.00 INR | In stock | displayed selling price matches; MRP not taken | html_requests | 1.137 s | 200 |
| 18 | decathlon.in | [Decathlon India - 80mm Oversize Stem](https://www.decathlon.in/p/8325779/80mm-oversize-stem) | 499.00 INR | In stock | displayed selling price matches; MRP not taken | html_requests | 0.927 s | 200 |
| 19 | decathlon.in | [Decathlon India - Battery Head Torch - 80 lumen Black](https://www.decathlon.in/p/8384991/battery-head-torch-80-lumen-black) | 799.00 INR | In stock | displayed selling price matches; MRP not taken | html_requests | 0.926 s | 200 |
| 20 | decathlon.in | [Decathlon India - WOMEN'S WOOL FELT HUNTING HAT 500 - BROWN](https://www.decathlon.in/p/8494199/women-warm-felt-hat-for-winter-safari-outdoors-hat500-brown) | 1,549.00 INR | In stock | displayed selling price matches; MRP not taken | html_requests | 0.959 s | 200 |
| 21 | decathlon.in | [Decathlon India - Rear Derailleur Microshift Advent 1X9 Speed Medium S](https://www.decathlon.in/p/864435/rear-derailleur-microshift-advent-1x9-speed-medium-screed) | 3,499.00 INR | In stock | displayed selling price matches; MRP not taken | html_requests | 0.868 s | 200 |
| 22 | gonoise.com | [Noise - Noise ALT Buds (S) Truly Wireless Bluetooth Earbuds - Chosen B](https://www.gonoise.com/products/noise-alt-buds-s-truly-wireless-bluetooth-earbuds-chosen-blue) | 1,899.00 INR | In stock | store JSON ₹1,899 (MRP ₹1,899), available=True | html_requests | 1.403 s | 200 |
| 23 | gonoise.com | [Noise - ALT Watch 1 & Buds (S) Combo](https://www.gonoise.com/products/noise-alt-watch-1-buds-s-combo) | 6,499.00 INR | In stock | store JSON ₹6,499 (MRP ₹6,999), available=True | html_requests | 1.378 s | 200 |
| 24 | ikea.com | [IKEA India - VIMLE 2-seat sofa, Knäbäck light beige](https://www.ikea.com/in/en/p/vimle-2-seat-sofa-knaebaeck-light-beige-s29634662/) | 54,990.00 INR | In stock | displayed selling price matches; MRP not taken | html_requests | 1.777 s | 200 |
| 25 | ikea.com | [IKEA India - VINTERFINT candlestick, for 3 candles red, 24 cm (9 ½")](https://www.ikea.com/in/en/p/vinterfint-candlestick-for-3-candles-red-50634269/) | 799.00 INR | In stock | displayed selling price matches; MRP not taken | html_requests | 1.296 s | 200 |
| 26 | ikea.com | [IKEA India - VISSLAÅN drawer organiser, grey, 35x11x3 cm (13 ¾x4 ¼x1")](https://www.ikea.com/in/en/p/visslaan-drawer-organiser-grey-00562118/) | 199.00 INR | In stock | displayed selling price matches; MRP not taken | html_requests | 1.804 s | 200 |
| 27 | ikea.com | [IKEA India - ZEBRASÄV pendant lamp, white/plastic, 46 cm (18")](https://www.ikea.com/in/en/p/zebrasaev-pendant-lamp-white-plastic-30580074/) | 499.00 INR | In stock | displayed selling price matches; MRP not taken | html_requests | 2.092 s | 200 |

**Notes:**
* Stock values are what each shop publishes. The 5 out-of-stock items (boAt Stone 650 and Aavante Bar Plus, Sleepy
  Owl enamel mug, Mokobara lunch bag, both Bombay Shaving Co items) are genuinely out of stock according to the
  shop's own data. A restock would be a genuine change.
* The two Books to Scrape products publish no machine-readable stock. Their stock shows "not published" (inherited
  behaviour).

---

## 5. Career pages (14 real boards + 1 controlled)

**Keywords:**
* default: `software, engineer, developer, backend, frontend, full stack, fullstack, SDE, intern, data, devops`;
* **Paytm** uses the same list without `frontend` and `intern`: Paytm's "(Frontend)" titles are field-sales roles,
  and its "intern" titles are HR internships;
* **Hevo** keeps your own keyword rule;
* **python.org** has no keyword filter.

Keywords are matched against the **job title**. Every relevant opening has its own apply link.

| # | Company | Board URL | Provider / method | Openings on board | Relevant (keywords) | Apply links | Interval | Sample relevant titles · locations · types | Apply link check |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Freshworks | `https://careers.smartrecruiters.com/Freshworks/pd` | SmartRecruiters job board | 15 | 13 | 13/13 | 12 h | Lead Software Engineer - Full Stack · Chennai, India · Full-time; Lead Software Engineer - Full Stack · Hyderabad, India · Full-time; Lead Software Engineer - Site Reliability · Boston, MA · Full-time · Hybrid | HTTP 200, title on page |
| 2 | Groww | `https://job-boards.eu.greenhouse.io/groww` | Greenhouse job board | 8 | 0 | 0/0 | 12 h | — (no opening matches the keywords) | n/a |
| 3 | HackerRank careers (Greenhouse job board) - technical roles | `https://job-boards.greenhouse.io/hackerrank` | Greenhouse job board | 32 | 17 | 17/17 | 12 h | AI Researcher Intern · Onsite in Bangalore; Customer Experience Engineering · Hybrid in Bangalore, India; Deep Learning Research Engineer · Hybrid in Bangalore, India | HTTP 200, title on page |
| 4 | InMobi | `https://job-boards.greenhouse.io/inmobi` | Greenhouse job board | 50 | 9 | 9/9 | 12 h | AI Engineer · San Mateo, CA; Machine Learning Engineer II - Backend · Bengaluru; Machine Learning Engineer – Ad Sciences · San Mateo, CA | HTTP 200, title on page |
| 5 | Razorpay | `https://job-boards.greenhouse.io/razorpaysoftwareprivatelimited` | Greenhouse job board | 26 | 4 | 4/4 | 12 h | DevOps Enginer · Malaysia; Engineering Manager · Bengaluru; Frontend Engineer · Bengaluru | HTTP 200, title on page |
| 6 | Zenoti | `https://job-boards.greenhouse.io/zenoti` | Greenhouse job board | 50 | 6 | 6/6 | 12 h | Lead - AI Data Intelligence (ETL,Azure, SQL, Python, Spark, Data Lakehouse) 7 - 11 years exp from SaaS companies · Hyderabad, Telangana, India; Lead Engineer - Full Stack (AI) · Hyderabad, Telangana, India; Lead Reliability Engine | HTTP 200, title on page |
| 7 | CRED | `https://jobs.lever.co/cred` | Lever job board | 10 | 1 | 1/1 | 12 h | fraud analytics engineer · bengaluru · full time · On-site | HTTP 200, title on page |
| 8 | HighLevel | `https://jobs.lever.co/gohighlevel` | Lever job board | 95 | 40 | 40/40 | 12 h | Director of Engineering - Marketplace · India · Employee India · Remote; Engineering Manager - I · India · Remote; Engineering Manager II - Monetisation · India / Delhi / Remote · Employee India · Remote | HTTP 200, title on page |
| 9 | https://jobs.lever.co/hevodata | `https://jobs.lever.co/hevodata` | Lever job board | 42 | 18 | 18/18 | default | Associate SDE · Bangalore, India · Full time · On-site; Associate SDE- Pune · Pune, Maharashtra · Full time · On-site; Associate Software Development Engineer (SDE) Intern · Bangalore, India · Full time · On-site | HTTP 200, title on page |
| 10 | Meesho careers (Lever job board) - technical roles | `https://jobs.lever.co/meesho` | Lever job board | 49 | 10 | 10/10 | 12 h | Data Scientist III · Bangalore, Karnataka · Full Time Employee · On-site; Data Scientist III (Team- Valmo) · Bangalore, Karnataka · Full Time Employee · On-site; Director Data Science · Bangalore, Karnataka · Full Time Employee ·  | HTTP 200, title on page |
| 11 | Mindtickle | `https://jobs.lever.co/mindtickle` | Lever job board | 17 | 7 | 7/7 | 12 h | AI Product Engineer · Pune, Maharashtra / Bengaluru, Karnataka · Full-Time · Hybrid; Customer Success Engineer - II · Pune, Maharashtra · Full-Time · On-site; Lead Design Engineer · Pune, Maharashtra / Bengaluru, Karnataka · Full- | HTTP 200, title on page |
| 12 | Paytm | `https://jobs.lever.co/paytm` | Lever job board | 193 | 5 | 5/5 | 12 h | Cloud & IT Operations Engineer · Luxembourg · Full-time Employment · On-site; Forward Deployed Engineer · Bangalore, Karnataka / Noida, Uttar Pradesh · Full-time Employment · On-site; Lead/Senior Lead - Data Devops · Noida, Uttar  | HTTP 200, title on page |
| 13 | Zeta | `https://jobs.lever.co/zeta` | Lever job board | 38 | 16 | 16/16 | 12 h | DevSecOps Engineer II · Hyderabad · Full-time · On-site; Director - Product and Solutions Engineering · East Coast · Full-time · Remote; Intern · Bangalore - WF · Intern · On-site | HTTP 200, title on page |
| 14 | Python.org job board - Python developer jobs | `https://www.python.org/jobs/` | Page section (CSS selector) | 22 | 22 | 22/22 | 6 h | Agentic Python Engineer · Remote, Worldwide · Back end, Integration, Systems; Agentic Python Engineer · Remote, Remote/Worldwide, Remote/Worldwide, Remote · Back end, Integration, Machine Learning; Agentic Python Engineer · Remote | HTTP 200, title on page |

### 5.1 How the boards were found

The audit did not assume URLs. For each company it:
1. probed the public Lever and Greenhouse board names (an HTTP 404 means no board);
2. opened the company's official careers page once and looked for the hiring system it links to.

What that found:
* **Razorpay** links to `job-boards.greenhouse.io/razorpaysoftwareprivatelimited`;
* **Groww** to the **EU** Greenhouse host;
* **Freshworks** to **SmartRecruiters**;
* **BrowserStack** to **Workday**.

### 5.2 Reliability

* **Greenhouse:** the number read equals the board's own "N jobs" header (Razorpay 26/26; HackerRank 32/32, Zenoti
  50/50 and Groww 8/8 when their stored pages were re-parsed with the fixed code).
* **Lever and SmartRecruiters:** the boards publish no total.
* **Zenoti and InMobi:** both returned exactly 50. That is their real total, not a page limit: no pagination exists
  and Zenoti's header says "50 jobs".
* **Groww:** 8 openings, none technical. It shows 0 relevant openings, which is correct.

### 5.3 Confirmed empty boards

A real Lever board with no openings was found during discovery: `jobs.lever.co/epifi`, which now belongs to
"Workloom". Its page contains `.postings-wrapper` and `p.no-postings-message` ("No job postings currently open.
Check back later!").

Before the fix, automatic mode turned that message into one fake opening. Now WebPulse reads 0 openings and records
the reason. Only explicit signals count:
* that Lever message;
* Greenhouse's "0 jobs";
* or a "no open positions" message inside the user's page section.

A bot check, a redesign or a missing list is still an error that keeps every opening. A drop from 10 or more openings
to 20 % or fewer still has to be seen twice in a row. Covered by unit tests, e2e J18 and the demo buttons.

---

## 6. Controlled demonstration results

All on throw-away instances with WebPulse's local demo site. These are not real-world data.

**Products (17/17):**

| Step | Result |
|---|---|
| Baseline ₹1,000, in stock | 1 version |
| ₹1,000 → ₹900 | v2, previous price kept as 1000 |
| ₹900 → ₹1,100 | v3 |
| Out of stock | v4 |
| Restock | v5 |
| ₹1,100 → ₹950 | v6, −13.6 % |
| Statistics | series 1000, 900, 1100, 1100, 1100, 950. Independent calculation: mean 1025, median 1050, p25 962.5, p75 1100, min 900, max 1100, "cheaper than 67 %", class **low**. WebPulse: identical in every field |
| Broken product page | error "Unable to extract restock data…"; price ₹950 and in stock **kept**, no version; page back → error cleared |
| Excel | header Date / Stock status / Price / Currency; prices 1000, 900, 1100, 1100, 1100, 950 as numbers |
| Min 500 / max 2000 | 900: no version; 450: version; 2500: version |
| 10 % threshold | 950 (−5 %): none; 850 (−10.5 %): version; 840 (−1.2 %): none |

**Job buttons (Controlled demo page):**

| Button | Result |
|---|---|
| Publish a new job | +1 new ("Junior Backend Developer (Python, Django)") |
| Reorder the jobs | no event |
| Publish a non-technical job | no event |
| Change a job | modified: location "Bengaluru" → "Hybrid, Bengaluru", same id |
| Remove a job | −1 removed |
| **Block the careers page** | error, 3 openings kept |
| Unblock | error cleared, no event |
| Remove a job, three more times | one removal event each |
| Remove the last (non-technical) job | the page's "No open positions" is recognised as a confirmed empty board |

The e2e suite (J01–J20) covers the same scenarios automatically, including webhook alerts: exactly one alert for a
new opening, none for the baseline, reordering or keyword edits.

---

## 7. Backend measurements (throw-away instance, local demo site)

| Test | Measured |
|---|---|
| 3 workers in parallel | six 3-second pages finished in **6.4 s** (two rounds), against 18 s serially |
| Duplicate UUID protection | the same watch queued 5 times while running: **2 checks, run one after the other**, never concurrently (UUID claim lock) |
| Scheduler accuracy | 10-second interval: gaps **10, 10, 10, 10 s** |
| Manual vs scheduled priority | with all 3 workers busy (4-second checks, scheduled every 5 s, 3 queued), a manual check finished after **3.0 s**, served ahead of the queue (priority 1 vs epoch-time priority) |
| Static vs browser (controlled JavaScript page) | plain HTTP 0.97 / 0.22 / 0.64 s, **misses** the JavaScript content; Edge 9.47 / 6.33 / 6.11 s, **sees** it |
| Static vs browser (real) | Decathlon gilet 1.14 s plain vs 9.63 s Edge, same ₹799; Quotes to Scrape 1.33 s (5 lines, no quotes) vs 11.56 s (25 lines) |
| Socket.IO | 14 frames reached the open Websites page, 4 about the re-checked watch; its row updated **without a reload** |
| REST API | 200 for systeminfo, list, get, put, history, difference, tags, search (`partial=true`); 201 create; 204 delete; **403** with no key or a wrong key |
| CSRF | form POST without a token → **400**; with a token → 302 |
| Restart and recovery | 23/23 watches with the same number of versions; back up in **1.6 s** |
| Network failures (retries = 2) | DNS failure **2.0 s**; connection refused **7.8 s**; page slower than the 5 s timeout **16.9 s** (3 attempts). Each is recorded as the watch's error and the app keeps serving |
| SSRF (instance without the test bypass) | `127.0.0.1`, `localhost`, `169.254.169.254` (cloud metadata) and `10.0.0.1` all **blocked at fetch time**; `file:///C:/Windows/win.ini` refused with HTTP 400 |
| Backup / restore (isolated) | backup zip 37,531 bytes, 23 files (JSON, txt, Brotli); restored into an empty instance: same UUID, 2/2 versions, same timestamps, price 849 / previous 999 / out of stock |
| Brotli (your real data folder) | 86 compressed files: 33,591 KB → 3,838 KB (**88.6 % smaller**); largest 2,659 KB → 269 KB |

---

## 8. Automated and UI test results

* **Live UI crawl in Edge** (read-only; links that change something were skipped):
  * 201 pages: every main page, every watch's preview and edit page, every job page with its filters, the diff
    pages, search, settings, backups, queue, demo;
  * 319 further internal links;
  * the 19 main pages again in **dark mode**.

  Results:
  * **0 HTTP errors**;
  * **0 browser console errors** after the fix below (before it, every navigation logged "Transport not open");
  * **0 backend tracebacks**.

  Count checks:
  * the Job listings total of active openings (171) equals the sum over the 15 boards' stored state;
  * Home "All products (28)" equals the 28 product watches;
  * search "decathlon" → 6 rows, "ikea" → 4, "jobs.lever" → 7, all correct.
* **End-to-end** `e2e\run_e2e.ps1 -Browser -UI`: **118/118** (core 60, persist 7, security 8, browser 8, UI 35), 0
  unexpected app-log errors.
  * Phase 13 had 115: J12 was rewritten for the blocked page, and J18–J20 are new.
* **Unit** `e2e\run_unit.ps1`: **457 passed** (Phase 13: 453; +4 job tests). Pytest reports "7 failed, 1 error", which
  is exactly the 8 entries in `e2e/known_windows_unit_failures.txt`, so there are **0 new failures**. Their causes,
  re-checked from the actual output:

  | Test(s) | Cause |
  |---|---|
  | 4 symlink tests | `WinError 1314`: symlinks need admin rights or Developer Mode |
  | `test_fetch_url_gate…junk_link_local_aaaa` | expects a Linux-only SSRF exception; on Windows the host correctly stays blocked |
  | 2 socket-stats tests | outdated **upstream** tests |
  | `test_auth_decorator_order` | the set-up error: the pytest-flask live server needs `fork()` |

  The earlier notes said "5 symlink + 2 live server"; they are corrected.
* **Templates** 37/37 parse; **imports** 52/52.

---

## 9. Bugs discovered and fixes made

| # | Bug (how found) | Fix |
|---|---|---|
| 1 | **Greenhouse "New" tag in job titles.** Found while validating Razorpay: "Lead Software Development Engineer **New**". When Greenhouse drops the tag after a few days, the opening would have been reported as *modified* (a false change) | `extract.greenhouse_jobs` removes `.tag-container`. One stored HackerRank title with the suffix was repaired. The Razorpay and Freshworks watches, created two minutes earlier while the running app still had the old code, were recreated so their baselines are clean |
| 2 | **An empty Lever board produced one fake opening** (the real Fi/Workloom board) | Lever is also recognised by `.postings-wrapper`; automatic mode needs real job links; explicit empty-board signals (§5.3) |
| 3 | **Uncaught JavaScript error "Transport not open" on every navigation** (live crawl). Inherited: `realtime.js` calls `socket.disconnect()` in `beforeunload` while the connection may still be setting up | the call is guarded with try/catch; 0 errors in the re-crawl |
| 4 | **Controlled demo: "Remove a job" did nothing for the last job** (sends an empty value, which the demo site ignores) | sends an explicit empty list |

**Improvements:**
* SmartRecruiters boards are read as structured jobs (Freshworks), with location, type and canonical links.
* Confirmed-empty detection.
* The board's stated total is shown on the Openings page.
* Controlled demo: a "Block the careers page" button and a broken-product test mode.

No architectural change; the modular monolith, attribution and licence are unchanged.

---

## 10. Unsupported websites and reasons

| Site | Why not monitored | Evidence |
|---|---|---|
| Amazon India, Flipkart, Myntra | Their published terms of use prohibit automated data collection. robots.txt alone would allow a product path, but no page was fetched | robots.txt check only |
| Croma | HTTP **403** with a bot-check page | one homepage request |
| Reliance Digital | the homepage includes a bot-check/CAPTCHA component; not pursued (no bypass), and 7 retailers were already validated | one homepage request |
| Snitch | `/products.json` is not available, so there is no independent check; not pursued | one request |
| Noise smartwatches (Kore, ColorFit Icon Rise Max) | the page's own JSON-LD product data is **malformed**, so automatic extraction fails. A CSS price selector would be needed; other Noise products work | extruct `JSONDecodeError` |
| Postman, PhonePe, Swiggy careers | the careers pages are rendered with JavaScript, and no public hiring-system link is in the HTML | one request each |
| BrowserStack careers | Workday, a JavaScript application | link found on the official page |
| Zomato careers | **robots.txt disallows** `/careers` | robots.txt |
| Dream11, Acko, smallcase, CleverTap, MoEngage, Unacademy, Ather, Yellow.ai, Gupshup, Cars24, Licious, Nykaa, Jupiter, Rapido, Juspay, Chargebee, Innovaccer, Whatfix, Spinny, Urban Company, Upstox, Atlan, Hasura, Tekion, ThoughtSpot, Udaan, Navi, apna, Plum, Sarvam AI, Jar, Zluri, LeadSquared, Capillary, Darwinbox | no public Lever or Greenhouse board under the names tried (HTTP 404); their own careers sites were not explored | 404s |
| Ola (`olacabs`), Druva, Rubrik, slice | read timeout / HTTP 406 / HTTP 403 / a page that is not a job board | one request each |

---

## 11. Remaining limitations

* **Genuine changes take time:**
  * no real retailer price or stock change and no real job change happened during the audit;
  * the new watches are baselines (24 h for products, 12 h for job boards).

  Leave WebPulse running (laptop plugged in, no sleep) to collect genuine history.
* **The % threshold compares with the previous check, not the last alert.** A price that drifts down by less than the
  threshold at every check is never reported (inherited behaviour).
* **Job keywords match titles only.** Some boards' titles are ambiguous (Paytm "Frontend" means sales), so keywords
  may need tuning per company.
* **JavaScript-only boards** (Workday, Ashby, many company sites) need the browser method or are unsupported.
* **Products:** stock is only as reliable as each shop's published data. Malformed JSON-LD (Noise smartwatches) needs
  a manual price selector.
* **Upstream keeps a version index per processor.** The older text versions of the 5 converted career pages remain
  on disk but are hidden while they are job monitors.
* **Your duplicate Hacker News watches** (`55f459f9`, `26f7c0b3`) and the Feature 3 watch without a selector
  (`acdb1a8a`) were left as they are; delete or fix them if you like.
* **Email and Telegram:** real delivery was not tested (no credentials). The secrets would be stored unencrypted in
  the data folder, as upstream does.
* Upstream's Linux-only integration tests cannot run on Windows; `e2e/` replaces them, and 8 unit tests are
  Windows-only failures.

---

## 12. How to demonstrate every feature yourself

WebPulse is running: http://127.0.0.1:5000, with the backend window titled "WebPulse backend".

1. **Home:** the six use-case cards with live counts. Job listings now shows 171 active openings.
2. **Websites:**
   1. Open **The Hindu - technology headlines** → **View page**: 20 headlines (CSS).
   2. **UGC**: 40 notices (XPath).
   3. **Python Insider**: only "Python x.y…" posts (CSS + regex).
   4. Press **Check now** on one of them. The backend window shows `Previous MD5: X, Fetched MD5 X` and no new version
      is saved.
   5. **Hacker News - front page headlines** → **View changes**: genuine red and green changes.
   6. **Wikipedia** → **View changes**: hourly genuine versions, including 16:04 today.
3. **Products:**
   1. Pick a row, e.g. Decathlon "Battery Head Torch" ₹799 in stock, or boAt "Aavante Bar Plus" ₹9,999 out of stock.
      Click the external-link icon and compare with the shop page: the selling price is shown, not the MRP.
   2. **Edit → Price & stock** shows the min/max and % threshold settings.
4. **Historical analytics:** **Controlled demo** → **Drop the price** twice and **Raise the price** once, then open
   "[Demo] Wireless earbuds" → **Price history**: the chart, min/max/average, "cheaper than N %", and **Download as
   XLSX**.
5. **Job listings:**
   1. Look at the 15 cards.
   2. Open **HighLevel** (40 technical openings) or **Hevo Data**. Try the filter chips and **Apply**; the Openings
      page also shows "the board itself says N" for Greenhouse boards (e.g. Razorpay).
6. **Controlled demo (jobs):**
   1. **Publish a new job** → **Openings** shows a New badge.
   2. **Reorder the jobs** → nothing changes.
   3. **Publish a non-technical job** → ignored.
   4. **Change a job** → Modified with the old → new location.
   5. **Remove a job** → Removed with the time.
   6. **Block the careers page** → an error, every job kept; then **Unblock**.
   7. **Reset the demo site** when finished.
7. **Behind the scenes:**
   * Home → **Workers and queue**: three workers. Click **Check all now** on Websites and watch the queue drain live
     (Socket.IO).
   * REST API: Settings → REST API key; `curl.exe -H "x-api-key: <key>" http://127.0.0.1:5000/api/v1/systeminfo`.
     Without the key you get 403.
8. **Settings → More tools → Backups:** **Create backup**, then download it.
9. **Dark mode:** the moon/sun button at the top right.
10. **Persistence:** press Ctrl+C in the backend window, run `.\run.ps1` again, and everything is still there.

---

## 13. Repository and network totals

* **Commit:** `98b83011` "Phase 14: complete functional audit and real-world data expansion" on branch `simplified`
  (parent `bb209b8f`). It changes 15 files:
  * `CHANGES.md`, `README.md`;
  * `docs/COMPLETE_FUNCTIONAL_AUDIT.md` (new), `docs/COMPLETE_WALKTHROUGH.md`;
  * `processors/job_listings/{extract,processor,tracker}.py`;
  * `blueprint/jobs/templates/jobs-detail.html`, `blueprint/demo_lab/__init__.py`, `demo-lab.html`;
  * `static/js/realtime.js`;
  * `tests/unit/test_job_listings.py`;
  * `e2e/fixture_server.py`, `e2e/test_e2e.py`, `e2e/known_windows_unit_failures.txt`.
* **Audit network use (scripts):** 260 HTTP requests, 128.5 MB of uncompressed bodies. That includes one 50 MB IKEA
  product sitemap and 119 HTTP 404s from board-name probes.

  | By purpose | Requests |
  |---|---|
  | Job board discovery | 128 |
  | robots.txt | 55 |
  | Product validation | 27 |
  | Apply-link checks | 13 |
  | Product discovery | 11 |
  | Careers-provider lookup | 8 |
  | Website candidates | 8 |
  | Board probes | 6 |
  | Sitemaps | 2 |
  | Retailer feasibility | 2 |

  At least 2 s between requests to the same host.
* **WebPulse's own checks of real sites during the audit:** 45. From now on, the real watches are checked every
  1–24 h according to their intervals: **138 checks a day** for the 53 real watches, calculated from their intervals
(default 3 h). The three Hacker News watches and hourly Wikipedia account for about half of that.
* **Paid APIs / LLMs / scraping services:** none, ₹0.
* **Final watch count:**
  * 62 in total: 53 real + 9 controlled demo;
  * by processor: 28 products, 19 websites, 15 job boards;
  * the real ones: 12 websites, 27 products (22 distinct Indian products + 4 sandbox products + the Decathlon gilet
    read through the browser), 14 career boards.

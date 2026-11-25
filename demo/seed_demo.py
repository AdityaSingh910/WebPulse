"""Create a WebPulse demonstration datastore.

    python demo/seed_demo.py <datastore_dir> [--force]

Run it while WebPulse is NOT running on that datastore, then start WebPulse with  .\\run.ps1 -Datastore <dir>

It creates two kinds of watches:

* LIVE watches on real public websites. They are checked by WebPulse on a polite schedule (every 6-12 hours).
  Only sites that welcome scraping/monitoring and whose robots.txt allows the pages are used:
  books.toscrape.com and quotes.toscrape.com (scraping sandboxes), webscraper.io/test-sites (scraping test
  shop), plus two public pages (Hacker News front page, python.org downloads).
* SAMPLE watches with SIMULATED history, so the price charts and change history have something to show on
  day one. They are clearly labelled: title prefix "[Sample data]", group "Sample data (simulated)", and they
  are PAUSED so WebPulse never fetches them. Their URLs point at example.com (reserved for documentation).
  The history is written through the app's own Watch.save_history_blob(), exactly as a real check would.
"""
import hashlib
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ.setdefault('DISABLE_VERSION_CHECK', 'true')

DAY = 86400


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    ds_path = os.path.abspath(sys.argv[1])
    force = '--force' in sys.argv
    if os.path.exists(os.path.join(ds_path, 'changedetection.json')) and not force:
        sys.exit(f'{ds_path} already holds a datastore - use an empty folder (or --force to add the demo watches to it)')
    os.makedirs(ds_path, exist_ok=True)

    from changedetectionio.store import ChangeDetectionStore
    from changedetectionio.processors.restock_diff import Restock

    ds = ChangeDetectionStore(datastore_path=ds_path, include_default_watches=False, version_tag='0.70.4')
    every = lambda h: {'time_between_check_use_default': False, 'time_between_check': {'weeks': None, 'days': None, 'hours': h, 'minutes': None, 'seconds': None}}

    # ---------------- LIVE watches (real websites) ----------------
    live = [
        dict(url='https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html', tag='E-commerce (live)',
             extras={'title': 'Books to Scrape - "A Light in the Attic" (price & stock)', 'processor': 'restock_diff',
                     'fetch_backend': 'html_requests', 'include_filters': ['.product_main .price_color'], **every(12)}),
        dict(url='https://webscraper.io/test-sites/e-commerce/static/product/60', tag='E-commerce (live)',
             extras={'title': 'Web Scraper test shop - laptop (price from microdata)', 'processor': 'restock_diff',
                     'fetch_backend': 'html_requests', **every(12)}),
        dict(url='https://quotes.toscrape.com/js/', tag='JavaScript pages (live)',
             extras={'title': 'Quotes to Scrape - JavaScript-rendered page', 'fetch_backend': 'html_webdriver', **every(12)}),
        dict(url='https://news.ycombinator.com/', tag='News & releases (live)',
             extras={'title': 'Hacker News - front page headlines', 'fetch_backend': 'html_requests',
                     'include_filters': ['.titleline > a'], **every(6)}),
        dict(url='https://www.python.org/downloads/', tag='News & releases (live)',
             extras={'title': 'Python - latest releases', 'fetch_backend': 'html_requests',
                     'include_filters': ['.download-list-widget'], **every(12)}),
    ]
    for w in live:
        ds.add_watch(url=w['url'], tag=w['tag'], extras=w['extras'])

    # ---------------- SAMPLE watches (simulated history, paused) ----------------
    now = int(time.time())
    rnd = random.Random(42)  # deterministic

    def price_series(days, points, start, path):
        """path: list of (day_fraction, price, in_stock) anchors; returns [(ts, price, in_stock)] with small noise."""
        out = []
        for i in range(points):
            f = i / (points - 1)
            for (f0, p0, s0), (f1, p1, s1) in zip(path, path[1:]):
                if f0 <= f <= f1:
                    t = (f - f0) / (f1 - f0) if f1 > f0 else 0
                    price = p0 + (p1 - p0) * t
                    stock = s0 if t < 0.5 else s1
                    break
            price = round(price * (1 + rnd.uniform(-0.012, 0.012)) / 10) * 10 - 1   # e.g. 4,299 style prices
            ts = now - int((1 - f) * days * DAY) - rnd.randint(0, 3600)
            out.append((ts, float(price), stock))
        out[-1] = (now - 600, out[-1][1], out[-1][2])
        return out

    samples = [
        ('[Sample data] Wireless noise-cancelling headphones', 'https://example.com/sample/wireless-headphones', 'INR',
         price_series(60, 24, 4999, [(0, 4999, True), (0.35, 4599, True), (0.5, 3499, True), (0.62, 3599, False),
                                     (0.72, 4299, True), (0.88, 4099, True), (1.0, 3799, True)])),
        ('[Sample data] 14-inch ultrabook laptop', 'https://example.com/sample/ultrabook-laptop', 'INR',
         price_series(60, 20, 64990, [(0, 64990, True), (0.3, 61990, True), (0.55, 59990, True), (0.7, 62990, True),
                                      (0.85, 58990, True), (1.0, 57990, True)])),
    ]
    for title, url, currency, series in samples:
        uuid = ds.add_watch(url=url, tag='Sample data (simulated)',
                            extras={'title': title, 'processor': 'restock_diff', 'paused': True, 'fetch_backend': 'html_requests'})
        watch = ds.data['watching'][uuid]
        last_price = None
        for ts, price, stock in series:
            snap = f"In Stock: {stock} - Price: {price}"
            watch.save_history_blob(contents=snap, timestamp=ts, snapshot_id=hashlib.md5(snap.encode()).hexdigest())
        prev = series[-2][1] if len(series) > 1 else None
        watch['restock'] = Restock({'in_stock': series[-1][2], 'price': series[-1][1], 'currency': currency,
                                    'original_price': series[0][1], 'last_price': prev})
        watch['last_checked'] = series[-1][0]
        watch['check_count'] = len(series)
        watch.commit()
        print(f'sample   {title}  ({len(series)} simulated snapshots)')

    # Simulated text-change history (to demonstrate the difference viewer)
    versions = [
        (21, "Product release notes\nVersion 2.3.0\n- Faster page loading\n- Fixed login timeout\nSupport: help@example.com"),
        (14, "Product release notes\nVersion 2.4.0\n- New dashboard widgets\n- Faster page loading\n- Fixed login timeout\nSupport: help@example.com"),
        (6, "Product release notes\nVersion 2.4.1\n- Security patch for file uploads\n- New dashboard widgets\n- Faster page loading\nSupport: help@example.com"),
        (1, "Product release notes\nVersion 2.5.0 (beta)\n- Dark mode\n- Security patch for file uploads\n- New dashboard widgets\nSupport: support@example.com"),
    ]
    uuid = ds.add_watch(url='https://example.com/sample/release-notes', tag='Sample data (simulated)',
                        extras={'title': '[Sample data] Software release notes page', 'paused': True, 'fetch_backend': 'html_requests'})
    watch = ds.data['watching'][uuid]
    for days_ago, text in versions:
        ts = now - days_ago * DAY - rnd.randint(0, 7200)
        watch.save_history_blob(contents=text, timestamp=ts, snapshot_id=hashlib.md5(text.encode()).hexdigest())
    watch['last_checked'] = now - DAY
    watch['previous_md5'] = hashlib.md5(versions[-1][1].encode()).hexdigest()
    watch.commit()
    print(f'sample   [Sample data] Software release notes page  ({len(versions)} simulated snapshots)')

    ds.commit()
    print(f'\nDemo datastore ready: {ds_path}  ({len(ds.data["watching"])} watches)')
    sys.stdout.flush()
    os._exit(0)  # the store starts background threads; nothing else to wait for


if __name__ == '__main__':
    main()

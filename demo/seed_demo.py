"""Create a WebPulse demonstration datastore.

    python demo/seed_demo.py <datastore_dir> [--force]

Run it while WebPulse is NOT running on that datastore, then start WebPulse with  .\\run.ps1 -Datastore <dir>

It creates LIVE watches on real public websites, checked by WebPulse on a polite schedule (every 6-12 hours).
Only sites that welcome scraping/monitoring and whose robots.txt allows the pages are used:
books.toscrape.com and quotes.toscrape.com (scraping sandboxes), webscraper.io/test-sites (scraping test shop),
plus two public pages (Hacker News front page, python.org downloads).

No history is invented: every saved version is the result of a real check. (Earlier versions of this script also
created "[Sample data]" watches with simulated price history; that was removed in Phase 11.) For real Indian shops,
job boards and the controlled demo, run demo/setup_presentation.py afterwards.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ.setdefault('DISABLE_VERSION_CHECK', 'true')



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

    ds.commit()
    print(f'\nDemo datastore ready: {ds_path}  ({len(ds.data["watching"])} watches)')
    sys.stdout.flush()
    os._exit(0)  # the store starts background threads; nothing else to wait for


if __name__ == '__main__':
    main()

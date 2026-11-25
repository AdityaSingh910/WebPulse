"""Prepare a WebPulse datastore for the project presentation (demo tooling, not part of the app).

    python demo/setup_presentation.py <datastore_dir> [<demo_site_dir>]

Run it while WebPulse is STOPPED. It is safe to run more than once. It:

1. copies the datastore to <datastore_dir>-backup-<date-time> first;
2. deletes every "[Sample data]" watch. Those carried simulated price history, and the presentation must only
   show history that WebPulse really recorded;
3. adds REAL public monitoring examples (skipping any that already exist):
     products: Indian shops with INR prices whose robots.txt allows product pages (Decathlon India, Sleepy Owl,
               boAt), checked every 12-24 hours;
     jobs:     public careers pages / job boards (HackerRank on Greenhouse, Meesho on Lever, python.org jobs),
               limited to the job list with a CSS selector and to technical roles with keywords;
4. sets up the CONTROLLED demo (WebPulse's own local demo site, reached only through the "WebPulse demo site"
   proxy): the demo product, the demo news page and a demo careers page. The old once-a-minute "clock" watch is
   removed, the concurrency-test pages are muted, and the demo watches use the normal Email/Telegram settings;
5. sets clear alert wording.

Nothing here invents history: every saved version comes from a real check made by WebPulse.
"""
import json
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ.setdefault('DISABLE_VERSION_CHECK', 'true')

DEMO_PROXY = 'webpulse-demo-site'
JOBS = 'Job listings'
TECH_KEYWORDS = 'engineer, developer, software, backend, data, python, intern, sde'


def every(hours=None, minutes=None):
    return {'time_between_check_use_default': False,
            'time_between_check': {'weeks': None, 'days': None, 'hours': hours, 'minutes': minutes, 'seconds': None}}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ds_path = os.path.abspath(sys.argv[1])
    site_dir = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(os.path.dirname(ds_path), 'webpulse-demo-site')
    if not os.path.isfile(os.path.join(ds_path, 'changedetection.json')):
        sys.exit(f'No WebPulse datastore in {ds_path}')

    backup = f"{ds_path}-backup-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copytree(ds_path, backup)
    print(f'backup   {backup}')

    from changedetectionio.blueprint.ui.views import job_keywords_rule
    from changedetectionio.store import ChangeDetectionStore
    ds = ChangeDetectionStore(datastore_path=ds_path, include_default_watches=False, version_tag='0.70.4')
    app = ds.data['settings']['application']
    watching = ds.data['watching']

    # ---- 2. remove simulated history ----
    for uuid in [u for u, w in watching.items() if (w.get('title') or '').startswith('[Sample data]')]:
        print('removed  ', watching[uuid].get('title'), '(simulated history)')
        ds.delete(uuid)
    if ds.tag_exists_by_name('Sample data (simulated)'):
        tag_uuid = ds.tag_uuid_for_title('Sample data (simulated)')
        app['tags'].pop(tag_uuid, None)

    # ---- 4a. tidy the controlled demo ----
    for uuid, w in list(watching.items()):
        url = w.get('url', '')
        if '.webpulse-demo.test' not in url:
            continue
        if 'clock.webpulse-demo.test' in url:
            print('removed  ', w.get('title'), '(changed every minute - would send an alert every minute)')
            ds.delete(uuid)
            continue
        w['notification_urls'] = []          # use the normal Email/Telegram settings (the old json:// receiver is blocked by SSRF protection)
        if 'slow.webpulse-demo.test' in url:
            w['notification_muted'] = True   # concurrency test pages change on every check
        w.commit()

    # A page may be watched twice with different fetch methods (plain HTTP and a real browser)
    existing = {(w.get('url'), w.get('fetch_backend') or 'system') for w in watching.values()}
    job_rule = job_keywords_rule(TECH_KEYWORDS)

    def add(url, tag, extras):
        extras = {'fetch_backend': 'html_requests', **extras}
        if (url, extras['fetch_backend']) in existing:
            print('exists   ', extras.get('title'))
            return
        ds.add_watch(url=url, tag=tag, extras=extras)
        existing.add((url, extras['fetch_backend']))
        print('added    ', extras.get('title'))

    restock = {'processor': 'restock_diff',
               'processor_config_restock_diff': {'in_stock_processing': 'all_changes', 'follow_price_changes': True}}
    jobs = {'filter_text_added': True, 'filter_text_removed': True, 'filter_text_replaced': True, 'extract_text': [job_rule]}

    # ---- 3. real examples ----
    add('https://www.decathlon.in/p/8189216/men-mountain-hiking-warm-fleece-gilet-jacket-black', 'Indian shops (live)',
        {'title': 'Decathlon India - Forclaz men\'s hiking fleece gilet', **restock, **every(hours=12)})
    add('https://www.decathlon.in/p/8189216/men-mountain-hiking-warm-fleece-gilet-jacket-black', 'Indian shops (live)',
        {'title': 'Decathlon India - same gilet, read with a real browser (JavaScript)', 'fetch_backend': 'html_webdriver',
         **restock, **every(hours=24)})
    add('https://sleepyowl.co/products/enamel-mug', 'Indian shops (live)',
        {'title': 'Sleepy Owl Coffee - enamel mug', **restock, **every(hours=24)})
    add('https://www.boat-lifestyle.com/products/stone-650', 'Indian shops (live)',
        {'title': 'boAt Stone 650 Bluetooth speaker', **restock, **every(hours=24)})

    add('https://job-boards.greenhouse.io/hackerrank', JOBS,
        {'title': 'HackerRank careers (Greenhouse job board) - technical roles', 'include_filters': ['.job-post'], **jobs, **every(hours=12)})
    add('https://jobs.lever.co/meesho', JOBS,
        {'title': 'Meesho careers (Lever job board) - technical roles', 'include_filters': ['.posting-title'], **jobs, **every(hours=12)})
    add('https://www.python.org/jobs/', JOBS,
        {'title': 'Python.org job board - Python developer jobs', 'include_filters': ['.list-recent-jobs h2 a'],
         'filter_text_added': True, 'filter_text_removed': True, 'filter_text_replaced': True, **every(hours=6)})

    # Hacker News changes several times an hour - keep it as a "frequent change" example, without alerts
    for w in watching.values():
        if w.get('url') == 'https://news.ycombinator.com/':
            w['notification_muted'] = True
            w.commit()

    # ---- 4b. controlled demo careers page ----
    add('http://careers.webpulse-demo.test/jobs.html', f'{JOBS}, Demo site (simulated)',
        {'title': '[Demo] DemoCorp careers page - technical roles', 'proxy': DEMO_PROXY, 'include_filters': ['#job-list'],
         **jobs, **every(hours=24)})

    # ---- 5. alert wording ----
    app['notification_title'] = 'WebPulse: {{watch_title}} changed'
    app['notification_body'] = ('{{watch_title}}\n{{watch_url}}\n\nWhat changed (green = added, red = removed):\n'
                                '{{diff}}\n\nFull history in WebPulse: {{diff_url}}\n')
    app['notification_format'] = 'htmlcolor'
    app['base_url'] = 'http://127.0.0.1:5000'
    ds.data['settings']['requests']['proxy'] = 'no-proxy'
    ds.commit()

    # Controlled demo site: a clear product name, the starting job list
    os.makedirs(site_dir, exist_ok=True)
    state_file = os.path.join(site_dir, 'state.json')
    try:
        state = json.load(open(state_file))
    except (OSError, ValueError):
        state = {}
    state.setdefault('price', '2999.00')
    state['name'] = 'Wireless Earbuds Pro (WebPulse demo product)'
    state.setdefault('jobs', 'Backend Engineer (Python) - Bengaluru|Data Engineer - Hyderabad|Software Engineering Intern - Remote')
    state.setdefault('stock', 'InStock')
    if '<' in state.get('text', '<'):
        # The demo site now shows its text as plain text (HTML is escaped)
        state['text'] = 'Company news: version 3.0 of our app is available now.'
    json.dump(state, open(state_file, 'w'))

    print(f'\nReady: {len(watching)} watches in {ds_path}')
    sys.stdout.flush()
    os._exit(0)  # the store starts background threads; nothing else to wait for


if __name__ == '__main__':
    main()

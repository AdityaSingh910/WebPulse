"""WebPulse LAB demonstrations (demo tooling, not part of the app). Drives the isolated LAB instance through
its REST API, exactly as a user/script would, and changes the local fixture site between checks.

    python demo/lab_demo.py setup        create the [LAB] watches (removes the non-LAB default watches)
    python demo/lab_demo.py changes      demo 1: text change with additions/deletions/modification
    python demo/lab_demo.py price        demo 2+3: Rs 2,999 -> Rs 2,499, then out of stock -> back in stock
    python demo/lab_demo.py all          setup + changes + price

LAB instance: http://127.0.0.1:5001   fixture site: http://127.0.0.1:8199   (see demo/lab.ps1)
"""
import json
import sys
import time

import requests

LAB = 'http://127.0.0.1:5001'
FIX = 'http://127.0.0.1:8199'
DS = r'C:\Users\adity\cdio-data\webpulse-lab'
NOTIFY = 'json://127.0.0.1:8199/notify'
TAG = 'LAB - local fixture (controlled)'
TAG_CONC = 'LAB - concurrency test (controlled)'

PAGE_V1 = ('Release bulletin<br>Version 3.0 is available now<br>New: dashboard themes<br>'
           'Known issue: slow exports on large files<br>Contact: support@example.com')
PAGE_V2 = ('Release bulletin<br>Version 3.1 is available now<br>New: dashboard themes<br>'
           'New: price alerts by e-mail<br>Contact: support@example.com')


def key():
    return json.load(open(DS + r'\changedetection.json', encoding='utf-8'))['settings']['application']['api_access_token']


def api(method, path, **kw):
    r = requests.request(method, LAB + '/api/v1' + path, headers={'x-api-key': key()}, timeout=30, **kw)
    r.raise_for_status()
    return r.json() if r.content else None


def fixture(**state):
    return requests.post(FIX + '/set', params=state, timeout=10).json()


def watches():
    return api('GET', '/watch')


def find(title_part):
    for uuid, w in watches().items():
        if title_part in (w.get('title') or ''):
            return uuid
    raise SystemExit(f'watch not found: {title_part} - run "setup" first')


def recheck_and_wait(uuid, label):
    w0 = api('GET', f'/watch/{uuid}')
    before, last0 = int(w0.get('history_n') or 0), (w0.get('last_checked') or 0)
    time.sleep(1.2)  # snapshots are keyed by second
    api('GET', f'/watch/{uuid}?recheck=1')
    t0 = time.time()
    while time.time() - t0 < 120:
        w = api('GET', f'/watch/{uuid}')
        if (w.get('last_checked') or 0) > last0 and not w.get('checking_now'):
            break
        time.sleep(1)
    after = int(w.get('history_n') or 0)
    state = w.get('processor_state_restock_diff')
    print(f'  {label:<42} snapshots {before} -> {after}  {"change detected" if after > before else "no change"}'
          + (f'  state={state}' if state else ''))
    return w


def setup():
    fixture(price='2999.00', stock='InStock', text=PAGE_V1)
    for uuid, w in watches().items():
        if not (w.get('title') or '').startswith('[LAB]'):
            api('DELETE', f'/watch/{uuid}')
            print(f'removed default watch {w.get("url")}')
    existing = {w.get('title') for w in watches().values()}

    def add(body):
        if body['title'] in existing:
            print(f'exists  {body["title"]}')
            return
        r = api('POST', '/watch', json=body)
        print(f'created {body["title"]}  ({r["uuid"]})')

    add({'url': FIX + '/page.html', 'title': '[LAB] News page - change detection demo', 'tag': TAG,
         'notification_urls': [NOTIFY]})
    add({'url': FIX + '/product.html', 'title': '[LAB] Demo product - price & stock (INR)', 'tag': TAG,
         'processor': 'restock_diff', 'notification_urls': [NOTIFY],
         'processor_config_restock_diff': {'in_stock_processing': 'all_changes', 'follow_price_changes': True}})
    add({'url': FIX + '/js.html?fetched-with=requests', 'title': '[LAB] JavaScript page - plain HTTP (static)',
         'tag': TAG, 'fetch_backend': 'html_requests'})
    add({'url': FIX + '/js.html?fetched-with=playwright', 'title': '[LAB] JavaScript page - Playwright/Edge (dynamic)',
         'tag': TAG, 'fetch_backend': 'html_webdriver'})
    for i in range(1, 9):
        add({'url': f'{FIX}/slow.html?d=8&n={i}', 'title': f'[LAB] Concurrency test - slow page {i} (8 s)',
             'tag': TAG_CONC})
    print('setup done - first checks are running now (the 8 slow pages take ~25 s with 3 workers)')


def changes():
    uuid = find('[LAB] News page')
    print('Demo 1 - change detection on the LAB news page')
    fixture(text=PAGE_V1)
    recheck_and_wait(uuid, 'baseline (version 3.0 bulletin)')
    fixture(text=PAGE_V2)
    recheck_and_wait(uuid, 'edited: 3.0->3.1, -known issue, +price alerts')


def price():
    uuid = find('[LAB] Demo product')
    print('Demo 2+3 - price and stock on the LAB demo product')
    steps = [
        (dict(price='2999.00', stock='InStock'), 'Rs 2,999 in stock (baseline)'),
        (dict(price='2499.00', stock='InStock'), 'price drop Rs 2,999 -> Rs 2,499'),
        (dict(price='2499.00', stock='OutOfStock'), 'in stock -> OUT of stock'),
        (dict(price='2499.00', stock='InStock'), 'out of stock -> back IN stock'),
    ]
    for state, label in steps:
        fixture(**state)
        recheck_and_wait(uuid, label)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if cmd in ('setup', 'all'):
        setup()
    if cmd in ('changes', 'all'):
        time.sleep(3)
        changes()
    if cmd in ('price', 'all'):
        price()

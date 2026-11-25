"""End-to-end regression tests for the simplified changedetection.io fork.

The upstream pytest suite needs fork() (pytest-flask live_server) and cannot run on native Windows,
so these tests drive a real running instance over HTTP instead (REST API + UI pages).

Modes
  core      18 core checks (C01-C18) + extended checks (E..). Needs ALLOW_IANA_RESTRICTED_ADDRESSES=true
            on the app under test because the fixture site is on 127.0.0.1.
  persist   run after restarting the app on the same datastore: data must survive (P..)
  security  run against an instance WITHOUT the SSRF bypass and WITH SALTED_PASS set (S..)

Usage: python test_e2e.py <mode> <datastore_dir> <base_url> <fixture_url> <work_dir> [options]
  --expect-removed=/path1,/path2   (core) these URLs must return 404
  --expect-no-ui=word1,word2       (core) these markers must not appear in dashboard/settings/edit/diff pages
  --password=XXX                   (security) the plain password matching SALTED_PASS
"""
import json
import os
import re
import sys
import time

import requests

MODE, DS, BASE, FIX, WORK = sys.argv[1:6]
OPTS = dict(a[2:].split('=', 1) for a in sys.argv[6:] if a.startswith('--') and '=' in a)
LOG = os.path.join(WORK, 'notifications.log')
STATE_FILE = os.path.join(WORK, 'e2e_state.json')
results = []


def check(cid, name, ok, detail=''):
    results.append({'id': cid, 'name': name, 'ok': bool(ok), 'detail': str(detail)[:300]})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} {name} {str(detail)[:160]}", flush=True)


def wait_up():
    for _ in range(90):
        try:
            requests.get(BASE + '/', timeout=3, allow_redirects=False)
            return True
        except Exception:
            time.sleep(1)
    return False


def api_key():
    return json.load(open(os.path.join(DS, 'changedetection.json'), encoding='utf-8'))['settings']['application']['api_access_token']


def make_api(key):
    h = {'x-api-key': key, 'Content-Type': 'application/json'}
    return lambda m, p, **kw: requests.request(m, BASE + '/api/v1' + p, headers={**h, **kw.pop('headers', {})}, timeout=30, **kw)


def wait_checked(api, uuid, n_history, timeout=90):
    t0, w = time.time(), {}
    while time.time() - t0 < timeout:
        w = api('GET', f'/watch/{uuid}').json()
        if w.get('last_checked') and int(w.get('history_n') or 0) >= n_history and not w.get('checking_now'):
            return w
        time.sleep(1)
    return w


def read_log():
    try:
        return [l for l in open(LOG, encoding='utf-8').read().splitlines() if l.strip()]
    except OSError:
        return []


def finish():
    passed = sum(r['ok'] for r in results)
    print(f"\nSUMMARY {MODE}: {passed}/{len(results)} passed", flush=True)
    with open(os.path.join(WORK, f'results_{MODE}.json'), 'w') as f:
        json.dump({'mode': MODE, 'passed': passed, 'total': len(results), 'results': results}, f, indent=1)
    sys.exit(0 if passed == len(results) else 1)


def mode_core():
    api = make_api(api_key())
    requests.post(FIX + '/set?price=499.00&stock=InStock&text=Version+one+of+the+page.')
    open(LOG, 'w').close()
    notif = [FIX.replace('http://', 'json://') + '/notify']

    # ---------------- 18 core regression checks (identical to the original baseline) ----------------
    r = api('GET', '/systeminfo')
    check('C01', 'API systeminfo', r.status_code == 200, r.text[:100])
    r = api('POST', '/watch', json={'url': FIX + '/page.html', 'title': 'Text page', 'notification_urls': notif})
    check('C02', 'API create text watch', r.status_code in (200, 201), r.text[:100])
    text_uuid = r.json()['uuid']
    r = api('POST', '/watch', json={'url': FIX + '/product.html', 'title': 'Product', 'processor': 'restock_diff',
                                   'notification_urls': notif})
    check('C03', 'API create restock/price watch', r.status_code in (200, 201), r.text[:100])
    prod_uuid = r.json()['uuid']

    w1, w2 = wait_checked(api, text_uuid, 1), wait_checked(api, prod_uuid, 1)
    check('C04', 'Scheduler/worker ran first check (text)', int(w1.get('history_n') or 0) >= 1, f"err={w1.get('last_error')}")
    check('C05', 'Scheduler/worker ran first check (product)', int(w2.get('history_n') or 0) >= 1, f"err={w2.get('last_error')}")
    rs = w2.get('processor_state_restock_diff') or {}
    check('C06', 'Price extracted from JSON-LD', rs.get('price') == 499.0, json.dumps(rs))
    check('C07', 'Stock extracted', rs.get('in_stock') is True, f"in_stock={rs.get('in_stock')}")

    time.sleep(1.5)
    requests.post(FIX + '/set?price=449.00&stock=OutOfStock&text=Version+two+-+BIG+NEWS.')
    api('GET', f'/watch/{text_uuid}?recheck=1')
    api('GET', f'/watch/{prod_uuid}?recheck=1')
    w1, w2 = wait_checked(api, text_uuid, 2), wait_checked(api, prod_uuid, 2)
    check('C08', 'Text change detected (2 snapshots)', int(w1.get('history_n') or 0) >= 2, f"history_n={w1.get('history_n')}")
    check('C09', 'Price/stock change detected (2 snapshots)', int(w2.get('history_n') or 0) >= 2, f"history_n={w2.get('history_n')}")
    rs = w2.get('processor_state_restock_diff') or {}
    check('C10', 'New price 449 recorded', rs.get('price') == 449.0 and rs.get('last_price') == 499.0, json.dumps(rs))

    h = api('GET', f'/watch/{text_uuid}/history').json()
    ts = sorted(h.keys())
    check('C11', 'API history list', len(ts) >= 2, ts)
    d = api('GET', f'/watch/{text_uuid}/difference/{ts[0]}/{ts[-1]}') if len(ts) >= 2 else None
    check('C12', 'API diff between snapshots', d is not None and 'BIG NEWS' in d.text, d.text[:120].replace('\n', ' | ') if d else '')

    s = requests.Session()
    r = s.get(f'{BASE}/diff/{prod_uuid}/processor-data', timeout=30)
    ok = False
    try:
        j = r.json()
        ok = [p['price'] for p in j['series']] == [499.0, 449.0] and j['summary']['avg'] == 474.0
    except Exception:
        pass
    check('C13', 'Price history chart data (series + analytics)', ok, r.text[:160])
    r = s.get(f'{BASE}/diff/{prod_uuid}', timeout=30)
    check('C14', 'Price history page renders', r.status_code == 200 and 'restock-graph' in r.text, f'status={r.status_code}')
    r = s.get(BASE + '/', timeout=30)
    check('C15', 'Dashboard renders with watches', r.status_code == 200 and 'Product' in r.text, f'status={r.status_code}')
    r = api('GET', '/search?q=Product')
    check('C16', 'API search', r.status_code == 200 and prod_uuid in r.text)
    r = api('GET', '/tags')
    check('C17', 'API tags', r.status_code == 200)
    for _ in range(30):
        if len(read_log()) >= 2:
            break
        time.sleep(1)
    lines = read_log()
    check('C18', 'Notifications delivered (Apprise json://)', len(lines) >= 1, f'{len(lines)} received')

    # ---------------- Extended checks ----------------
    r = requests.get(BASE + '/api/v1/watch', timeout=10)
    check('E01', 'API rejects missing API key', r.status_code in (401, 403), r.status_code)
    r = requests.get(BASE + '/api/v1/watch', headers={'x-api-key': 'wrong'}, timeout=10)
    check('E02', 'API rejects wrong API key', r.status_code in (401, 403), r.status_code)
    r = api('POST', '/watch', json={'url': 'file:///c:/windows/win.ini'})
    check('E03', 'URL validation rejects file://', r.status_code == 400, f'{r.status_code} {r.text[:80]}')
    r = api('POST', '/watch', json={'url': 'javascript:alert(1)'})
    check('E04', 'URL validation rejects javascript:', r.status_code == 400, f'{r.status_code} {r.text[:80]}')

    r = s.get(f'{BASE}/edit/{text_uuid}', timeout=30)
    check('E05', 'Edit page (text watch) renders', r.status_code == 200 and 'csrf_token' in r.text, r.status_code)
    r = s.get(f'{BASE}/edit/{prod_uuid}', timeout=30)
    check('E06', 'Edit page (price watch) renders', r.status_code == 200 and 'csrf_token' in r.text, r.status_code)
    r = s.get(f'{BASE}/settings', timeout=30)
    check('E07', 'Settings page renders', r.status_code == 200 and 'csrf_token' in r.text, r.status_code)
    r = s.get(f'{BASE}/diff/{text_uuid}', timeout=30)
    check('E08', 'Text diff page renders the change', r.status_code == 200 and 'BIG NEWS' in r.text, r.status_code)
    r = s.get(f'{BASE}/preview/{text_uuid}', timeout=30)
    check('E09', 'Preview page renders', r.status_code == 200 and 'BIG NEWS' in r.text, r.status_code)
    r = s.get(f'{BASE}/diff/{prod_uuid}/processor-export.xlsx', timeout=30)
    check('E10', 'Price history XLSX export', r.status_code == 200 and r.content[:2] == b'PK', f'{r.status_code} {len(r.content)}B')
    check('E11', 'Notification payload references the watch', any('8099' in l or 'Product' in l or 'Text page' in l for l in lines), lines[:1])

    r = api('POST', '/tag', json={'title': 'Electronics'})
    tag_uuid = (r.json() or {}).get('uuid') if r.status_code in (200, 201) else None
    r2 = api('PUT', f'/watch/{prod_uuid}', json={'tags': [tag_uuid]}) if tag_uuid else None
    w = api('GET', f'/watch/{prod_uuid}').json()
    check('E12', 'API tag create + assign to watch', tag_uuid and tag_uuid in (w.get('tags') or []), f'tag={tag_uuid}')

    r = api('POST', '/import', data=f'{FIX}/page.html?imported=1\n{FIX}/page.html?imported=2',
            headers={'Content-Type': 'text/plain'})
    imported = r.json() if r.status_code == 200 else []
    check('E13', 'API bulk import of URLs', isinstance(imported, list) and len(imported) == 2, f'{r.status_code} {r.text[:80]}')

    # Scheduler: a watch with a 5 s interval must be re-checked automatically (no manual recheck)
    r = api('POST', '/watch', json={'url': FIX + '/page.html?sched=1', 'title': 'Scheduled',
                                   'time_between_check_use_default': False,
                                   'time_between_check': {'seconds': 5}})
    sched_uuid = r.json()['uuid']
    w = wait_checked(api, sched_uuid, 1)
    first = w.get('last_checked') or 0
    t0, later = time.time(), first
    while time.time() - t0 < 40 and later <= first:
        time.sleep(2)
        later = api('GET', f'/watch/{sched_uuid}').json().get('last_checked') or 0
    check('E14', 'Scheduler re-checks on its own interval', later > first, f'last_checked {first} -> {later}')

    # Concurrency: 6 slow (3 s) pages; with >=3 workers at least 2 must be in flight at once
    slow = [api('POST', '/watch', json={'url': f'{FIX}/slow.html?d=3&n={i}', 'title': f'Slow {i}'}).json()['uuid'] for i in range(6)]
    peak, t0 = 0, time.time()
    while time.time() - t0 < 60:
        cn = api('GET', '/systeminfo').json().get('checking_now') or []
        peak = max(peak, len(cn))
        done = all(int(api('GET', f'/watch/{u}').json().get('history_n') or 0) >= 1 for u in slow)
        if done:
            break
        time.sleep(0.5)
    check('E15', 'Concurrent workers (peak parallel checks >= 2, all 6 done)', peak >= 2 and done, f'peak={peak} done={done} in {time.time() - t0:.1f}s')

    r = s.get(f'{BASE}/queue', timeout=30)
    check('E16', 'Queue/status page renders', r.status_code == 200, r.status_code)
    r = s.get(f'{BASE}/backups/', timeout=30)
    check('E17', 'Backups page renders', r.status_code == 200, r.status_code)
    victim = slow[-1]
    r = api('DELETE', f'/watch/{victim}')
    r2 = api('GET', f'/watch/{victim}')
    check('E18', 'API delete watch', r.status_code in (200, 204) and r2.status_code == 404, f'{r.status_code}/{r2.status_code}')

    # Every remaining UI page must render (catches template errors from removed features)
    pages = ['/tags/list', f'/tags/edit/{tag_uuid}', '/imports/import', '/settings/notifications/',
             '/settings/notification-logs', '/backups/create', '/clear_history', f'/diff/{text_uuid}/extract',
             '/queue.json', f'/edit/{sched_uuid}', '/login', '/static/flags/1x1/gb.svg']
    bad = {}
    for p in pages:
        r = s.get(BASE + p, timeout=30, allow_redirects=False)
        if r.status_code not in (200, 302):
            bad[p] = r.status_code
    check('E21', f'All other UI pages render ({len(pages)} pages)', not bad, bad or 'all OK')

    # Group (tag) edit form saves via the real form + CSRF token
    page = s.get(f'{BASE}/tags/edit/{tag_uuid}', timeout=30).text
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page) or re.search(r'value="([^"]+)"[^>]*name="csrf_token"', page)
    r = s.post(f'{BASE}/tags/edit/{tag_uuid}', data={'csrf_token': m.group(1) if m else '', 'title': 'Electronics-renamed'},
               timeout=30, allow_redirects=False)
    t = api('GET', '/tags').json()
    check('E22', 'Group edit form saves (UI + CSRF)', r.status_code in (200, 302) and 'Electronics-renamed' in json.dumps(t), r.status_code)

    removed = [p for p in OPTS.get('expect-removed', '').split(',') if p]
    if removed:
        bad = {}
        for p in removed:
            sc = s.get(BASE + p, timeout=15, allow_redirects=False).status_code
            if sc != 404:
                bad[p] = sc
        check('E19', f'Removed features return 404 ({len(removed)} URLs)', not bad, bad or 'all 404')
    no_ui = [w for w in OPTS.get('expect-no-ui', '').split(',') if w]
    if no_ui:
        page = ''.join(s.get(BASE + p, timeout=30).text for p in
                       ('/', '/settings', f'/edit/{text_uuid}', f'/edit/{prod_uuid}', f'/diff/{text_uuid}', f'/diff/{prod_uuid}'))
        leftovers = [w for w in no_ui if w.lower() in page.lower()]
        check('E20', f'No UI elements of removed features ({len(no_ui)} markers)', not leftovers, leftovers or 'clean')

    json.dump({'text_uuid': text_uuid, 'prod_uuid': prod_uuid, 'tag_uuid': tag_uuid, 'sched_uuid': sched_uuid},
              open(STATE_FILE, 'w'))


def mode_persist():
    st = json.load(open(STATE_FILE))
    api = make_api(api_key())
    w = api('GET', f"/watch/{st['text_uuid']}")
    check('P01', 'Text watch persisted across restart', w.status_code == 200 and int(w.json().get('history_n') or 0) >= 2, w.status_code)
    w = api('GET', f"/watch/{st['prod_uuid']}").json()
    rs = w.get('processor_state_restock_diff') or {}
    check('P02', 'Price state persisted', rs.get('price') == 449.0 and rs.get('in_stock') is False, json.dumps(rs))
    check('P03', 'Tag assignment persisted', st['tag_uuid'] in (w.get('tags') or []))
    h = api('GET', f"/watch/{st['text_uuid']}/history").json()
    ts = sorted(h.keys())
    d = api('GET', f"/watch/{st['text_uuid']}/history/{ts[-1]}")
    check('P04', 'Snapshot content readable after restart', 'BIG NEWS' in d.text, d.text[:80])
    r = requests.get(f"{BASE}/diff/{st['prod_uuid']}/processor-data", timeout=30)
    check('P05', 'Price history series persisted', r.status_code == 200 and len(r.json().get('series', [])) == 2)


def mode_security():
    s = requests.Session()
    r = s.get(BASE + '/', allow_redirects=False, timeout=10)
    check('S01', 'Password protection: dashboard redirects to login', r.status_code in (301, 302) and 'login' in r.headers.get('Location', ''), r.status_code)
    page = s.get(BASE + '/login', timeout=10).text
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page) or re.search(r'value="([^"]+)"[^>]*name="csrf_token"', page)
    token = m.group(1) if m else ''
    s.post(BASE + '/login', data={'csrf_token': token, 'password': 'definitely-wrong'}, timeout=10)
    r = s.get(BASE + '/', allow_redirects=False, timeout=10)
    check('S02', 'Wrong password is refused', r.status_code in (301, 302), r.status_code)
    page = s.get(BASE + '/login', timeout=10).text
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page) or re.search(r'value="([^"]+)"[^>]*name="csrf_token"', page)
    token = m.group(1) if m else ''
    s.post(BASE + '/login', data={'csrf_token': token, 'password': OPTS.get('password', '')}, timeout=10)
    r = s.get(BASE + '/', allow_redirects=False, timeout=10)
    check('S03', 'Correct password logs in', r.status_code == 200, r.status_code)
    r = requests.post(BASE + '/login', data={'password': OPTS.get('password', '')}, timeout=10, allow_redirects=False)
    check('S04', 'CSRF: login POST without token is rejected', r.status_code == 400, r.status_code)

    api = make_api(api_key())
    check('S05', 'API key auth still works with password on', api('GET', '/systeminfo').status_code == 200)

    for cid, target in (('S06', FIX + '/page.html'), ('S07', 'http://169.254.169.254/latest/meta-data/'),
                        ('S08', 'http://10.0.0.1/')):
        r = api('POST', '/watch', json={'url': target})
        if r.status_code == 400:
            check(cid, f'SSRF blocked at creation: {target}', True, r.text[:100])
            continue
        uuid = r.json().get('uuid')
        t0, w = time.time(), {}
        while time.time() - t0 < 40:
            w = api('GET', f'/watch/{uuid}').json()
            if w.get('last_checked') and not w.get('checking_now'):
                break
            time.sleep(1)
        check(cid, f'SSRF blocked at fetch: {target}', int(w.get('history_n') or 0) == 0 and w.get('last_error'), w.get('last_error'))


def mode_browser():
    """Needs PLAYWRIGHT_DRIVER_URL on the app (headless Edge/Chrome over CDP) + the SSRF bypass for the fixture."""
    api = make_api(api_key())
    requests.post(FIX + '/set?price=499.00&stock=InStock&text=Version+one+of+the+page.')
    r = api('POST', '/watch', json={'url': FIX + '/js.html', 'title': 'JS via browser', 'fetch_backend': 'html_webdriver'})
    check('B01', 'Create watch using the Playwright (html_webdriver) fetcher', r.status_code in (200, 201), r.text[:100])
    js_uuid = r.json().get('uuid')
    r = api('POST', '/watch', json={'url': FIX + '/js.html?plain=1', 'title': 'JS via requests', 'fetch_backend': 'html_requests'})
    plain_uuid = r.json().get('uuid')
    r = api('POST', '/watch', json={'url': FIX + '/js-product.html', 'title': 'JS product', 'processor': 'restock_diff',
                                   'fetch_backend': 'html_webdriver'})
    jsprod_uuid = r.json().get('uuid')

    w = wait_checked(api, js_uuid, 1, timeout=120)
    ts = sorted(api('GET', f'/watch/{js_uuid}/history').json().keys())
    snap = api('GET', f'/watch/{js_uuid}/history/{ts[-1]}').text if ts else ''
    check('B02', 'Browser fetch executes JavaScript', 'Rendered by JavaScript' in snap, f"err={w.get('last_error')} snap={snap[:80]!r}")
    wait_checked(api, plain_uuid, 1)
    ts2 = sorted(api('GET', f'/watch/{plain_uuid}/history').json().keys())
    snap2 = api('GET', f'/watch/{plain_uuid}/history/{ts2[-1]}').text if ts2 else ''
    check('B03', 'Control: plain HTTP fetch does NOT see JS content', 'Loading...' in snap2 and 'Rendered by JavaScript' not in snap2, snap2[:80])
    w = wait_checked(api, jsprod_uuid, 1, timeout=120)
    rs = w.get('processor_state_restock_diff') or {}
    check('B04', 'Price injected by JavaScript extracted via browser', rs.get('price') == 499.0 and rs.get('in_stock') is True, f"{json.dumps(rs)} err={w.get('last_error')}")
    check('B05', 'Browser screenshot saved', os.path.isfile(os.path.join(DS, js_uuid, 'last-screenshot.png')))
    check('B06', 'Visual-selector element data saved', os.path.isfile(os.path.join(DS, js_uuid, 'elements.deflate')))

    # change detection through the browser
    requests.post(FIX + '/set?text=Version+two+-+BIG+NEWS.')
    time.sleep(1.2)
    api('GET', f'/watch/{js_uuid}?recheck=1')
    w = wait_checked(api, js_uuid, 2, timeout=120)
    ts = sorted(api('GET', f'/watch/{js_uuid}/history').json().keys())
    d = api('GET', f'/watch/{js_uuid}/difference/{ts[0]}/{ts[-1]}').text if len(ts) >= 2 else ''
    check('B07', 'Change detected on a JS-rendered page', 'BIG NEWS' in d, d[:100].replace('\n', ' | '))
    s = requests.Session()
    r = s.get(f'{BASE}/edit/{js_uuid}', timeout=30)
    check('B08', 'Edit page offers the browser tools (Visual Selector / Browser Steps)',
          r.status_code == 200 and 'visualselector' in r.text and 'browser-steps' in r.text, r.status_code)


if not wait_up():
    print('App did not come up')
    sys.exit(2)
{'core': mode_core, 'persist': mode_persist, 'security': mode_security, 'browser': mode_browser}[MODE]()
finish()

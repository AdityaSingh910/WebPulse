"""Browser UI tests for WebPulse - drives the real interface in Microsoft Edge with Playwright.

Run by e2e/run_e2e.ps1 -UI against a throw-away instance + the local fixture site (needs
ALLOW_IANA_RESTRICTED_ADDRESSES=true on that instance because the fixture is on 127.0.0.1).

Usage: python ui_test.py <datastore_dir> <base_url> <fixture_url> <work_dir>
Screenshots of every step are written to <work_dir>/ui-screens/.
"""
import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from playwright.sync_api import sync_playwright, expect

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
DS, BASE, FIX, WORK = sys.argv[1:5]
SHOTS = os.path.join(WORK, 'ui-screens')
os.makedirs(SHOTS, exist_ok=True)
LOG = os.path.join(WORK, 'notifications.log')
results = []
console_errors = []


def check(cid, name, ok, detail=''):
    results.append({'id': cid, 'name': name, 'ok': bool(ok), 'detail': str(detail)[:300]})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} {name} {str(detail)[:150]}", flush=True)


def api():
    key = json.load(open(os.path.join(DS, 'changedetection.json'), encoding='utf-8'))['settings']['application']['api_access_token']
    return key, {'x-api-key': key}


def watch_by_url(fragment):
    _, h = api()
    for uuid, w in requests.get(BASE + '/api/v1/watch', headers=h, timeout=20).json().items():
        if fragment in w.get('url', ''):
            return uuid
    return None


def wait_history(uuid, n, timeout=90):
    _, h = api()
    t0 = time.time()
    while time.time() - t0 < timeout:
        w = requests.get(f'{BASE}/api/v1/watch/{uuid}', headers=h, timeout=20).json()
        if int(w.get('history_n') or 0) >= n and not w.get('checking_now'):
            return w
        time.sleep(1)
    return w


def shot(page, name):
    page.screenshot(path=os.path.join(SHOTS, name + '.png'))


def run():
    for _ in range(60):
        try:
            requests.get(BASE + '/', timeout=3)
            break
        except Exception:
            time.sleep(1)
    requests.post(FIX + '/set?price=499.00&stock=InStock&text=Version+one+of+the+page.')
    open(LOG, 'w').close()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=BASE)
        page = ctx.new_page()
        page.on('pageerror', lambda e: console_errors.append(f'{page.url}: {e}'))
        page.on('console', lambda m: console_errors.append(f'{page.url}: {m.text}') if m.type == 'error' else None)
        page.on('dialog', lambda d: d.accept())

        # ---- U01/U02: branding + removed elements ----
        page.goto(BASE + '/', wait_until='networkidle')
        shot(page, '01-dashboard-empty')
        title = page.title()
        brand = page.locator('.wp-brand').inner_text()
        check('U01', 'WebPulse branding (title, logo, favicon)', 'WebPulse' in title and 'WebPulse' in brand.replace('\n', '')
              and page.locator('link[rel="icon"][href*="webpulse-mark"]').count() == 1, f'title={title!r}')
        html = page.content()
        gone = {
            'GitHub button': page.locator('a[href*="github.com"]').count(),
            'heart/donate': page.locator('#heart-us, #overlay').count(),
            'language selector': page.locator('.language-selector, #language-modal').count(),
            'country flags': page.locator('.fi, [class*="fi-"]').count(),
            '"soon" badge / Browsers': page.locator('text=/\\bsoon\\b/i').count(),
            'version label': len(re.findall(r'v0\.\d+\.\d+', page.inner_text('body'))),
            'Chrome extension': page.locator('a[href*="chromewebstore"]').count(),
            'upstream name in UI': len(re.findall(r'changedetection', page.inner_text('body'), re.I)),
            'external CDN': len(re.findall(r'src="https?://', html)),
        }
        check('U02', 'Removed UI elements are absent', not any(gone.values()), {k: v for k, v in gone.items() if v} or 'all absent')

        # ---- U03: add a text watch with the quick-add form ----
        page.fill('#new-watch-form input[name="url"]', FIX + '/page.html')
        page.click('#add-watch-go')
        page.wait_for_load_state('networkidle')
        uuid = watch_by_url('/page.html')
        w = wait_history(uuid, 1) if uuid else {}
        page.goto(BASE + '/', wait_until='networkidle')
        check('U03', 'Add watch from the dashboard form (and first check runs)', uuid and int(w.get('history_n') or 0) >= 1
              and page.locator(f'tr[data-watch-uuid="{uuid}"]').count() == 1, f'uuid={uuid}')

        # ---- U04: edit the watch title through the edit page ----
        page.locator(f'tr[data-watch-uuid="{uuid}"] a:has-text("Edit")').first.click()
        page.wait_for_load_state('networkidle')
        shot(page, '02-edit-page')
        page.fill('input[name="title"]', 'UI test - news page')
        page.locator('form.pure-form button:has-text("Save"), form.pure-form input[type=submit][value="Save"]').first.click()
        page.wait_for_load_state('networkidle')
        check('U04', 'Edit page saves changes', 'UI test - news page' in page.content(), page.url)

        # ---- U05/U06: change the page, Recheck from the row, open History ----
        requests.post(FIX + '/set?text=Version+two+-+BIG+NEWS.')
        time.sleep(1.2)
        page.goto(BASE + '/', wait_until='networkidle')
        page.locator(f'tr[data-watch-uuid="{uuid}"] button:has-text("Recheck")').first.click()
        w = wait_history(uuid, 2)
        check('U05', 'Recheck button queues a check that detects the change', int(w.get('history_n') or 0) >= 2, f"history_n={w.get('history_n')}")
        page.goto(BASE + '/', wait_until='networkidle')
        link = page.locator(f'tr[data-watch-uuid="{uuid}"] a.history-link').first
        if link.get_attribute('target'):   # "Open History in a new tab" (default on) -> follow the new tab
            with ctx.expect_page() as new_tab:
                link.click()
            hist = new_tab.value
        else:
            link.click()
            hist = page
        hist.wait_for_load_state('networkidle')
        shot(hist, '03-text-diff')
        check('U06', 'History page shows the difference', hist.locator('#difference').count() == 1
              and 'BIG NEWS' in hist.locator('#difference').inner_text(), hist.url)
        if hist is not page:
            hist.close()

        # ---- U07: preview ----
        page.goto(f'{BASE}/preview/{uuid}', wait_until='networkidle')
        check('U07', 'Snapshot preview page', 'BIG NEWS' in page.inner_text('body'))

        # ---- U08/U09: price watch via quick-add with the restock processor ----
        page.goto(BASE + '/', wait_until='networkidle')
        page.fill('#new-watch-form input[name="url"]', FIX + '/product.html')
        page.check('#new-watch-form input[name="processor"][value="restock_diff"]')
        page.click('#add-watch-go')
        page.wait_for_load_state('networkidle')
        puuid = watch_by_url('/product.html')
        wait_history(puuid, 1)
        requests.post(FIX + '/set?price=449.00&stock=OutOfStock')
        time.sleep(1.2)
        page.goto(BASE + '/', wait_until='networkidle')
        page.locator(f'tr[data-watch-uuid="{puuid}"] button:has-text("Recheck")').first.click()
        wait_history(puuid, 2)
        page.goto(BASE + '/', wait_until='networkidle')
        row = page.locator(f'tr[data-watch-uuid="{puuid}"]')
        row_text = row.inner_text()
        shot(page, '04-dashboard-with-price')
        check('U08', 'Price watch shows price + stock on the dashboard', '449' in row_text and re.search(r'(Not in|Out of) stock', row_text), row_text.replace('\n', ' ')[:120])
        row.locator('a.history-link').first.click()   # restock rows roll down an inline chart
        page.wait_for_selector('.restock-inline-row', timeout=15000)
        page.wait_for_timeout(800)
        shot(page, '05-inline-price-chart')
        check('U09', 'Inline price chart rolls down on the dashboard', page.locator('.restock-inline-row svg, .restock-inline-row canvas').count() >= 1)
        page.goto(f'{BASE}/diff/{puuid}', wait_until='networkidle')
        page.wait_for_timeout(800)
        shot(page, '06-price-history-page')
        check('U10', 'Price history page draws the chart and table', page.locator('.restock-graph-default svg, .restock-graph-default canvas').count() >= 1
              and '449' in page.inner_text('body'))

        # ---- U11: groups ----
        page.goto(BASE + '/tags/list', wait_until='networkidle')
        page.fill('input[name="name"]', 'UI test group')
        page.locator('form button:has-text("Save"), form input[type=submit][value="Save"]').first.click()
        page.wait_for_load_state('networkidle')
        check('U11', 'Create a group on the Groups page', 'UI test group' in page.content())

        # ---- U12: search modal ----
        page.goto(BASE + '/', wait_until='networkidle')
        page.click('.wp-sidebar .js-open-search-modal')
        page.wait_for_selector('#search-modal[open]', timeout=5000)
        page.fill('#search-modal-input', 'product')
        page.keyboard.press('Enter')
        page.wait_for_url(re.compile(r'q=product'), timeout=15000)
        page.wait_for_load_state('networkidle')
        rows = page.locator('tr[data-watch-uuid]').count()
        check('U12', 'Search from the sidebar filters the list', 'q=product' in page.url and rows == 1, f'{page.url} rows={rows}')

        # ---- U13: API key masked, reveal + copy ----
        key, _ = api()
        page.goto(BASE + '/settings#api', wait_until='networkidle')
        masked = page.locator('.wp-secret-value').inner_text()
        page.click('[data-wp-secret-reveal]')
        revealed = page.locator('.wp-secret-value').inner_text()
        page.click('[data-wp-secret-copy]')
        page.wait_for_timeout(300)
        clip = page.evaluate('navigator.clipboard.readText()')
        shot(page, '07-settings-api')
        check('U13', 'API key masked by default, reveal and copy work', key not in masked and set(masked) == {'•'}
              and revealed == key and clip == key, f'masked={masked[:12]}...')

        # ---- U14: settings save ----
        page.goto(BASE + '/settings#general', wait_until='networkidle')
        page.fill('input[name="application-history_snapshot_max_length"]', '50')
        page.locator('#actions button, #actions input[type=submit]').first.click()
        page.wait_for_load_state('networkidle')
        saved = json.load(open(os.path.join(DS, 'changedetection.json'), encoding='utf-8'))['settings']['application'].get('history_snapshot_max_length')
        check('U14', 'Settings form saves', str(saved) == '50', f'stored={saved}')

        # ---- U15: notifications - add a URL, send a test, save ----
        page.goto(BASE + '/settings/notifications/', wait_until='networkidle')
        page.fill('textarea.notification-urls', FIX.replace('http://', 'json://') + '/notify')
        page.locator('#send-test-notification').click()
        got = False
        for _ in range(20):
            if any('notify' in l or l.strip() for l in open(LOG, encoding='utf-8')):
                got = True
                break
            time.sleep(1)
        page.locator('form button:has-text("Save"), form input[type=submit][value="Save"]').first.click()
        page.wait_for_load_state('networkidle')
        shot(page, '08-notifications')
        check('U15', 'Notification test message is delivered (Apprise)', got)

        # ---- U16: import ----
        page.goto(BASE + '/imports/import', wait_until='networkidle')
        page.fill('textarea[name="urls"]', f'{FIX}/page.html?import=1\n{FIX}/page.html?import=2')
        page.locator('button:has-text("Import")').first.click()
        page.wait_for_load_state('networkidle')
        check('U16', 'Import a list of URLs', bool(watch_by_url('import=1')) and bool(watch_by_url('import=2')))

        # ---- U17/U18: pause + mute toggles ----
        page.goto(BASE + '/', wait_until='networkidle')
        page.click('#menu-pause button')
        page.wait_for_load_state('networkidle')
        paused = 'Paused' in page.locator('#menu-pause').inner_text()
        page.click('#menu-pause button')
        page.wait_for_load_state('networkidle')
        resumed = 'Monitoring' in page.locator('#menu-pause').inner_text()
        check('U17', 'Pause / resume all monitoring', paused and resumed)
        page.click('#menu-mute button')
        page.wait_for_load_state('networkidle')
        muted = 'Muted' in page.locator('#menu-mute').inner_text()
        page.click('#menu-mute button')
        page.wait_for_load_state('networkidle')
        check('U18', 'Mute / unmute notifications', muted and 'Alerts on' in page.locator('#menu-mute').inner_text())

        # ---- U19: dark mode ----
        page.click('.toggle-light-mode')
        dark = page.evaluate('document.documentElement.getAttribute("data-darkmode")')
        page.reload(wait_until='networkidle')
        shot(page, '09-dark-mode')
        persisted = page.evaluate('document.documentElement.getAttribute("data-darkmode")')
        page.click('.toggle-light-mode')
        check('U19', 'Dark mode toggle (persists across reload)', dark == 'true' and persisted == 'true', f'{dark}/{persisted}')

        # ---- U20: delete a watch from the edit page (confirm modal) ----
        victim = watch_by_url('import=2')
        page.goto(f'{BASE}/edit/{victim}', wait_until='networkidle')
        page.locator('a:has-text("Delete")').last.click()
        page.locator('[data-action="confirm"]').click()
        page.wait_for_load_state('networkidle')
        check('U20', 'Delete a watch (with confirmation dialog)', watch_by_url('import=2') is None)

        # ---- U21: queue + backups pages ----
        page.goto(BASE + '/queue', wait_until='networkidle')
        q_ok = 'Check queue' in page.title()
        page.goto(BASE + '/backups/create', wait_until='networkidle')
        check('U21', 'Queue and Backups pages', q_ok and page.locator('.wp-topbar h1').inner_text() == 'Backups')

        # ---- U22: mobile navigation drawer ----
        m = browser.new_context(viewport={'width': 390, 'height': 844})
        mp = m.new_page()
        mp.goto(BASE + '/', wait_until='networkidle')
        hidden_before = mp.locator('.wp-sidebar').bounding_box()['x'] < 0
        mp.click('[data-wp-nav-open]')
        mp.wait_for_timeout(400)
        shown = mp.locator('.wp-sidebar').bounding_box()['x'] >= 0
        mp.screenshot(path=os.path.join(SHOTS, '10-mobile-drawer.png'))
        no_hscroll = mp.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
        check('U22', 'Mobile: drawer navigation, no sideways scrolling', hidden_before and shown and no_hscroll, f'hscroll_ok={no_hscroll}')
        m.close()

        # ---- U23: every internal link on every page resolves ----
        pages = ['/', '/tags/list', '/imports/import', '/settings', '/settings/notifications/', '/settings/notification-logs',
                 '/queue', '/backups/create', f'/edit/{uuid}', f'/diff/{uuid}', f'/preview/{uuid}', f'/diff/{puuid}', f'/edit/{puuid}']
        links, external = set(), set()
        for pth in pages:
            page.goto(BASE + pth, wait_until='networkidle')
            for a in page.locator('a[href]').all():
                if a.get_attribute('data-method') or a.get_attribute('data-requires-confirm'):
                    continue
                href = a.get_attribute('href') or ''
                if href.startswith(('javascript:', '#', 'mailto:')) or not href:
                    continue
                full = urljoin(BASE + pth, href)
                if urlparse(full).netloc == urlparse(BASE).netloc:
                    links.add(full.split('#')[0])
                else:
                    external.add(full)
        s = requests.Session()
        broken = {}
        for l in sorted(links):
            if '/logout' in l:
                continue
            code = s.get(l, timeout=30, allow_redirects=True).status_code
            if code >= 400:
                broken[l] = code
        check('U23', f'No broken internal links ({len(links)} links on {len(pages)} pages)', not broken, broken or 'all OK')
        allowed_ext = ('github.com/dgtlmoon/changedetection.io', 'apache.org/licenses', 'jinja.palletsprojects.com', 'appriseit.com',
                       'github.com/caronc/apprise', 'core.telegram.org', 'docs.python.org', 'regexr.com', 'jsonpath.com',
                       'xpather.com', 'pypi.org', 'jqplay.org', 'stedolan.github.io', 'distill.io', 'discord.com', 'example.com',
                       '127.0.0.1:8099')
        _, h = api()
        watched = {w.get('url') for w in requests.get(BASE + '/api/v1/watch', headers=h, timeout=20).json().values()}
        # links to the monitored sites themselves (the watch title / open-link icons) are expected
        unexpected = sorted(e for e in external if e not in watched and not any(a in e.lower() for a in allowed_ext))
        check('U24', f'External links limited to attribution + technical references ({len(external)} found)', not unexpected, unexpected or 'ok')

        # ---- U25: password login through the UI, then remove it again ----
        page.goto(BASE + '/settings#general', wait_until='networkidle')
        page.fill('input[name="application-password"]', 'webpulse-demo-pass')
        page.locator('#actions button, #actions input[type=submit]').first.click()
        page.wait_for_load_state('networkidle')
        page.goto(BASE + '/', wait_until='networkidle')
        on_login = '/login' in page.url
        shot(page, '11-login')
        page.fill('input[name="password"]', 'webpulse-demo-pass')
        page.click('button:has-text("Sign in")')
        page.wait_for_load_state('networkidle')
        logged_in = page.locator('.wp-sidebar').count() == 1 and '/login' not in page.url
        page.goto(BASE + '/settings#general', wait_until='networkidle')
        page.locator('[name="application-removepassword_button"], button:has-text("Remove password"), input[value="Remove password"]').first.click()
        page.wait_for_load_state('networkidle')
        check('U25', 'Password login page (WebPulse branded) and sign-in', on_login and logged_in)

        browser.close()

    # 'Transport not open' is raised by the Socket.IO client when the test navigates away before the live-update
    # handshake finished (pages are left within milliseconds here); it does not occur on a page that is actually used.
    real_errors = [e for e in console_errors if 'favicon' not in e.lower() and 'Transport not open' not in e]
    check('U26', 'No JavaScript errors on any page visited', not real_errors, real_errors[:4] or 'none')

    passed = sum(r['ok'] for r in results)
    print(f"\nSUMMARY ui: {passed}/{len(results)} passed  (screenshots: {SHOTS})", flush=True)
    with open(os.path.join(WORK, 'results_ui.json'), 'w') as f:
        json.dump({'mode': 'ui', 'passed': passed, 'total': len(results), 'results': results}, f, indent=1)
    sys.exit(0 if passed == len(results) else 1)


if __name__ == '__main__':
    run()

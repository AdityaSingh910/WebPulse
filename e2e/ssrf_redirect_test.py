"""SSRF through redirects and page JavaScript (added in Phase 15).

Two local demo-site instances: the first (PUBLIC_PORT) plays a public web page; the second (PRIVATE_PORT) plays an
internal service holding a secret. The start URL on the "public" one is let through deliberately (as a real public
host would be); every later address is checked by the real WebPulse code. Both fetchers must refuse to bring the
secret back:
  S09  plain HTTP: a 302 redirect into the private address is blocked (content_fetchers/requests.py, per-hop check)
  S10  browser:    a 302 redirect into the private address fails the fetch, nothing is saved (playwright.py guard)
  S11  browser:    the page's JavaScript fetch() of the private address is blocked (playwright.py guard)
  S12  browser:    a normal page (no private address involved) is unaffected

Usage: python ssrf_redirect_test.py <work_dir> <cdp_url> [public_port] [private_port]
Writes results_ssrf.json in the same format as test_e2e.py.
"""
import asyncio, json, os, subprocess, sys, time
from unittest import mock
import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
WORK, CDP = sys.argv[1], sys.argv[2]
PUB, PRIV = (int(sys.argv[3]) if len(sys.argv) > 3 else 8187), (int(sys.argv[4]) if len(sys.argv) > 4 else 8188)
os.environ.pop('ALLOW_IANA_RESTRICTED_ADDRESSES', None)
os.environ['PLAYWRIGHT_DRIVER_URL'] = CDP
results = []


def check(cid, name, ok, detail=''):
    results.append({'id': cid, 'name': name, 'ok': bool(ok), 'detail': str(detail)[:300]})
    print(f"[{'PASS' if ok else 'FAIL'}] {cid} {name} {str(detail)[:160]}", flush=True)


fixture = os.path.join(REPO, 'e2e', 'fixture_server.py')
procs = [subprocess.Popen([sys.executable, '-I', fixture, str(PUB), os.path.join(WORK, 'ssrf-public')], stderr=subprocess.DEVNULL),
         subprocess.Popen([sys.executable, '-I', fixture, str(PRIV), os.path.join(WORK, 'ssrf-private')], stderr=subprocess.DEVNULL)]
try:
    time.sleep(1.5)
    requests.post(f'http://127.0.0.1:{PUB}/set', params={'text': 'An ordinary public page', 'http_status': '200'}, timeout=5)
    requests.post(f'http://127.0.0.1:{PRIV}/set', params={'text': 'SECRET-INTERNAL-DATA', 'http_status': '200'}, timeout=5)
    public = f'http://127.0.0.1:{PUB}'
    private = f'http://127.0.0.1:{PRIV}/page.html'
    redirect, jsfetch, normal = f'{public}/redirect?to={private}', f'{public}/fetch-private.html?to={private}', f'{public}/page.html'

    from changedetectionio import validate_url as vu
    from changedetectionio.content_fetchers import requests as req_mod
    from changedetectionio.content_fetchers import playwright as pw_mod
    from changedetectionio.browser_steps import browser_steps as bs_mod
    real_allowed, real_priv, real_async = req_mod.is_fetch_url_allowed, vu.is_url_private_or_parser_confused, bs_mod.validate_fetch_url_async
    is_public = lambda u: u.startswith(public)

    async def start_check(u, *a, **k):
        if is_public(u):
            return
        return await real_async(u, *a, **k)

    with mock.patch.object(req_mod, 'is_fetch_url_allowed', lambda u: (True, '') if is_public(u) else real_allowed(u)), \
            mock.patch.object(vu, 'is_url_private_or_parser_confused', lambda u: False if is_public(u) else real_priv(u)), \
            mock.patch.object(bs_mod, 'validate_fetch_url_async', start_check):

        f = req_mod.fetcher()
        try:
            asyncio.run(f.run(url=redirect, timeout=15, request_headers={}, request_method='GET'))
            check('S09', 'Plain HTTP: redirect into a private address is blocked', 'SECRET' not in (f.content or ''), 'not blocked, content kept')
        except Exception as e:
            check('S09', 'Plain HTTP: redirect into a private address is blocked', 'Redirect blocked' in str(e), str(e)[:120])

        def browser(url):
            f = pw_mod.fetcher()
            try:
                asyncio.run(f.run(url=url, timeout=30, request_headers={}, request_method='GET'))
                return f.content or '', None
            except Exception as e:
                return '', str(e)

        c, err = browser(redirect)
        check('S10', 'Browser: redirect into a private address fails the fetch, nothing saved', 'SECRET' not in c and err, (err or c)[:120])
        c, err = browser(jsfetch)
        check('S11', 'Browser: page JavaScript fetch() of a private address is blocked', 'SECRET' not in c, (err or ' '.join(c.split()))[:120])
        c, err = browser(normal)
        check('S12', 'Browser: an ordinary page is unaffected by the guard', 'An ordinary public page' in c and not err, (err or 'ok')[:120])
finally:
    for p in procs:
        p.terminate()
passed = sum(r['ok'] for r in results)
print(f"\nSUMMARY ssrf: {passed}/{len(results)}", flush=True)
json.dump({'mode': 'ssrf', 'passed': passed, 'total': len(results), 'results': results}, open(os.path.join(WORK, 'results_ssrf.json'), 'w'), indent=1)
sys.exit(0 if passed == len(results) else 1)

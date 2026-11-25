"""Add the controlled "demo site" watches to a WebPulse datastore (demo tooling, not part of the app).

    python demo/add_demo_site.py <datastore_dir>        (run while WebPulse is stopped)

How the controlled demo stays isolated while SSRF protection stays ON:
  * The demo watches use addresses on the reserved ".test" domain (RFC 2606) - e.g.
    http://shop.webpulse-demo.test/product.html - which never resolve on the internet.
  * They are fetched through ONE named proxy, "WebPulse demo site (simulated)" = the local demo site
    (e2e/fixture_server.py on 127.0.0.1:8199, started by run.ps1). That server never forwards anything:
    whatever host is asked for, it only answers with its own canned pages. Choosing this proxy for a real
    website therefore cannot reach anything else.
  * The system-wide default proxy is set to "No proxy", so every other watch connects directly, exactly as
    before. ALLOW_IANA_RESTRICTED_ADDRESSES stays off: private/local addresses remain blocked.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.environ.setdefault('DISABLE_VERSION_CHECK', 'true')

PROXY_KEY = 'webpulse-demo-site'
PROXY = {PROXY_KEY: {'label': 'WebPulse demo site (simulated)', 'url': 'http://127.0.0.1:8199'}}
NOTIFY = 'json://127.0.0.1:8199/notify'
GROUP = 'Demo site (simulated)'
GROUP_SLOW = 'Demo site - concurrency test (simulated)'


def every(minutes=None, hours=None):
    return {'time_between_check_use_default': False,
            'time_between_check': {'weeks': None, 'days': None, 'hours': hours, 'minutes': minutes, 'seconds': None}}


def main():
    ds_path = os.path.abspath(sys.argv[1])
    json.dump(PROXY, open(os.path.join(ds_path, 'proxies.json'), 'w'), indent=1)

    from changedetectionio.store import ChangeDetectionStore
    ds = ChangeDetectionStore(datastore_path=ds_path, include_default_watches=False, version_tag='0.70.4')
    ds.data['settings']['requests']['proxy'] = 'no-proxy'   # everything not explicitly on the demo proxy goes direct

    existing = {w.get('title') for w in ds.data['watching'].values()}
    demo = [
        ('http://news.webpulse-demo.test/page.html', GROUP,
         {'title': '[Demo] Company news page', 'notification_urls': [NOTIFY], **every(hours=24)}),
        ('http://shop.webpulse-demo.test/product.html', GROUP,
         {'title': '[Demo] Wireless earbuds', 'processor': 'restock_diff', 'notification_urls': [NOTIFY],
          'processor_config_restock_diff': {'in_stock_processing': 'all_changes', 'follow_price_changes': True},
          **every(hours=24)}),
        ('http://clock.webpulse-demo.test/slow.html?d=0&n=clock', GROUP,
         {'title': '[Demo] Clock page - checked automatically every minute', 'history_snapshot_max_length': 30,
          **every(minutes=1)}),
    ] + [
        (f'http://slow.webpulse-demo.test/slow.html?d=6&n={i}', GROUP_SLOW,
         {'title': f'[Demo] Slow page {i} (takes 6 seconds)', **every(hours=24)}) for i in range(1, 7)
    ]
    for url, group, extras in demo:
        if extras['title'] in existing:
            print('exists ', extras['title'])
            continue
        extras = {'fetch_backend': 'html_requests', 'proxy': PROXY_KEY, **extras}
        ds.add_watch(url=url, tag=group, extras=extras)
        print('added  ', extras['title'])
    ds.commit()
    print(f'\nDemo site watches ready in {ds_path} (proxy "{PROXY[PROXY_KEY]["label"]}", system default: No proxy)')
    sys.stdout.flush()
    os._exit(0)


if __name__ == '__main__':
    main()

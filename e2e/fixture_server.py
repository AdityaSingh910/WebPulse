"""Local fixture site: the end-to-end test site and the WebPulse controlled-demo site (added for the simplified fork).

GET  /product.html          -> schema.org Product page, name/price/stock from state.json
GET  /page.html             -> plain text page, body text from state.json
GET  /jobs.html             -> a careers page: the job list (#job-list) from state.json, plus a banner and footer
                               that change on EVERY request (used to show that a CSS filter ignores them)
GET  /js.html, /js-product.html -> content / price data that only exists after JavaScript runs
GET  /slow.html?d=SECONDS&n=ID -> responds after a delay of at most 10 s (used to prove concurrent workers)
GET  /state.json            -> the current state (read by the WebPulse "Controlled demo" page)
POST /set?price=..&stock=..&text=..&name=..&jobs=a|b|c -> change state (known keys only, bounded values)
POST /reset                 -> back to the default state
POST /notify                -> notification receiver, appends request bodies to notifications.log

Security: it binds to 127.0.0.1 only, and it is NOT a forwarding proxy. When WebPulse uses it as the
"WebPulse demo site" proxy, it answers every request - whatever host is asked for - with its own canned
pages above or a 404. CONNECT (HTTPS tunnelling) is not implemented and gets a 501, so nothing is ever
relayed to another address.

Usage: python fixture_server.py <port> <work_dir>
"""
import json
import os
import random
import sys
import time
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
WORK = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
os.makedirs(WORK, exist_ok=True)
STATE = os.path.join(WORK, 'state.json')
LOG = os.path.join(WORK, 'notifications.log')
DEFAULT_JOBS = ['Backend Engineer (Python) - Bengaluru', 'Data Engineer - Hyderabad', 'Software Engineering Intern - Remote']
DEFAULT = {'price': '499.00', 'stock': 'InStock', 'text': 'Version one of the page.', 'name': 'Test Headphones',
           'jobs': '|'.join(DEFAULT_JOBS)}
STOCK_VALUES = {'InStock', 'OutOfStock', 'PreOrder', 'BackOrder', 'SoldOut', 'LimitedAvailability'}
MAX_VALUE = 2000
MAX_DELAY = 10.0


def load():
    s = dict(DEFAULT)
    try:
        with open(STATE) as f:
            s.update(json.load(f))
    except (OSError, ValueError):
        pass
    return s


def save(s):
    with open(STATE, 'w') as f:
        json.dump(s, f)


def valid(key, value):
    if key not in DEFAULT or len(value) > MAX_VALUE:
        return False
    if key == 'stock':
        return value in STOCK_VALUES
    if key == 'price':
        try:
            return 0 <= float(value) < 10_000_000
        except ValueError:
            return False
    return True


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype='text/html', code=200):
        b = body.encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def _404(self):
        self._send('<html><body><h1>404 - not a page of the WebPulse demo site</h1></body></html>', code=404)

    def do_GET(self):
        s = load()
        u = urlparse(self.path)
        q = parse_qs(u.query)
        name = escape(s['name'])
        if u.path == '/product.html':
            ld = {"@context": "https://schema.org", "@type": "Product", "name": s['name'],
                  "offers": {"@type": "Offer", "price": s['price'], "priceCurrency": "INR",
                             "availability": "https://schema.org/" + s['stock']}}
            self._send(f"<html><head><title>{name}</title><script type='application/ld+json'>"
                       f"{json.dumps(ld)}</script></head><body><h1>{name}</h1>"
                       f"<p class='price'>Rs {escape(s['price'])}</p></body></html>")
        elif u.path == '/page.html':
            self._send(f"<html><head><title>News page</title></head><body><h1>News</h1>"
                       f"<p>{escape(s['text'])}</p></body></html>")
        elif u.path == '/jobs.html':
            jobs = [j for j in s['jobs'].split('|') if j.strip()]
            items = ''.join(f"<li class='job'>{escape(j)}</li>" for j in jobs)
            self._send("<html><head><title>DemoCorp Careers</title></head><body>"
                       "<h1>Careers at DemoCorp (WebPulse controlled demo)</h1>"
                       f"<p class='banner'>Visitors today: {random.randint(100, 999)} - join our team!</p>"
                       f"<h2>Open positions</h2><ul id='job-list'>{items}</ul>"
                       f"<footer>Page generated at {time.strftime('%H:%M:%S')}</footer></body></html>")
        elif u.path == '/js.html':
            # Content only exists after JavaScript runs - a plain HTTP fetch sees just the placeholder
            self._send("<html><head><title>JS page</title></head><body><div id='app'>Loading...</div>"
                       "<script>document.getElementById('app').innerHTML = '<p>' + ['Rendered','by','JavaScript'].join(' ')"
                       f" + ' - ' + {json.dumps(s['text'])} + '</p>';</script></body></html>")
        elif u.path == '/js-product.html':
            # schema.org price data injected by JavaScript (only a real browser sees it)
            ld = json.dumps({"@context": "https://schema.org", "@type": "Product", "name": "JS Headphones",
                             "offers": {"@type": "Offer", "price": s['price'], "priceCurrency": "INR",
                                        "availability": "https://schema.org/" + s['stock']}})
            self._send("<html><head><title>JS Headphones</title></head><body><h1>JS Headphones</h1><script>"
                       "var e=document.createElement('script');e.type='application/ld+json';"
                       f"e.text={json.dumps(ld)};document.head.appendChild(e);</script></body></html>")
        elif u.path == '/slow.html':
            try:
                delay = min(max(float(q.get('d', ['2'])[0]), 0.0), MAX_DELAY)
            except ValueError:
                delay = 2.0
            time.sleep(delay)
            self._send(f"<html><body><p>Slow page {escape(q.get('n', ['0'])[0][:20])} at {time.time()}</p></body></html>")
        elif u.path == '/state.json':
            self._send(json.dumps(s), 'application/json')
        else:
            self._404()

    def do_POST(self):
        u = urlparse(self.path)
        n = min(int(self.headers.get('Content-Length') or 0), 1_000_000)
        body = self.rfile.read(n).decode(errors='replace')
        if u.path == '/set':
            s = load()
            for k, v in parse_qs(u.query).items():
                if not valid(k, v[0]):
                    self._send(json.dumps({'error': f'not allowed: {k}'[:80]}), 'application/json', 400)
                    return
                s[k] = v[0]
            save(s)
            self._send(json.dumps(s), 'application/json')
        elif u.path == '/reset':
            save(dict(DEFAULT))
            self._send(json.dumps(DEFAULT), 'application/json')
        elif u.path == '/notify':
            with open(LOG, 'a', encoding='utf-8') as f:
                f.write(body.replace('\n', ' ') + '\n')
            self._send('{"ok":true}', 'application/json')
        else:
            self._404()

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()

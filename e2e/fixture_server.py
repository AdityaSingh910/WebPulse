"""Local fixture site: the end-to-end test site and the WebPulse controlled-demo site (added for the simplified fork).

GET  /product.html          -> schema.org Product page, name/price/stock from state.json
GET  /page.html             -> plain text page, body text from state.json
GET  /jobs.html             -> a careers page: the job list (#job-list) from state.json, plus a banner and footer
                               that change on EVERY request (used to show that a CSS filter ignores them).
                               Each job "Title - Location" is a card with its own link /jobs/<slug of the title>,
                               so changing the location keeps the same job (a "modified" opening)
GET  /jobs/<slug>           -> the detail page of one job (the "Apply" link)
GET  /redirect?to=, /fetch-private.html?to= -> SSRF tests only: a 302 / a JavaScript fetch() to another 127.0.0.1 address
GET  /js.html, /js-product.html -> content / price data that only exists after JavaScript runs
GET  /slow.html?d=SECONDS&n=ID -> responds after a delay of at most 10 s (used to prove concurrent workers)
GET  /state.json            -> the current state (read by the WebPulse "Controlled demo" page)
POST /set?price=..&stock=..&text=..&name=..&jobs=a|b|c&jobs_page=normal|blocked -> change state (known keys only,
                               bounded values); product_page=broken|malformed|noprice|nostock serves a product page without data / with broken JSON-LD / without
                               a price / without stock; http_status=403|404|429|500|503 makes every page answer with that status; jobs_page=blocked serves a bot-check page instead of the careers page,
                               an empty job list shows an explicit "No open positions" message
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
import re
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
           'jobs': '|'.join(DEFAULT_JOBS), 'jobs_page': 'normal', 'product_page': 'normal', 'http_status': '200'}
JOBS_PAGE_VALUES = {'normal', 'blocked'}
PRODUCT_PAGE_VALUES = {'normal', 'broken', 'malformed', 'noprice', 'nostock'}
HTTP_STATUS_VALUES = {'200', '403', '404', '429', '500', '503'}
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


def parse_jobs(value):
    """'Title - Location|...' -> [(slug, title, location)]; the slug comes from the title only"""
    out = []
    for j in (value or '').split('|'):
        if not j.strip():
            continue
        title, _, loc = j.rpartition(' - ') if ' - ' in j else (j, '', '')
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:80] or 'job'
        out.append((slug, title.strip(), loc.strip()))
    return out


def save(s):
    with open(STATE, 'w') as f:
        json.dump(s, f)


def valid(key, value):
    if key not in DEFAULT or len(value) > MAX_VALUE:
        return False
    if key == 'jobs_page':
        return value in JOBS_PAGE_VALUES
    if key == 'product_page':
        return value in PRODUCT_PAGE_VALUES
    if key == 'http_status':
        return value in HTTP_STATUS_VALUES
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
        # Error-response test mode: every content page answers with this status (429 also sends Retry-After)
        if s.get('http_status', '200') != '200' and u.path not in ('/state.json',):
            code = int(s['http_status'])
            self.send_response(code)
            if code == 429:
                self.send_header('Retry-After', '120')
            body = f"<html><body><h1>HTTP {code}</h1></body></html>".encode()
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        q = parse_qs(u.query)
        name = escape(s['name'])
        if u.path == '/product.html' and s.get('product_page') in ('malformed', 'noprice', 'nostock'):
            mode = s['product_page']
            offer = {"@type": "Offer", "priceCurrency": "INR"}
            if mode != 'noprice':
                offer['price'] = s['price']
            if mode != 'nostock':
                offer['availability'] = "https://schema.org/" + s['stock']
            ld = json.dumps({"@context": "https://schema.org", "@type": "Product", "name": s['name'], "offers": offer})
            if mode == 'malformed':
                ld = ld.replace('"offers":', '"offers" ').replace('}', '', 1)   # broken JSON, as some real shops publish
            self._send(f"<html><head><title>{name}</title><script type='application/ld+json'>{ld}</script></head>"
                       f"<body><h1>{name}</h1><div><p>Unclosed <b>markup<i> and a stray </span> tag</body></html>")
        elif u.path == '/product.html' and s.get('product_page') == 'broken':
            # A shop page that loads (HTTP 200) but carries no price/stock data - e.g. a redesign or a holding page
            self._send(f"<html><head><title>{name}</title></head><body><h1>{name}</h1><p>Temporarily unavailable.</p></body></html>")
        elif u.path == '/product.html':
            ld = {"@context": "https://schema.org", "@type": "Product", "name": s['name'],
                  "offers": {"@type": "Offer", "price": s['price'], "priceCurrency": "INR",
                             "availability": "https://schema.org/" + s['stock']}}
            self._send(f"<html><head><title>{name}</title><script type='application/ld+json'>"
                       f"{json.dumps(ld)}</script></head><body><h1>{name}</h1>"
                       f"<p class='price'>Rs {escape(s['price'])}</p></body></html>")
        elif u.path == '/page.html':
            self._send(f"<html><head><title>News page</title></head><body><h1>News</h1>"
                       f"<p>{escape(s['text'])}</p></body></html>")
        elif u.path == '/jobs.html' and s.get('jobs_page') == 'blocked':
            # What a bot check / temporary block looks like: HTTP 200, but no job list at all
            self._send("<html><head><title>Just a moment...</title></head><body><h1>Checking your browser</h1>"
                       "<p>Please verify you are a human to continue.</p></body></html>")
        elif u.path == '/jobs.html':
            items = ''.join(f"<li class='job'><a class='job-title' href='/jobs/{slug}'>{escape(title)}</a>"
                            f"<span class='job-location'>{escape(loc)}</span><span class='job-type'>Full time</span></li>"
                            for slug, title, loc in parse_jobs(s['jobs']))
            self._send("<html><head><title>DemoCorp Careers</title></head><body>"
                       "<h1>Careers at DemoCorp (WebPulse controlled demo)</h1>"
                       f"<p class='banner'>Visitors today: {random.randint(100, 999)} - join our team!</p>"
                       f"<h2>Open positions</h2><ul id='job-list'>{items}</ul>"
                       + ("" if items else "<p class='no-openings'>No open positions right now - please check back soon.</p>")
                       + f"<footer>Page generated at {time.strftime('%H:%M:%S')}</footer></body></html>")
        elif u.path == '/redirect':
            # SSRF test only: an "open redirect" that sends the fetcher to another 127.0.0.1 address
            to = q.get('to', [''])[0]
            if not re.match(r'^http://127\.0\.0\.1:\d{2,5}/[\w./?=&-]*$', to):
                return self._404()
            self.send_response(302)
            self.send_header('Location', to)
            self.send_header('Content-Length', '0')
            self.end_headers()
        elif u.path == '/fetch-private.html':
            # SSRF test only: a page whose JavaScript reads another 127.0.0.1 address and writes it into the page
            to = q.get('to', [''])[0]
            if not re.match(r'^http://127\.0\.0\.1:\d{2,5}/[\w./?=&-]*$', to):
                return self._404()
            self._send("<html><body><div id='out'>waiting</div><script>fetch(" + json.dumps(to) + ").then(r => r.text())"
                       ".then(t => document.getElementById('out').textContent = 'LEAKED: ' + t)"
                       ".catch(e => document.getElementById('out').textContent = 'blocked: ' + e);</script></body></html>")
        elif u.path.startswith('/jobs/'):
            job = next((j for j in parse_jobs(s['jobs']) if j[0] == u.path[len('/jobs/'):]), None)
            if not job:
                return self._404()
            self._send(f"<html><head><title>{escape(job[1])}</title></head><body><h1>{escape(job[1])}</h1>"
                       f"<p>{escape(job[2])} - DemoCorp (WebPulse controlled demo)</p></body></html>")
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

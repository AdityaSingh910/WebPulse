"""Local test fixture site for the end-to-end regression tests (added for the simplified fork).

GET  /product.html          -> schema.org Product page, price/stock from state.json
GET  /page.html             -> plain text page, body text from state.json
GET  /slow.html?d=SECONDS&n=ID -> responds after a delay (used to prove concurrent workers)
POST /set?price=..&stock=..&text=..  -> change state
POST /notify                -> notification receiver, appends request bodies to notifications.log

Usage: python fixture_server.py <port> <work_dir>
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
WORK = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
os.makedirs(WORK, exist_ok=True)
STATE = os.path.join(WORK, 'state.json')
LOG = os.path.join(WORK, 'notifications.log')
DEFAULT = {'price': '499.00', 'stock': 'InStock', 'text': 'Version one of the page.'}


def load():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return dict(DEFAULT)


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, ctype='text/html'):
        b = body.encode()
        self.send_response(200)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        s = load()
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == '/product.html':
            ld = {"@context": "https://schema.org", "@type": "Product", "name": "Test Headphones",
                  "offers": {"@type": "Offer", "price": s['price'], "priceCurrency": "INR",
                             "availability": "https://schema.org/" + s['stock']}}
            self._send(f"<html><head><title>Test Headphones</title><script type='application/ld+json'>"
                       f"{json.dumps(ld)}</script></head><body><h1>Test Headphones</h1>"
                       f"<p class='price'>Rs {s['price']}</p></body></html>")
        elif u.path == '/page.html':
            self._send(f"<html><head><title>News page</title></head><body><h1>News</h1>"
                       f"<p>{s['text']}</p></body></html>")
        elif u.path == '/js.html':
            # Content only exists after JavaScript runs - a plain HTTP fetch sees just the placeholder
            self._send("<html><head><title>JS page</title></head><body><div id='app'>Loading...</div>"
                       "<script>document.getElementById('app').innerHTML = '<p>' + ['Rendered','by','JavaScript'].join(' ')"
                       f" + ' - {s['text']}</p>';</script></body></html>")
        elif u.path == '/js-product.html':
            # schema.org price data injected by JavaScript (only a real browser sees it)
            ld = json.dumps({"@context": "https://schema.org", "@type": "Product", "name": "JS Headphones",
                             "offers": {"@type": "Offer", "price": s['price'], "priceCurrency": "INR",
                                        "availability": "https://schema.org/" + s['stock']}})
            self._send("<html><head><title>JS Headphones</title></head><body><h1>JS Headphones</h1><script>"
                       "var e=document.createElement('script');e.type='application/ld+json';"
                       f"e.text={json.dumps(ld)};document.head.appendChild(e);</script></body></html>")
        elif u.path == '/slow.html':
            time.sleep(float(q.get('d', ['2'])[0]))
            self._send(f"<html><body><p>Slow page {q.get('n', ['0'])[0]} at {time.time()}</p></body></html>")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n).decode(errors='replace')
        if u.path == '/set':
            s = load()
            for k, v in parse_qs(u.query).items():
                s[k] = v[0]
            with open(STATE, 'w') as f:
                json.dump(s, f)
            self._send(json.dumps(s), 'application/json')
        elif u.path == '/notify':
            with open(LOG, 'a', encoding='utf-8') as f:
                f.write(body.replace('\n', ' ') + '\n')
            self._send('{"ok":true}', 'application/json')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()

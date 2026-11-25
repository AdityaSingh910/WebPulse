"""WebPulse notification history (added 2026, based on changedetection.io, Apache-2.0, see CHANGES.md).

Upstream keeps the result of each notification only in an in-memory list (the "notification debug log")
that is emptied on every restart. This module keeps the same record - what was sent, where to, whether
it worked - in a small JSON-lines file in the datastore, so the Notifications page can show the history
of real deliveries after a restart.

Secrets never reach the file: destinations are stored masked (mask_notification_url), and error text is
reduced to its WARNING/ERROR lines with every password, token and bot key from the notification URLs
replaced by ****.
"""
import json
import os
import re
import threading
import time
from urllib.parse import urlsplit, unquote

FILENAME = 'notification-history.jsonl'
KEEP = 500
_lock = threading.Lock()


def channel_of(url):
    """A plain name for where a notification URL sends to"""
    scheme = (url or '').split('://', 1)[0].lower()
    if scheme in ('mailto', 'mailtos'):
        return 'Email'
    if scheme in ('tgram',):
        return 'Telegram'
    if scheme in ('json', 'jsons', 'xml', 'xmls', 'form', 'forms', 'get', 'gets', 'post', 'posts', 'put', 'puts'):
        return 'Webhook'
    return 'Other'


def _secret_parts(urls):
    """Every piece of the notification URLs that could be a credential"""
    parts = set()
    for url in urls or []:
        url = url.strip()
        if channel_of(url) == 'Telegram':
            # tgram://<bot token>/<chat id> - the "host" is the token, which urlsplit cannot read as a host
            parts.add(url.split('://', 1)[-1].split('/', 1)[0])
            continue
        try:
            s = urlsplit(url)
            user, password = s.username, s.password
        except ValueError:
            continue
        for p in (user, password):
            if p:
                parts.add(unquote(p))
                parts.add(p)
        for seg in s.path.split('/'):
            if len(seg) >= 8:
                parts.add(unquote(seg))
        for kv in s.query.split('&'):
            k, _, v = kv.partition('=')
            if k.lower() in ('pass', 'password', 'token', 'key', 'apikey', 'secret') and v:
                parts.add(unquote(v))
    return sorted((p for p in parts if len(p) >= 6), key=len, reverse=True)


def clean_error(text, urls):
    """The useful lines of an Apprise error, with any credential masked"""
    if not text:
        return ''
    lines = [l for l in str(text).splitlines() if l.strip()]
    important = [l for l in lines if ' - WARNING - ' in l or ' - ERROR - ' in l or ('DEBUG' not in l and 'INFO' not in l)]
    out = '\n'.join(important or lines[-3:])
    for secret in _secret_parts(urls):
        out = out.replace(secret, '****')
    out = re.sub(r'bot\d{5,}:[A-Za-z0-9_-]{20,}', 'bot****', out)   # a Telegram bot token wherever it appears
    return out[:800]


def record(datastore_path, urls, ok, title='', error=None, watch=None, kind='change'):
    """Append one notification attempt. Never raises - history must not break sending."""
    try:
        from changedetectionio.notification.masking import mask_notification_url
        urls = [u.strip() for u in (urls or []) if u and u.strip() and not u.strip().startswith('#')]
        entry = {
            'ts': int(time.time()),
            'kind': kind,
            'ok': bool(ok),
            'title': clean_error(title, urls)[:300] if title else '',
            'destinations': [{'channel': channel_of(u), 'to': mask_notification_url(u)} for u in urls],
            'error': clean_error(error, urls) if error else '',
            'watch_uuid': watch.get('uuid') if watch else None,
            'watch_title': (watch.label if hasattr(watch, 'label') else watch.get('title')) if watch else None,
            'watch_url': watch.get('url') if watch else None,
        }
        path = os.path.join(datastore_path, FILENAME)
        with _lock:
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')
            # Trim now and then, keeping the newest KEEP entries
            if os.path.getsize(path) > 600 * KEEP:
                with open(path, encoding='utf-8') as f:
                    keep = f.readlines()[-KEEP:]
                with open(path, 'w', encoding='utf-8') as f:
                    f.writelines(keep)
    except Exception as e:  # pragma: no cover - logging only
        from loguru import logger
        logger.warning(f"Could not write notification history: {e}")


def read(datastore_path, limit=200):
    """Newest first"""
    path = os.path.join(datastore_path, FILENAME)
    if not os.path.isfile(path):
        return []
    with _lock:
        with open(path, encoding='utf-8') as f:
            lines = f.readlines()[-limit:]
    out = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out

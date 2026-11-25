"""WebPulse simple notification setup: Email and Telegram (added 2026, based on changedetection.io, Apache-2.0).

WebPulse still sends every notification through the existing Apprise pipeline, which reads a list of
notification URLs (settings.application.notification_urls). This module only turns a few plain form fields
into those URLs, and reads them back for display:

    Email     mailtos://<user>:<app password>@<domain>[:port]?to=<to>[&smtp=<host>&from=<from>&mode=ssl]
    Telegram  tgram://<bot token>/<chat id>

Every other URL in the list (for example a json:// webhook used by the automated tests) is left untouched.
Secrets (password, bot token) are never sent back to the browser.
"""
import re
from urllib.parse import quote, unquote, urlsplit, parse_qs

# Mail providers Apprise configures by itself (SMTP host, port and TLS) from the address alone
KNOWN_MAIL_DOMAINS = ('gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com', 'yahoo.com',
                      'yahoo.co.in', 'zoho.com', 'zoho.in', 'yandex.com', 'fastmail.com', 'icloud.com', 'me.com')
EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$')
TELEGRAM_TOKEN_RE = re.compile(r'^\d{5,15}:[A-Za-z0-9_-]{30,64}$')
TELEGRAM_CHAT_RE = re.compile(r'^(-?\d{3,20}|@[A-Za-z0-9_]{5,32})$')
SMTP_HOST_RE = re.compile(r'^[A-Za-z0-9.\-]{3,253}$')


def is_email_url(url):
    return url.strip().lower().startswith(('mailto://', 'mailtos://'))


def is_telegram_url(url):
    return url.strip().lower().startswith('tgram://')


def split_urls(urls):
    """(email url or None, telegram url or None, every other url)"""
    email = telegram = None
    other = []
    for u in urls or []:
        if is_email_url(u) and email is None:
            email = u.strip()
        elif is_telegram_url(u) and telegram is None:
            telegram = u.strip()
        else:
            other.append(u)
    return email, telegram, other


def _email_list(text):
    return [e.strip() for e in re.split(r'[,;\s]+', text or '') if e.strip()]


def build_email_url(sender, password, recipients, smtp_host='', smtp_port=''):
    """Returns (url, error). `recipients` is a comma separated list; empty means the sender."""
    sender = (sender or '').strip()
    if not EMAIL_RE.match(sender):
        return None, 'Enter the email address WebPulse should send from (for example yourname@gmail.com).'
    if not password:
        return None, 'Enter the app password for that email account.'
    to = _email_list(recipients) or [sender]
    bad = [e for e in to if not EMAIL_RE.match(e)]
    if bad:
        return None, f'Not a valid email address: {bad[0]}'
    user, domain = sender.rsplit('@', 1)
    query = {'to': ','.join(to)}
    netloc_port = ''
    smtp_host = (smtp_host or '').strip()
    if smtp_host:
        if not SMTP_HOST_RE.match(smtp_host):
            return None, 'The mail server name is not valid.'
        port = str(smtp_port or '').strip()
        if port and (not port.isdigit() or not 0 < int(port) < 65536):
            return None, 'The mail server port must be a number.'
        query['smtp'] = smtp_host
        query['from'] = sender
        if port:
            netloc_port = f':{port}'
            if port == '465':
                query['mode'] = 'ssl'
    elif domain.lower() not in KNOWN_MAIL_DOMAINS:
        return None, f'WebPulse does not know the mail server for "{domain}". Open "Use a different mail server" and enter it.'
    qs = '&'.join(f'{k}={quote(v, safe="@,.")}' for k, v in query.items())
    return f"mailtos://{quote(user, safe='')}:{quote(password, safe='')}@{domain}{netloc_port}/?{qs}", None


def parse_email_url(url):
    """What can be shown of a stored email URL - never the password"""
    if not url:
        return None
    try:
        s = urlsplit(url)
        q = parse_qs(s.query)
        user = unquote(s.username or '')
        domain = s.hostname or ''
        sender = q.get('from', [f'{user}@{domain}'])[0]
        return {
            'sender': sender,
            'recipients': ', '.join(_email_list(q.get('to', [''])[0])) or sender,
            'smtp_host': q.get('smtp', [''])[0],
            'smtp_port': str(s.port or ''),
            'has_password': bool(s.password),
        }
    except ValueError:
        return {'sender': '', 'recipients': '', 'smtp_host': '', 'smtp_port': '', 'has_password': False}


def email_password_of(url):
    try:
        return unquote(urlsplit(url).password or '') if url else ''
    except ValueError:
        return ''


def build_telegram_url(token, chat_id):
    token = (token or '').strip()
    chat_id = (chat_id or '').strip()
    if not TELEGRAM_TOKEN_RE.match(token):
        return None, 'That does not look like a bot token. It looks like 123456789:AAH... and comes from @BotFather.'
    if not TELEGRAM_CHAT_RE.match(chat_id):
        return None, 'Enter your chat ID (a number). Send any message to your bot, then press "Find my chat ID".'
    return f'tgram://{token}/{chat_id}', None


def parse_telegram_url(url):
    if not url:
        return None
    rest = url.split('://', 1)[-1]
    token, _, chat = rest.partition('/')
    chat = chat.split('?', 1)[0].strip('/')
    return {'chat_id': chat, 'token_hint': (token.split(':', 1)[0] + ':••••') if token else '', 'has_token': bool(token)}


def telegram_token_of(url):
    return url.split('://', 1)[-1].split('/', 1)[0] if url else ''


def find_telegram_chats(token):
    """Ask Telegram which chats recently messaged the bot. Returns (list of (chat id, name), error)."""
    import requests
    if not TELEGRAM_TOKEN_RE.match(token or ''):
        return [], 'Enter a valid bot token first.'
    try:
        # The host is fixed and the token is validated above, so this cannot be pointed anywhere else
        r = requests.get(f'https://api.telegram.org/bot{token}/getUpdates', timeout=15)
        data = r.json()
    except Exception as e:
        return [], f'Could not reach Telegram: {type(e).__name__}'
    if not data.get('ok'):
        return [], 'Telegram did not accept this bot token: ' + str(data.get('description', 'unknown error'))[:120]
    chats = {}
    for upd in data.get('result', []):
        msg = upd.get('message') or upd.get('channel_post') or upd.get('my_chat_member') or {}
        chat = msg.get('chat') or {}
        if chat.get('id') is not None:
            name = chat.get('title') or ' '.join(filter(None, [chat.get('first_name'), chat.get('last_name')])) or chat.get('username') or ''
            chats[str(chat['id'])] = name
    if not chats:
        return [], 'No messages found. Open Telegram, send any message (for example "hi") to your bot, then try again.'
    return list(chats.items()), None

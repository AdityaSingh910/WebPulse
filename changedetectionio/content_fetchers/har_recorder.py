# Modified 2026 for the simplified (academic) fork of changedetection.io - optional features removed, see CHANGES.md
"""Record the network traffic of one browser fetch as a HAR 1.2 file.

Diagnostic aid for "why does this site block/behave differently for the browser" (#4539).

The playwright fetcher uses playwright's own HAR recording and only needs save_har_file() from here.
`requests` has none either, har_from_requests_responses() builds it from the responses of each hop.

Only loaded when recording is switched on for a watch, see HAR_UUID_RECORD in the browser fetchers.

    HAR_UUID_RECORD     comma separated watch UUIDs to record (case insensitive)
    HAR_FORMAT          'zip' (default, har-record.zip holding har-record.har) or 'har' (plain har-record.har)
    HAR_INCLUDE_BINARY  also keep the bodies of images, fonts, media etc, off by default - every request
                        is always listed with its headers and sizes, this is only about the payload
"""
import asyncio
import json
import os
import zipfile
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlsplit

from loguru import logger

from changedetectionio.strtobool import strtobool

HAR_ZIP_FILENAME = 'har-record.zip'
HAR_FILENAME = 'har-record.har'
# Bodies worth reading when working out why a page behaves the way it does
TEXT_MIME_MARKERS = ('json', 'xml', 'javascript', 'ecmascript', 'html', 'urlencoded')

# Response bodies larger than this are listed with their size but not embedded
MAX_EMBEDDED_BODY_BYTES = 2 * 1024 * 1024
# How long to let in-flight body reads finish once the fetch is over
BODY_DRAIN_TIMEOUT_SECONDS = 5


def har_recording_wanted(watch_uuid, env_value=None):
    """True when watch_uuid is in the comma separated HAR_UUID_RECORD list (case insensitive)."""
    if env_value is None:
        env_value = os.getenv('HAR_UUID_RECORD', '')
    if not watch_uuid or not env_value:
        return False
    wanted = {u.strip().strip('"\'').lower() for u in env_value.split(',')}
    return str(watch_uuid).lower() in wanted


def include_binary_bodies():
    return bool(strtobool(os.getenv('HAR_INCLUDE_BINARY', 'False')))


def is_text_mime_type(mime_type):
    mime_type = (mime_type or '').lower()
    return mime_type.startswith('text/') or any(m in mime_type for m in TEXT_MIME_MARKERS)


def strip_binary_bodies(har):
    """Drop the payload of images, fonts, media etc, their entries stay with headers and sizes."""
    for entry in har.get('log', {}).get('entries', []):
        content = entry.get('response', {}).get('content') or {}
        if 'text' in content and not is_text_mime_type(content.get('mimeType')):
            del content['text']
            content.pop('encoding', None)
            content['comment'] = 'Binary body not recorded, set HAR_INCLUDE_BINARY=true to keep it'
    return har


def save_har(directory, har):
    """Write the HAR into directory as HAR_FORMAT asks, replacing the one from the previous check. Blocking."""
    if not include_binary_bodies():
        strip_binary_bodies(har)

    har_format = os.getenv('HAR_FORMAT', 'zip').strip().lower() or 'zip'
    if har_format not in ('zip', 'har'):
        logger.warning(f"HAR_FORMAT '{har_format}' is not 'zip' or 'har', using 'zip'")
        har_format = 'zip'

    filename, other = (HAR_ZIP_FILENAME, HAR_FILENAME) if har_format == 'zip' else (HAR_FILENAME, HAR_ZIP_FILENAME)
    destination = os.path.join(directory, filename)
    tmp = destination + '.tmp'
    if har_format == 'zip':
        with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(HAR_FILENAME, json.dumps(har))
    else:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(har, f)
    os.replace(tmp, destination)

    # Only ever one recording per watch, don't leave a stale one behind when HAR_FORMAT was changed
    stale = os.path.join(directory, other)
    if os.path.exists(stale):
        os.unlink(stale)
    return destination


def load_har(directory):
    """(HAR dict, unix time it was recorded) of the recording in directory, (None, None) without one. Blocking."""
    zipped, plain = os.path.join(directory, HAR_ZIP_FILENAME), os.path.join(directory, HAR_FILENAME)
    if os.path.isfile(zipped):
        with zipfile.ZipFile(zipped) as z:
            return json.loads(z.read(HAR_FILENAME)), os.path.getmtime(zipped)
    if os.path.isfile(plain):
        with open(plain, 'r', encoding='utf-8') as f:
            return json.load(f), os.path.getmtime(plain)
    return None, None


def save_har_file(directory, har_file):
    """Same as save_har() for a HAR that some other recorder already wrote to har_file. Blocking."""
    with open(har_file, 'r', encoding='utf-8') as f:
        return save_har(directory, json.load(f))


def _name_value_list(headers):
    # CDP gives a dict and folds repeated headers (Set-Cookie) into one value joined by newlines
    out = []
    for name, value in (headers or {}).items():
        for v in str(value).split('\n'):
            out.append({'name': name, 'value': v})
    return out


def _header(headers, wanted):
    for name, value in (headers or {}).items():
        if name.lower() == wanted:
            return str(value)
    return ''


def _request_cookies(headers):
    out = []
    for part in _header(headers, 'cookie').split(';'):
        name, sep, value = part.strip().partition('=')
        if sep:
            out.append({'name': name, 'value': value})
    return out


def _response_cookies(headers):
    out = []
    for line in _header(headers, 'set-cookie').split('\n'):
        name, sep, value = line.split(';', 1)[0].strip().partition('=')
        if sep:
            out.append({'name': name, 'value': value})
    return out


def _iso(wall_time):
    return datetime.fromtimestamp(wall_time or 0, tz=timezone.utc).isoformat(timespec='milliseconds')


def _http_version(protocol):
    return {'h2': 'HTTP/2.0', 'h3': 'HTTP/3.0'}.get(protocol or '', (protocol or '').upper())


def har_from_requests_responses(recorded, title=''):
    """Build a HAR from `requests` responses, one entry per hop.

    recorded is a list of (wall clock time the request started, requests.Response), which the
    requests fetcher collects with a session 'response' hook so every redirect hop is in there.
    """
    import base64
    entries = []
    keep_binary = include_binary_bodies()
    for started, r in recorded:
        request = r.request
        request_headers = dict(request.headers or {})

        # r.headers folds repeated headers (Set-Cookie) together with commas, the raw ones are still separate
        response_headers = {}
        try:
            pairs = list(r.raw.headers.items())
        except Exception:
            pairs = list(r.headers.items())
        for name, value in pairs:
            response_headers[name] = f"{response_headers[name]}\n{value}" if name in response_headers else value

        mime_type = _header(response_headers, 'content-type')
        body = r.content or b''
        content = {'size': len(body), 'mimeType': mime_type}
        if body and len(body) <= MAX_EMBEDDED_BODY_BYTES:
            if is_text_mime_type(mime_type):
                try:
                    content['text'] = body.decode(r.encoding or 'utf-8')
                except (UnicodeDecodeError, LookupError):
                    content['text'] = base64.b64encode(body).decode('ascii')
                    content['encoding'] = 'base64'
            elif keep_binary:
                content['text'] = base64.b64encode(body).decode('ascii')
                content['encoding'] = 'base64'

        request_body = request.body or ''
        if isinstance(request_body, bytes):
            request_body = request_body.decode('utf-8', errors='replace')
        http_version = {10: 'HTTP/1.0', 11: 'HTTP/1.1', 20: 'HTTP/2.0'}.get(getattr(r.raw, 'version', None), '')
        elapsed = round(r.elapsed.total_seconds() * 1000, 3)

        har_request = {
            'method': request.method or '',
            'url': request.url or '',
            'httpVersion': http_version,
            'cookies': _request_cookies(request_headers),
            'headers': _name_value_list(request_headers),
            'queryString': [{'name': n, 'value': v} for n, v in
                            parse_qsl(urlsplit(request.url or '').query, keep_blank_values=True)],
            'headersSize': -1,
            'bodySize': len(request_body),
        }
        if request_body:
            har_request['postData'] = {'mimeType': _header(request_headers, 'content-type'), 'text': request_body}

        entries.append({
            'pageref': 'page_1',
            'startedDateTime': _iso(started),
            'time': elapsed,
            'request': har_request,
            'response': {
                'status': r.status_code,
                'statusText': r.reason or '',
                'httpVersion': http_version,
                'cookies': _response_cookies(response_headers),
                'headers': _name_value_list(response_headers),
                'content': content,
                'redirectURL': _header(response_headers, 'location'),
                'headersSize': -1,
                'bodySize': len(body),
            },
            'cache': {},
            # requests only measures request-sent to headers-parsed
            'timings': {'blocked': -1, 'dns': -1, 'connect': -1, 'ssl': -1, 'send': 0, 'wait': elapsed, 'receive': 0},
        })
    return _har_log(entries, title)


def _har_log(entries, title):
    started = entries[0]['startedDateTime'] if entries else _iso(None)
    return {
        'log': {
            'version': '1.2',
            'creator': {'name': 'changedetection.io', 'version': '1'},
            'pages': [{'startedDateTime': started, 'id': 'page_1', 'title': title,
                       'pageTimings': {'onContentLoad': -1, 'onLoad': -1}}],
            'entries': entries,
        }
    }

"""HAR recording of a fetch (HAR_UUID_RECORD). (The CDP-event HarRecorder was only used by the removed Puppeteer fetcher.)"""

import asyncio
import json
import zipfile

from changedetectionio.content_fetchers.har_recorder import har_from_requests_responses, har_recording_wanted, save_har


def test_uuid_list_is_comma_separated_and_case_insensitive():
    uuid = 'aBcDef12-0000-4000-8000-000000000001'
    assert har_recording_wanted(uuid, env_value=f'something-else, {uuid.upper()} ')
    assert har_recording_wanted(uuid, env_value=f'"{uuid.lower()}"')
    assert not har_recording_wanted(uuid, env_value='something-else')
    assert not har_recording_wanted(uuid, env_value='')
    assert not har_recording_wanted(None, env_value=uuid)


def _har_with(mime_type):
    return {'log': {'entries': [{'response': {'content': {'size': 4, 'mimeType': mime_type,
                                                         'text': 'AAAA', 'encoding': 'base64'}}}]}}


def test_binary_bodies_are_left_out_unless_asked_for(tmp_path, monkeypatch):
    monkeypatch.setenv('HAR_FORMAT', 'har')
    monkeypatch.delenv('HAR_INCLUDE_BINARY', raising=False)

    def saved_content(mime_type):
        with open(save_har(str(tmp_path), _har_with(mime_type))) as f:
            return json.load(f)['log']['entries'][0]['response']['content']

    # The request is still listed with its size, only the payload is gone
    image = saved_content('image/png')
    assert 'text' not in image and 'encoding' not in image
    assert image['size'] == 4 and 'HAR_INCLUDE_BINARY' in image['comment']

    for readable in ('text/html; charset=utf-8', 'application/json', 'application/javascript', 'image/svg+xml'):
        assert saved_content(readable)['text'] == 'AAAA', readable

    monkeypatch.setenv('HAR_INCLUDE_BINARY', 'true')
    assert saved_content('image/png')['text'] == 'AAAA'


def test_har_format_selects_plain_har_or_zip(tmp_path, monkeypatch):
    monkeypatch.delenv('HAR_FORMAT', raising=False)
    assert save_har(str(tmp_path), _har_with('text/html')).endswith('har-record.zip')

    # Switching format must not leave the old recording lying around next to the new one
    monkeypatch.setenv('HAR_FORMAT', 'HAR')
    destination = save_har(str(tmp_path), _har_with('text/html'))
    assert [p.name for p in tmp_path.iterdir()] == ['har-record.har']
    with open(destination) as f:
        assert json.load(f)['log']['entries']

    monkeypatch.setenv('HAR_FORMAT', 'nonsense')
    save_har(str(tmp_path), _har_with('text/html'))
    assert [p.name for p in tmp_path.iterdir()] == ['har-record.zip']


def test_requests_responses_become_har_entries(monkeypatch):
    """The `requests` fetcher hands over the response of each hop"""
    from datetime import timedelta
    from types import SimpleNamespace

    def response(url, status, headers, body=b'', encoding='utf-8', request_headers=None):
        return SimpleNamespace(
            request=SimpleNamespace(method='GET', url=url, headers=request_headers or {}, body=None),
            raw=SimpleNamespace(headers=SimpleNamespace(items=lambda: headers), version=11),
            status_code=status, reason='whatever', content=body, encoding=encoding,
            elapsed=timedelta(milliseconds=120))

    monkeypatch.delenv('HAR_INCLUDE_BINARY', raising=False)
    recorded = [
        (1700000000.0, response('http://site/start?a=1', 302,
                                [('Location', '/img.png'), ('Set-Cookie', 'a=1; Path=/'), ('Set-Cookie', 'b=2')],
                                request_headers={'Cookie': 'session=abc'})),
        (1700000000.2, response('http://site/img.png', 200, [('Content-Type', 'image/png')], body=b'\x89PNG')),
        (1700000000.4, response('http://site/page', 200, [('Content-Type', 'text/html')], body='héllo'.encode())),
    ]
    redirect, image, page = har_from_requests_responses(recorded, title='t')['log']['entries']

    assert redirect['response']['status'] == 302
    assert redirect['response']['redirectURL'] == '/img.png'
    assert redirect['response']['cookies'] == [{'name': 'a', 'value': '1'}, {'name': 'b', 'value': '2'}]
    assert redirect['request']['cookies'] == [{'name': 'session', 'value': 'abc'}]
    assert redirect['request']['queryString'] == [{'name': 'a', 'value': '1'}]
    assert redirect['time'] == 120.0 and redirect['response']['httpVersion'] == 'HTTP/1.1'

    assert image['response']['content'] == {'size': 4, 'mimeType': 'image/png'}
    assert page['response']['content']['text'] == 'héllo'

    monkeypatch.setenv('HAR_INCLUDE_BINARY', '1')
    image = har_from_requests_responses(recorded)['log']['entries'][1]
    assert image['response']['content']['encoding'] == 'base64'

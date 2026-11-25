"""Persistence check (demo tooling): fingerprint every watch of a WebPulse instance, or compare two fingerprints.

    python demo/persistence_check.py snapshot <base_url> <datastore_dir> <out.json>
    python demo/persistence_check.py compare <before.json> <after.json>
"""
import json
import sys

import requests


def snapshot(base, ds, out):
    key = json.load(open(ds + r'\changedetection.json', encoding='utf-8'))['settings']['application']['api_access_token']
    h = {'x-api-key': key}
    data = {}
    for uuid, w in requests.get(base + '/api/v1/watch', headers=h, timeout=30).json().items():
        full = requests.get(f'{base}/api/v1/watch/{uuid}', headers=h, timeout=30).json()
        hist = requests.get(f'{base}/api/v1/watch/{uuid}/history', headers=h, timeout=30).json()
        data[uuid] = {
            'title': full.get('title'), 'url': full.get('url'), 'processor': full.get('processor'),
            'fetch_backend': full.get('fetch_backend'), 'paused': full.get('paused'), 'tags': sorted(full.get('tags') or []),
            'notification_urls': full.get('notification_urls'), 'include_filters': full.get('include_filters'),
            'snapshots': sorted(hist.keys()), 'restock': full.get('processor_state_restock_diff'),
        }
    groups = requests.get(base + '/api/v1/tags', headers=h, timeout=30).json()
    json.dump({'watches': data, 'groups': sorted(t['title'] for t in groups.values())}, open(out, 'w'), indent=1)
    print(f'{base}: {len(data)} watches, {sum(len(v["snapshots"]) for v in data.values())} snapshots, {len(groups)} groups -> {out}')


def compare(a, b):
    A, B = json.load(open(a)), json.load(open(b))
    problems = []
    if A['groups'] != B['groups']:
        problems.append('groups differ')
    for uuid, wa in A['watches'].items():
        wb = B['watches'].get(uuid)
        if not wb:
            problems.append(f'missing after restart: {wa["title"]}')
            continue
        for k in wa:
            if k == 'snapshots':
                if not set(wa[k]) <= set(wb[k]):     # new checks may add snapshots, none may disappear
                    problems.append(f'{wa["title"]}: snapshots lost')
            elif k != 'restock' and wa[k] != wb[k]:
                problems.append(f'{wa["title"]}: {k} changed')
    n_snap = sum(len(v['snapshots']) for v in A['watches'].values())
    print(f'compared {len(A["watches"])} watches / {n_snap} snapshots / {len(A["groups"])} groups: '
          + ('ALL INTACT' if not problems else f'{len(problems)} PROBLEM(S)'))
    for p in problems:
        print('  ', p)


if __name__ == '__main__':
    if sys.argv[1] == 'snapshot':
        snapshot(*sys.argv[2:5])
    else:
        compare(*sys.argv[2:4])

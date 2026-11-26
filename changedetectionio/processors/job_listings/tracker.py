# WebPulse structured job tracking (2026, written for the simplified fork of changedetection.io, Apache-2.0).
#
# Compares the openings found by one check with what WebPulse already knows about this careers page, and keeps
# the per-watch state file jobs.json (next to history.txt in the watch's data folder):
#
#   jobs      every opening ever seen, keyed by its id (canonical job URL): fields, first_seen, added_at,
#             last_seen, status active/removed, removed_at, modified_at and the last field changes
#   events    one entry per check that changed something: added / removed / modified openings and the number
#             of active openings afterwards - this is the job history and the data for the chart
#
# Rules:
#   * The first successful extraction is the baseline: its openings are recorded but are not "new".
#   * Changing the selector or keywords re-baselines: openings that no longer match are forgotten, openings that
#     now match are recorded silently - a filter edit is not a job change.
#   * Order never matters (sets of ids). Duplicate ids on one page count once.
#   * A check that fails, or finds no openings at all, never reaches this module (see processor.py), so a
#     temporary failure cannot mark every job as removed. A sudden drop to <= 20% of the openings must be seen on
#     two checks in a row before the missing openings are marked as removed.
# Pure functions plus load/save - no network, no Flask.
import json
import os
import tempfile

from .extract import FIELDS

STATE_FILE = 'jobs.json'
STATE_VERSION = 1
MAX_EVENTS = 1000
MAX_REMOVED_KEPT = 1500
MAX_CHANGES_PER_JOB = 20
SUDDEN_DROP_MIN_PREVIOUS = 10
SUDDEN_DROP_RATIO = 0.2


class SuspiciousDrop(Exception):
    def __init__(self, found, previous):
        self.found, self.previous = found, previous
        super().__init__(f"Only {found} of the {previous} openings seen last time were found")


def empty_state():
    return {'version': STATE_VERSION, 'baseline_at': None, 'filter_hash': None, 'jobs': {}, 'events': [],
            'last_success': None, 'last_found': None, 'last_matched': None, 'strategy': None, 'company': None,
            'pending_drop': None}


def load_state(data_dir):
    path = os.path.join(data_dir or '', STATE_FILE)
    try:
        with open(path, encoding='utf-8') as f:
            state = json.load(f)
        if isinstance(state, dict) and isinstance(state.get('jobs'), dict):
            base = empty_state()
            base.update(state)
            return base
    except (OSError, ValueError):
        pass
    return empty_state()


def save_state(data_dir, state):
    """Atomic write (temp file + rename), so a reader never sees half a file"""
    os.makedirs(data_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=data_dir, prefix='.jobs-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, separators=(',', ':'))
        os.replace(tmp, os.path.join(data_dir, STATE_FILE))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _mini(rec):
    return {'id': rec['id'], 'title': rec.get('title', ''), 'location': rec.get('location', ''), 'url': rec.get('url', '')}


def active_jobs(state):
    return [j for j in state['jobs'].values() if j.get('status') == 'active']


def apply_check(state, jobs, now, filter_hash, found_total):
    """Update state with this check's (already keyword-filtered) openings.
    Returns the event dict ({'kind': 'baseline'|'change', ...}) or None when nothing changed.
    Raises SuspiciousDrop (state untouched) for an unconfirmed sudden drop."""
    first = state.get('baseline_at') is None
    rebaseline = not first and state.get('filter_hash') != filter_hash
    baseline = first or rebaseline

    # Sudden drop safeguard - only for an unchanged filter, a filter edit is expected to change the numbers
    prev_found = state.get('last_found') or 0
    if not baseline and prev_found >= SUDDEN_DROP_MIN_PREVIOUS and found_total <= prev_found * SUDDEN_DROP_RATIO:
        pending = state.get('pending_drop')
        if not pending or pending.get('found') != found_total:
            state['pending_drop'] = {'found': found_total, 'previous': prev_found, 'at': now}
            raise SuspiciousDrop(found_total, prev_found)
    state['pending_drop'] = None

    current = {}
    for j in jobs:
        current.setdefault(j['id'], j)

    known = state['jobs']
    added, removed, modified = [], [], []

    for jid, j in current.items():
        rec = known.get(jid)
        if rec is None:
            rec = {'id': jid, **{f: j.get(f, '') for f in FIELDS}, 'url': j.get('url', ''),
                   'first_seen': now, 'added_at': now, 'last_seen': now, 'status': 'active',
                   'removed_at': None, 'modified_at': None, 'baseline': baseline, 'changes': []}
            known[jid] = rec
            if not baseline:
                added.append(_mini(rec))
            continue

        if rec.get('status') != 'active':
            # Re-opened (seen again after being removed)
            rec.update({'status': 'active', 'added_at': now, 'removed_at': None, 'baseline': baseline})
            if not baseline:
                added.append(_mini(rec))
        else:
            diffs = [{'field': f, 'old': rec.get(f, ''), 'new': j.get(f, '')}
                     for f in FIELDS if (rec.get(f) or '') != (j.get(f) or '')]
            if diffs and not baseline:
                rec['modified_at'] = now
                rec['changes'] = (rec.get('changes') or []) + [dict(d, at=now) for d in diffs]
                rec['changes'] = rec['changes'][-MAX_CHANGES_PER_JOB:]
                modified.append({**_mini(j | {'id': jid}), 'changes': diffs})
        for f in FIELDS:
            rec[f] = j.get(f, '')
        rec['url'] = j.get('url', '') or rec.get('url', '')
        rec['last_seen'] = now

    for jid in list(known):
        rec = known[jid]
        if rec.get('status') == 'active' and jid not in current:
            if rebaseline:
                del known[jid]          # no longer matches the new selector/keywords: not a removed opening
            else:
                rec.update({'status': 'removed', 'removed_at': now})
                removed.append(_mini(rec))

    # Keep the file bounded: forget the oldest removed openings first
    gone = sorted((r for r in known.values() if r.get('status') == 'removed'), key=lambda r: r.get('removed_at') or 0)
    for r in gone[:max(0, len(gone) - MAX_REMOVED_KEPT)]:
        del known[r['id']]

    state['filter_hash'] = filter_hash
    if first:
        state['baseline_at'] = now
    state['last_success'] = now
    state['last_found'] = found_total
    state['last_matched'] = len(current)

    event = None
    if baseline:
        event = {'at': now, 'kind': 'baseline', 'reason': 'first' if first else 'filters', 'active': len(current),
                 'added': [], 'removed': [], 'modified': []}
    elif added or removed or modified:
        event = {'at': now, 'kind': 'change', 'active': len(current),
                 'added': added, 'removed': removed, 'modified': modified}
    if event:
        state['events'] = (state.get('events') or []) + [event]
        state['events'] = state['events'][-MAX_EVENTS:]
    return event


def snapshot_text(state):
    """The text saved as the watch's version: one line per active opening, sorted, so the order on the page
    never matters. Notifications show the difference between two of these."""
    lines = []
    for j in sorted(active_jobs(state), key=lambda r: (r.get('title', '').lower(), r.get('location', '').lower(), r['id'])):
        parts = [j.get('title'), j.get('location'), j.get('employment_type'), j.get('team')]
        line = ' · '.join(p for p in parts if p)
        if j.get('url'):
            line += f"  {j['url']}"
        lines.append(line)
    return '\n'.join(lines) if lines else 'No matching job openings'


# ---------------------------------------------------------------------------------------------- read side
def is_new(rec, now, days):
    return (rec.get('status') == 'active' and not rec.get('baseline')
            and (not days or (rec.get('added_at') or 0) >= now - days * 86400))


def summary(state, now, days=7):
    """Counts for one careers page. days=0 means since monitoring started."""
    since = 0 if not days else now - days * 86400
    jobs = list(state['jobs'].values())
    return {
        'active': sum(1 for j in jobs if j.get('status') == 'active'),
        'new': sum(1 for j in jobs if is_new(j, now, days)),
        'removed': sum(1 for j in jobs if j.get('status') == 'removed' and (j.get('removed_at') or 0) >= since),
        'modified': sum(1 for j in jobs if j.get('status') == 'active' and (j.get('modified_at') or 0) > 0
                        and (j.get('modified_at') or 0) >= since),
        'known': len(jobs),
    }


def filtered_jobs(state, show, now, days=7):
    since = 0 if not days else now - days * 86400
    jobs = list(state['jobs'].values())
    if show == 'new':
        jobs = [j for j in jobs if is_new(j, now, days)]
    elif show == 'active':
        jobs = [j for j in jobs if j.get('status') == 'active']
    elif show == 'removed':
        jobs = [j for j in jobs if j.get('status') == 'removed' and (j.get('removed_at') or 0) >= since]
    elif show == 'modified':
        jobs = [j for j in jobs if j.get('status') == 'active' and (j.get('modified_at') or 0) > 0
                and (j.get('modified_at') or 0) >= since]
    # Active first, newest first, then by title
    return sorted(jobs, key=lambda j: (j.get('status') != 'active', -(j.get('added_at') or 0), j.get('title', '').lower()))


def timeline(state):
    """[(timestamp, active, added, removed, modified)] oldest first - for the chart"""
    return [(e['at'], e.get('active', 0), len(e.get('added') or []), len(e.get('removed') or []),
             len(e.get('modified') or [])) for e in state.get('events') or []]

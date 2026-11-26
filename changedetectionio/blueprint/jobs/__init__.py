# WebPulse "Job listings" pages (2026, written for the simplified fork of changedetection.io, Apache-2.0).
#
#   /jobs/              one card per careers page: active, new, removed and changed openings
#   /jobs/<uuid>        the openings of one careers page with filters (All / New / Active / Removed / Modified),
#                       first detected / last seen, apply links, a chart of active openings and the job history
#   /jobs/<uuid>/keywords   POST: change the keyword filter in plain words (re-baselines on the next check)
#
# Read-only views of processors/job_listings/tracker.py's jobs.json; checks are queued with the normal queue.
import time

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext

from changedetectionio.auth_decorator import login_optionally_required

SHOW = ('all', 'new', 'active', 'removed', 'modified')
PERIODS = (7, 30, 0)


def is_job_listings_watch(w):
    return w.get('processor') == 'job_listings'


def chart_geometry(points, width=640, height=170, pad_l=34, pad_r=12, pad_t=12, pad_b=24):
    """Step line of active openings over time, as SVG coordinates (computed here, drawn by the template)"""
    if not points:
        return None
    pts = list(points)
    now = int(time.time())
    if len(pts) == 1 or pts[-1][0] < now - 60:
        pts.append((now,) + tuple(pts[-1][1:2]) + (0, 0, 0))   # extend the last value to "now"
    t0, t1 = pts[0][0], pts[-1][0]
    vmax = max(max(p[1] for p in pts), 1)
    span_t = max(t1 - t0, 1)
    x = lambda t: pad_l + (t - t0) / span_t * (width - pad_l - pad_r)
    y = lambda v: pad_t + (1 - v / vmax) * (height - pad_t - pad_b)
    path = []
    for i, p in enumerate(pts):
        if i == 0:
            path.append(f"M{x(p[0]):.1f},{y(p[1]):.1f}")
        else:
            path.append(f"H{x(p[0]):.1f}V{y(p[1]):.1f}")
    markers = [{'x': round(x(p[0]), 1), 'y': round(y(p[1]), 1), 'at': p[0], 'active': p[1],
                'added': p[2], 'removed': p[3], 'modified': p[4]} for p in points]
    ticks = sorted({0, vmax, round(vmax / 2)})
    return {'w': width, 'h': height, 'path': ''.join(path), 'markers': markers,
            'yticks': [{'v': v, 'y': round(y(v), 1)} for v in ticks],
            'x0': pad_l, 'x1': width - pad_r, 'ybase': round(y(0), 1), 't0': t0, 't1': t1}


def daily_rows(events):
    """Additions/removals per day, newest first - the table view of the job history"""
    import datetime
    days = {}
    for e in events:
        if e.get('kind') != 'change':
            continue
        d = datetime.datetime.fromtimestamp(e['at']).strftime('%Y-%m-%d')
        row = days.setdefault(d, {'day': d, 'added': 0, 'removed': 0, 'modified': 0, 'active': 0})
        row['added'] += len(e.get('added') or [])
        row['removed'] += len(e.get('removed') or [])
        row['modified'] += len(e.get('modified') or [])
        row['active'] = e.get('active', 0)
    return sorted(days.values(), key=lambda r: r['day'], reverse=True)


def construct_blueprint(datastore, update_q, queuedWatchMetaData, worker_pool):
    from changedetectionio.processors.job_listings import tracker
    from changedetectionio.processors.job_listings.extract import keywords_from_rules

    bp = Blueprint('jobs', __name__, template_folder='templates')

    def _period():
        try:
            days = int(request.args.get('days', 7))
        except ValueError:
            days = 7
        return days if days in PERIODS else 7

    def _card(w, now, days):
        state = tracker.load_state(w.data_dir)
        return {'watch': w, 'state': state, 'summary': tracker.summary(state, now, days),
                'company': w.get('title') or state.get('company') or w.label,
                'keywords': keywords_from_rules(w.get('extract_text'))}

    @bp.route('/', methods=['GET'])
    @login_optionally_required
    def overview():
        from changedetectionio.blueprint.demo_lab import is_demo_watch
        now, days = int(time.time()), _period()
        watches = [w for w in datastore.data['watching'].values() if is_job_listings_watch(w)]
        cards = sorted((_card(w, now, days) for w in watches),
                       key=lambda c: (is_demo_watch(c['watch']), c['company'].lower()))
        totals = {k: sum(c['summary'][k] for c in cards) for k in ('active', 'new', 'removed', 'modified')}
        recent = []
        for c in cards:
            for e in c['state'].get('events') or []:
                if e.get('kind') == 'change':
                    recent.append((e, c))
        recent.sort(key=lambda ec: ec[0]['at'], reverse=True)
        return render_template('jobs-overview.html', cards=cards, totals=totals, days=days, periods=PERIODS,
                               recent=recent[:8], now=now)

    @bp.route('/<uuid_str:uuid>', methods=['GET'])
    @login_optionally_required
    def job_page(uuid):
        w = datastore.data['watching'].get(uuid)
        if not w:
            abort(404)
        if not is_job_listings_watch(w):
            return redirect(url_for('ui.ui_diff.diff_history_page', uuid=uuid))
        now, days = int(time.time()), _period()
        show = request.args.get('show', 'all')
        show = show if show in SHOW else 'all'
        card = _card(w, now, days)
        state = card['state']
        events = list(reversed(state.get('events') or []))
        # Opening the page counts as viewing the latest change (same as the inherited diff page does)
        if w.history_n:
            datastore.set_last_viewed(uuid, int(time.time()))
        return render_template('jobs-detail.html', c=card, w=w, state=state, show=show, days=days, periods=PERIODS,
                               jobs=tracker.filtered_jobs(state, show, now, days), now=now,
                               is_new=lambda j: tracker.is_new(j, now, days),
                               chart=chart_geometry(tracker.timeline(state)),
                               daily=daily_rows(state.get('events') or []),
                               events=events[:60], events_total=len(events))

    @bp.route('/<uuid_str:uuid>/check', methods=['POST'])
    @login_optionally_required
    def check_now(uuid):
        w = datastore.data['watching'].get(uuid)
        if not w:
            abort(404)
        if worker_pool.is_watch_running(uuid) or uuid in update_q.get_queued_uuids():
            flash(gettext('This careers page is already being checked.'))
        else:
            worker_pool.queue_item_async_safe(update_q, queuedWatchMetaData.PrioritizedItem(priority=1, item={'uuid': uuid}))
            flash(gettext('Checking %(name)s now - refresh in a few seconds.', name=w.label))
        if request.args.get('back') == 'overview':
            return redirect(url_for('jobs.overview'))
        return redirect(url_for('jobs.job_page', uuid=uuid))

    @bp.route('/<uuid_str:uuid>/keywords', methods=['POST'])
    @login_optionally_required
    def set_keywords(uuid):
        from changedetectionio.blueprint.ui.views import job_keywords_rule
        w = datastore.data['watching'].get(uuid)
        if not w or not is_job_listings_watch(w):
            abort(404)
        rule = job_keywords_rule(request.form.get('job_keywords', ''))
        w['extract_text'] = [rule] if rule else []
        datastore.update_watch(uuid=uuid, update_obj={'extract_text': w['extract_text']})
        worker_pool.queue_item_async_safe(update_q, queuedWatchMetaData.PrioritizedItem(priority=1, item={'uuid': uuid}))
        flash(gettext('Keywords saved. WebPulse is reading the page again; the openings that match now become the new starting point (no alert).')
              if rule else gettext('Keyword filter removed: every opening is tracked. WebPulse is reading the page again.'))
        return redirect(url_for('jobs.job_page', uuid=uuid))

    return bp

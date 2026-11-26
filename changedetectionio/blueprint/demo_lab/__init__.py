# WebPulse "Controlled demo" page (2026, based on changedetection.io, Apache-2.0, see CHANGES.md).
#
# For live presentations: a real website will not change on cue, so WebPulse also watches its own small demo
# site (e2e/fixture_server.py, started by run.ps1 on 127.0.0.1). This page changes that site on demand - a price
# drop, a restock, a new job - and then asks WebPulse to check it straight away, using exactly the same fetch,
# change-detection and notification code as for real websites.
#
# Security:
#  * The page only exists when run.ps1 sets WEBPULSE_DEMO_SITE, and that value must be http://127.0.0.1:<port>.
#  * The only outgoing requests it makes are POST /set and GET /state.json to that fixed address. Nothing the
#    user types is turned into a URL, so it cannot be used to reach anything else (no SSRF).
#  * Every action is a POST protected by the normal CSRF token and login.
#  * Everything it touches is labelled "Controlled demo" and lives on the reserved .test domain.
import os
import re
import time
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import gettext

from changedetectionio.auth_decorator import login_optionally_required

DEMO_DOMAIN = '.webpulse-demo.test'
_SITE_RE = re.compile(r'^http://127\.0\.0\.1:\d{2,5}$')

NEW_JOBS = ['Junior Backend Developer (Python, Django) - Pune', 'Data Engineering Intern - Remote',
            'Site Reliability Engineer - Hyderabad', 'Frontend Developer (React) - Bengaluru',
            'Machine Learning Engineer - Gurugram', 'Cloud Platform Engineer (AWS) - Chennai']
IRRELEVANT_JOB = 'Office Administrator - Mumbai'


def demo_site_url():
    """The local demo site, or None when the controlled demo is not enabled"""
    url = (os.getenv('WEBPULSE_DEMO_SITE') or '').strip().rstrip('/')
    return url if _SITE_RE.match(url) else None


def is_demo_watch(watch):
    host = (urlparse(watch.get('url') or '').hostname or '').lower()
    return host.endswith(DEMO_DOMAIN)


def construct_blueprint(datastore, update_q, queuedWatchMetaData, worker_pool):
    bp = Blueprint('demo_lab', __name__, template_folder='templates')

    @bp.app_context_processor
    def _demo_flags():
        return {'demo_lab_enabled': demo_site_url() is not None, 'is_demo_watch': is_demo_watch}

    def _site():
        import requests
        base = demo_site_url()
        return base, requests

    def _state():
        base, requests = _site()
        try:
            return requests.get(base + '/state.json', timeout=5).json()
        except Exception:
            return None

    def _set(**values):
        base, requests = _site()
        r = requests.post(base + '/set', params=values, timeout=5)
        r.raise_for_status()

    def _demo_watches(path_fragment=None):
        out = []
        for w in datastore.data['watching'].values():
            if is_demo_watch(w) and (path_fragment is None or path_fragment in w.get('url', '')):
                out.append(w)
        return out

    def _check_now(path_fragment):
        n = 0
        for w in _demo_watches(path_fragment):
            if w.get('paused'):
                continue
            worker_pool.queue_item_async_safe(update_q, queuedWatchMetaData.PrioritizedItem(priority=1, item={'uuid': w['uuid']}))
            n += 1
        return n

    @bp.route('/', methods=['GET'])
    @login_optionally_required
    def demo_page():
        if not demo_site_url():
            return render_template('demo-lab.html', enabled=False, state=None, groups={})
        state = _state()
        groups = {
            'product': _demo_watches('/product.html'),
            'jobs': _demo_watches('/jobs.html'),
            'news': _demo_watches('/page.html'),
        }
        jobs = [j for j in (state or {}).get('jobs', '').split('|') if j.strip()]
        return render_template('demo-lab.html', enabled=True, state=state, jobs=jobs, groups=groups,
                               alerts_on=any(u.strip().lower().startswith(('mailto', 'tgram://'))
                                             for u in datastore.data['settings']['application'].get('notification_urls') or []))

    @bp.route('/action', methods=['POST'])
    @login_optionally_required
    def demo_action():
        if not demo_site_url():
            flash(gettext('The controlled demo site is not running. Start WebPulse with run.ps1.'), 'error')
            return redirect(url_for('demo_lab.demo_page'))
        state = _state()
        if state is None:
            flash(gettext('The controlled demo site is not reachable. Restart WebPulse with run.ps1.'), 'error')
            return redirect(url_for('demo_lab.demo_page'))
        action = request.form.get('action', '')
        jobs = [j for j in state.get('jobs', '').split('|') if j.strip()]
        try:
            price = float(state.get('price') or 0)
        except ValueError:
            price = 0
        target, msg = None, None
        if action == 'price_drop':
            new = max(round(price * 0.85 / 10) * 10 - 1, 1)
            _set(price=f'{new:.2f}')
            target, msg = '/product.html', gettext('Price dropped from ₹%(old)s to ₹%(new)s.', old=f'{price:,.0f}', new=f'{new:,.0f}')
        elif action == 'price_rise':
            new = round(price * 1.12 / 10) * 10 - 1
            _set(price=f'{new:.2f}')
            target, msg = '/product.html', gettext('Price raised from ₹%(old)s to ₹%(new)s.', old=f'{price:,.0f}', new=f'{new:,.0f}')
        elif action == 'out_of_stock':
            _set(stock='OutOfStock')
            target, msg = '/product.html', gettext('The product is now out of stock.')
        elif action == 'back_in_stock':
            _set(stock='InStock')
            target, msg = '/product.html', gettext('The product is back in stock.')
        elif action == 'add_job':
            new_job = next((j for j in NEW_JOBS if j not in jobs), None)
            if not new_job:
                flash(gettext('All sample jobs are already published. Use “Reset the demo site” first.'), 'error')
                return redirect(url_for('demo_lab.demo_page'))
            _set(jobs='|'.join([new_job] + jobs))
            target, msg = '/jobs.html', gettext('New job published: %(job)s', job=new_job)
        elif action == 'add_irrelevant_job':
            if IRRELEVANT_JOB not in jobs:
                _set(jobs='|'.join(jobs + [IRRELEVANT_JOB]))
            target, msg = '/jobs.html', gettext('Published a non-technical job (%(job)s). The keyword filter should ignore it.', job=IRRELEVANT_JOB)
        elif action == 'remove_job':
            if not jobs:
                flash(gettext('There are no jobs left to remove.'), 'error')
                return redirect(url_for('demo_lab.demo_page'))
            removed = jobs[-1] if jobs[-1] != IRRELEVANT_JOB or len(jobs) == 1 else jobs[-2]
            _set(jobs='|'.join(j for j in jobs if j != removed) or '|')     # '|' = no jobs (an empty value is ignored)
            target, msg = '/jobs.html', gettext('Job removed: %(job)s', job=removed)
        elif action == 'modify_job':
            if not jobs:
                flash(gettext('There are no jobs to change.'), 'error')
                return redirect(url_for('demo_lab.demo_page'))
            first = jobs[0]
            changed = first.replace(' - ', ' - Hybrid, ', 1) if 'Hybrid' not in first else first.replace('Hybrid, ', '', 1)
            _set(jobs='|'.join([changed] + jobs[1:]))
            target, msg = '/jobs.html', gettext('Job changed: “%(old)s” is now “%(new)s”.', old=first, new=changed)
        elif action == 'shuffle_jobs':
            if len(jobs) < 2:
                flash(gettext('Publish at least two jobs first.'), 'error')
                return redirect(url_for('demo_lab.demo_page'))
            _set(jobs='|'.join(jobs[1:] + jobs[:1]))
            target, msg = '/jobs.html', gettext('The same jobs are now listed in a different order. WebPulse should report no change.')
        elif action in ('block_jobs_page', 'unblock_jobs_page'):
            blocked = action == 'block_jobs_page'
            _set(jobs_page='blocked' if blocked else 'normal')
            target, msg = '/jobs.html', (gettext('The careers page now shows a “verify you are human” page instead of the jobs. WebPulse should report an error and keep every opening.')
                                         if blocked else gettext('The careers page is back to normal.'))
        elif action == 'news_update':
            text = time.strftime('Company update at %H:%M: ') + gettext('our new office in Pune opens next month.')
            _set(text=text)
            target, msg = '/page.html', gettext('The news page text was changed.')
        elif action == 'reset':
            base, requests = _site()
            requests.post(base + '/reset', timeout=5)
            target, msg = None, gettext('The demo site is back to its starting state (nothing was checked).')
        else:
            flash(gettext('Unknown demo action.'), 'error')
            return redirect(url_for('demo_lab.demo_page'))

        if target:
            n = _check_now(target)
            msg += ' ' + (gettext('WebPulse is checking %(n)s demo page(s) now - the result appears below in a few seconds.', n=n) if n
                          else gettext('No demo watch uses this page yet.'))
        flash(msg)
        return redirect(url_for('demo_lab.demo_page'))

    return bp

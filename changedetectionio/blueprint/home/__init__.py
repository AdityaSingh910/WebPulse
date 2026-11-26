# WebPulse Home page (2026): one overview page organised around what people use WebPulse for - website
# monitoring, product prices, stock, job listings, price history and notifications - with the technical parts
# (scheduler, workers, fetch methods, API, storage) summarised in one small "behind the scenes" row.
# Presentation only: it reads the existing datastore / worker pool / queue and reuses existing helpers
# (price summary, timeago, price format). Based on changedetection.io (Apache-2.0), see CHANGES.md.
import os
import time

from flask import Blueprint, render_template

from changedetectionio.auth_decorator import login_optionally_required
from changedetectionio.store import ChangeDetectionStore

JOB_LISTINGS_GROUP = 'Job listings'


def construct_blueprint(datastore: ChangeDetectionStore, update_q, worker_pool):
    home_blueprint = Blueprint('home', __name__, template_folder='templates')

    # The "Job listings" group is what makes a website a job-listing monitor; make sure it exists so the
    # Job listings page is empty (not "everything") before the first careers page is added.
    if not datastore.tag_exists_by_name(JOB_LISTINGS_GROUP):
        datastore.add_tag(JOB_LISTINGS_GROUP)

    def job_tag_uuids():
        return {uuid for uuid, t in datastore.data['settings']['application'].get('tags', {}).items()
                if (t.get('title') or '').strip().lower() == JOB_LISTINGS_GROUP.lower()}

    def is_job_watch(w, tag_uuids=None):
        if w.get('processor') == 'job_listings':
            return True
        tag_uuids = job_tag_uuids() if tag_uuids is None else tag_uuids
        return bool(set(w.get('tags') or []) & tag_uuids)

    @home_blueprint.app_context_processor
    def _job_helpers():
        # Used by the sidebar (active item) and the website list ("Jobs" badge)
        uuids = job_tag_uuids()
        return {'job_listings_group': JOB_LISTINGS_GROUP, 'job_listings_tag_uuid': next(iter(uuids), None)}

    @home_blueprint.route('/', methods=['GET'])
    @login_optionally_required
    def home_page():
        from changedetectionio import forms
        from changedetectionio.blueprint.demo_lab import is_demo_watch, demo_site_url
        from changedetectionio.notification import history as notification_history
        from changedetectionio.notification import simple_setup
        from changedetectionio.processors.restock_diff.difference import _build_series, compute_price_summary

        app_settings = datastore.data['settings']['application']
        watches = list(datastore.data['watching'].values())
        now = time.time()
        job_uuids = job_tag_uuids()

        default_backend = app_settings.get('fetch_backend') or 'html_requests'

        def backend(w):
            b = w.get('fetch_backend') or 'system'
            return default_backend if b == 'system' else b

        default_interval = datastore.threshold_seconds

        def interval(w):
            if w.get('time_between_check_use_default', True):
                return default_interval
            return w.threshold_seconds() or default_interval

        def real_first(ws):
            """Real websites before controlled-demo ones, then most recently changed first"""
            return sorted(ws, key=lambda w: (is_demo_watch(w), -(w.last_changed or 0)))

        from changedetectionio.processors.job_listings import tracker as job_tracker
        products = [w for w in watches if w.get('processor') == 'restock_diff']
        jobs = [w for w in watches if w.get('processor') != 'restock_diff' and is_job_watch(w, job_uuids)]
        sites = [w for w in watches if w.get('processor') != 'restock_diff' and not is_job_watch(w, job_uuids)]
        active = [w for w in watches if not w.get('paused')]

        # ---- website monitoring ----
        site_changes = sorted([w for w in sites if w.last_changed], key=lambda w: w.last_changed, reverse=True)[:4]

        # ---- products / stock ----
        in_stock = [w for w in products if (w.get('restock') or {}).get('in_stock') is True]
        out_stock = [w for w in products if (w.get('restock') or {}).get('in_stock') is False]
        unknown_stock = [w for w in products if (w.get('restock') or {}).get('in_stock') is None]

        # ---- price analytics: the real product with the longest history (a demo one only if no real one has any) ----
        analytics = None
        with_history = sorted([w for w in products if w.history_n >= 2], key=lambda w: (is_demo_watch(w), -w.history_n))
        for w in with_history[:1]:
            try:
                summary = compute_price_summary(_build_series(w))
                if summary:
                    analytics = {'watch': w, 'summary': summary, 'currency': (w.get('restock') or {}).get('currency') or ''}
            except Exception:
                analytics = None

        # ---- notifications ----
        email_url, telegram_url, other_urls = simple_setup.split_urls(app_settings.get('notification_urls') or [])
        recent_sent = notification_history.read(datastore.datastore_path, limit=200)

        # ---- behind the scenes ----
        due = sorted(((max(0, (w.get('last_checked') or 0) + interval(w) - now)), w.label) for w in active)

        return render_template(
            'home.html',
            form=forms.quickWatchForm(None),
            browser_available=bool(os.getenv('PLAYWRIGHT_DRIVER_URL')),
            is_demo=is_demo_watch,
            demo_enabled=demo_site_url() is not None,
            demo_n=sum(1 for w in watches if is_demo_watch(w)),
            # websites
            sites=real_first(sites)[:5], sites_n=len(sites), site_changes=site_changes,
            unread_n=sum(1 for w in sites if w.has_unviewed),
            errors_n=sum(1 for w in watches if w.get('last_error')),
            # products and stock
            products=real_first(products)[:5], products_n=len(products),
            in_stock_n=len(in_stock), out_stock_n=len(out_stock), unknown_stock_n=len(unknown_stock),
            stock_list=real_first(in_stock + out_stock)[:4],
            # jobs
            jobs=real_first(jobs)[:5], jobs_n=len(jobs), jobs_unread_n=sum(1 for w in jobs if w.has_unviewed),
            job_summary={w.get('uuid'): job_tracker.summary(job_tracker.load_state(w.data_dir), now, 7)
                         for w in jobs if w.get('processor') == 'job_listings'},
            # analytics
            analytics=analytics,
            # notifications
            email_on=bool(email_url), telegram_on=bool(telegram_url), webhooks_n=len(other_urls),
            all_muted=app_settings.get('all_muted', False),
            sent_ok_n=sum(1 for h in recent_sent if h.get('ok') and h.get('kind') != 'test'),
            last_sent=recent_sent[0] if recent_sent else None,
            # behind the scenes
            default_interval=default_interval, all_paused=app_settings.get('all_paused', False),
            next_due=due[0] if due else None,
            workers_n=worker_pool.get_worker_count(), running_n=len(worker_pool.get_running_uuids()), queued_n=update_q.qsize(),
            static_n=sum(1 for w in watches if backend(w) == 'html_requests'),
            dynamic_n=sum(1 for w in watches if backend(w) == 'html_webdriver'),
            api_enabled=app_settings.get('api_access_token_enabled', True),
            total_snapshots=sum(w.history_n for w in watches),
            watches_total=len(watches),
        )

    return home_blueprint

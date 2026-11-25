# WebPulse Home page (2026): one overview page with a card per feature. Presentation only - it reads the
# existing datastore / worker pool / queue and reuses existing helpers (price summary, timeago, price format).
# Based on changedetection.io (Apache-2.0), see CHANGES.md.
import os
import time

from flask import Blueprint, render_template

from changedetectionio.auth_decorator import login_optionally_required
from changedetectionio.store import ChangeDetectionStore

DEMO_PREFIXES = ('[Demo]', '[Sample data]')


def construct_blueprint(datastore: ChangeDetectionStore, update_q, worker_pool):
    home_blueprint = Blueprint('home', __name__, template_folder='templates')

    @home_blueprint.route('/', methods=['GET'])
    @login_optionally_required
    def home_page():
        from changedetectionio import forms
        from changedetectionio.processors.restock_diff.difference import _build_series, compute_price_summary

        app_settings = datastore.data['settings']['application']
        req_settings = datastore.data['settings']['requests']
        watches = list(datastore.data['watching'].values())
        now = time.time()

        def is_demo(w):
            return (w.get('title') or '').startswith(DEMO_PREFIXES)

        default_backend = app_settings.get('fetch_backend') or 'html_requests'

        def backend(w):
            b = w.get('fetch_backend') or 'system'
            return default_backend if b == 'system' else b

        default_interval = datastore.threshold_seconds

        def interval(w):
            if w.get('time_between_check_use_default', True):
                return default_interval
            return w.threshold_seconds() or default_interval

        # ---- monitoring / changes ----
        active = [w for w in watches if not w.get('paused')]
        unread = [w for w in watches if w.has_unviewed]
        errors = [w for w in watches if w.get('last_error')]
        changed = sorted([w for w in watches if w.last_changed], key=lambda w: w.last_changed, reverse=True)[:4]

        # ---- products / stock / analytics ----
        products = [w for w in watches if w.get('processor') == 'restock_diff']
        in_stock = [w for w in products if (w.get('restock') or {}).get('in_stock') is True]
        out_stock = [w for w in products if (w.get('restock') or {}).get('in_stock') is False]
        unknown_stock = [w for w in products if (w.get('restock') or {}).get('in_stock') is None]
        products_view = sorted(products, key=lambda w: (is_demo(w), -(w.last_changed or 0)))[:5]

        analytics = None
        with_history = sorted([w for w in products if w.history_n >= 2], key=lambda w: w.history_n, reverse=True)
        if with_history:
            w = with_history[0]
            try:
                summary = compute_price_summary(_build_series(w))
                if summary:
                    analytics = {'watch': w, 'summary': summary, 'currency': (w.get('restock') or {}).get('currency') or ''}
            except Exception:
                analytics = None

        # ---- scraping ----
        static_n = sum(1 for w in watches if backend(w) == 'html_requests')
        dynamic_n = sum(1 for w in watches if backend(w) == 'html_webdriver')
        browser_available = bool(os.getenv('PLAYWRIGHT_DRIVER_URL'))
        # A ready-made comparison: the same page watched with both fetchers (matched by URL without the query string)
        pair = None
        by_base = {}
        for w in watches:
            by_base.setdefault(w.get('url', '').split('?')[0], []).append(w)
        for ws in by_base.values():
            s = [w for w in ws if backend(w) == 'html_requests' and w.history_n]
            d = [w for w in ws if backend(w) == 'html_webdriver' and w.history_n]
            if s and d:
                pair = {'static': s[0], 'dynamic': d[0]}
                break

        # ---- scheduling ----
        due = []
        for w in active:
            nxt = (w.get('last_checked') or 0) + interval(w)
            due.append((max(0, nxt - now), w))
        due.sort(key=lambda x: x[0])

        # ---- workers / queue ----
        running = worker_pool.get_running_uuids()

        # ---- notifications ----
        global_urls = app_settings.get('notification_urls') or []
        watch_urls = [w for w in watches if w.get('notification_urls')]

        # ---- history ----
        total_snapshots = sum(w.history_n for w in watches)
        first_ts = [int(next(iter(w.history.keys()))) for w in watches if w.history_n]

        return render_template(
            'home.html',
            form=forms.quickWatchForm(None),
            browser_available=browser_available,
            watches_total=len(watches), active_n=len(active), paused_n=len(watches) - len(active),
            demo_n=sum(1 for w in watches if is_demo(w)), errors_n=len(errors),
            unread_n=len(unread), changed=changed,
            products=products_view, products_n=len(products),
            in_stock_n=len(in_stock), out_stock_n=len(out_stock), unknown_stock_n=len(unknown_stock),
            out_stock=out_stock[:3],
            analytics=analytics,
            static_n=static_n, dynamic_n=dynamic_n, pair=pair,
            default_interval=default_interval, all_paused=app_settings.get('all_paused', False),
            jitter=req_settings.get('jitter_seconds', 0), next_due=due[:3],
            workers_n=worker_pool.get_worker_count(), running_n=len(running), queued_n=update_q.qsize(),
            global_urls_n=len(global_urls), watch_urls_n=len(watch_urls), all_muted=app_settings.get('all_muted', False),
            api_enabled=app_settings.get('api_access_token_enabled', True),
            total_snapshots=total_snapshots, oldest_snapshot=min(first_ts) if first_ts else None,
            is_demo=is_demo,
        )

    return home_blueprint

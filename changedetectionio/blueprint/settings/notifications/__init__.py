# Modified 2026 for the simplified (academic) fork of changedetection.io - optional features removed, see CHANGES.md
"""
Notification settings — child blueprint of /settings.

Registered by the parent settings blueprint at url_prefix='/notifications', so the
URLs land at /settings/notifications/<backend>. Today the only backend is apprise;
future backends (simple_email, raw webhooks, etc.) slot in as sibling routes here
without re-shaping the URL space again.

The eventual data-model refactor is to give each notification config its own
uuid (`notification_uuid`) referenced from global/watch/group settings, instead
of inlining apprise URL strings on every record — that's not done here; this
file just gives that future work a stable home.
"""
import os

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_babel import gettext

from changedetectionio.store import ChangeDetectionStore
from changedetectionio.auth_decorator import login_optionally_required


def construct_notifications_blueprint(datastore: ChangeDetectionStore):
    notifications_blueprint = Blueprint(
        'notifications', __name__,
        template_folder="templates",
    )

    # ---- WebPulse (2026): the simple Email + Telegram page. It edits the same notification_urls list
    #      that the Apprise pipeline reads; nothing about how notifications are sent changes. ----
    def _send_test(urls):
        """Send one real notification to `urls` now, and record it. Returns (ok, message)."""
        from changedetectionio.notification_service import NotificationContextData, set_basic_notification_vars
        from changedetectionio.notification.handler import process_notification
        from changedetectionio.notification import history
        watches = sorted(datastore.data['watching'].values(),
                         key=lambda w: (w.history_n >= 2, w.last_changed or 0), reverse=True)
        watch = watches[0] if watches else None
        if not watch:
            return False, gettext('Add at least one website first - the test message describes its latest change.')
        app_settings = datastore.data['settings']['application']
        n_object = NotificationContextData({
            'watch_url': watch.get('url'),
            'watch_open_url': watch.open_link_override or watch.get('url'),
            'notification_urls': urls,
            'notification_title': 'WebPulse test message - notifications are working',
            'notification_body': 'This is a test message from WebPulse.\n\n'
                                 'Example - the latest change of {{watch_title}} ({{watch_url}}):\n---\n{{diff}}\n---',
            'notification_format': app_settings.get('notification_format'),
            'as_async': False,
        })
        dates = list(watch.history.keys())
        prev = watch.get_history_snapshot(timestamp=dates[-2]) if len(dates) > 1 else ''
        cur = watch.get_history_snapshot(timestamp=dates[-1]) if dates else ''
        n_object.update(set_basic_notification_vars(current_snapshot=cur, prev_snapshot=prev, watch=watch,
                                                    triggered_text='', timestamp_changed=dates[-1] if dates else None))
        try:
            sent = process_notification(n_object, datastore)
        except Exception as e:
            history.record(datastore.datastore_path, urls, ok=False, kind='test', error=str(e), watch=watch)
            lines = history.clean_error(str(e), urls).splitlines()
            return False, (lines[-1][:300] if lines else gettext('sending failed'))
        history.record(datastore.datastore_path, urls, ok=True, kind='test',
                       title=(sent or [{}])[0].get('title', ''), watch=watch)
        return True, ''

    @notifications_blueprint.route("/", methods=['GET', 'POST'])
    @login_optionally_required
    def index():
        from changedetectionio.notification import simple_setup as ss, history
        app_settings = datastore.data['settings']['application']
        email_url, telegram_url, other = ss.split_urls(list(app_settings.get('notification_urls') or []))
        chats = []
        typed = {}

        def store(new_email, new_telegram, new_other):
            app_settings['notification_urls'] = [u for u in (new_email, new_telegram) if u] + list(new_other)
            datastore.commit()

        def back():
            return redirect(url_for('settings.notifications.index'))

        if request.method == 'POST':
            f = request.form
            action = f.get('action', '')

            if action in ('save_email', 'test_email'):
                # A blank password field means "keep the saved one" - it is never sent to the browser
                password = f.get('email_password') or ss.email_password_of(email_url)
                new_url, err = ss.build_email_url(f.get('email_sender'), password, f.get('email_recipients'),
                                                  f.get('email_smtp_host'), f.get('email_smtp_port'))
                if err:
                    flash(err, 'error')
                    typed = {k: f.get(k, '') for k in ('email_sender', 'email_recipients', 'email_smtp_host', 'email_smtp_port')}
                else:
                    store(new_url, telegram_url, other)
                    if action == 'test_email':
                        ok, msg = _send_test([new_url])
                        if ok:
                            flash(gettext('Saved. A test email was sent - check your inbox (and the spam folder).'))
                        else:
                            flash(gettext('Saved, but the test email failed: %(msg)s', msg=msg), 'error')
                    else:
                        flash(gettext('Email settings saved.'))
                    return back()

            elif action == 'remove_email':
                store(None, telegram_url, other)
                flash(gettext('Email notifications turned off and the saved password deleted.'))
                return back()

            elif action == 'find_chat':
                token = (f.get('telegram_token') or '').strip() or ss.telegram_token_of(telegram_url)
                chats, err = ss.find_telegram_chats(token)
                if err:
                    flash(err, 'error')
                elif len(chats) == 1:
                    new_url, _ = ss.build_telegram_url(token, chats[0][0])
                    if new_url:
                        store(email_url, new_url, other)
                        flash(gettext('Found your chat "%(name)s" (ID %(id)s) and saved it. Now press "Save and send test".',
                                      name=chats[0][1] or '-', id=chats[0][0]))
                        return back()
                else:
                    # Several chats messaged the bot - save the token and let the user pick one
                    typed = {'telegram_chat_id': ''}
                    if f.get('telegram_token') and ss.TELEGRAM_TOKEN_RE.match(token):
                        new_url, _ = ss.build_telegram_url(token, chats[0][0])
                        store(email_url, new_url, other)
                        telegram_url = new_url

            elif action in ('save_telegram', 'test_telegram'):
                token = (f.get('telegram_token') or '').strip() or ss.telegram_token_of(telegram_url)
                new_url, err = ss.build_telegram_url(token, f.get('telegram_chat_id'))
                if err:
                    flash(err, 'error')
                    typed = {'telegram_chat_id': f.get('telegram_chat_id', '')}
                else:
                    store(email_url, new_url, other)
                    if action == 'test_telegram':
                        ok, msg = _send_test([new_url])
                        if ok:
                            flash(gettext('Saved. A test message was sent - check Telegram.'))
                        else:
                            flash(gettext('Saved, but the test message failed: %(msg)s', msg=msg), 'error')
                    else:
                        flash(gettext('Telegram settings saved.'))
                    return back()

            elif action == 'remove_telegram':
                store(email_url, None, other)
                flash(gettext('Telegram notifications turned off and the saved bot token deleted.'))
                return back()

            elif action in ('save_webhook', 'test_webhook'):
                hooks = [l.strip() for l in (f.get('webhook_urls') or '').splitlines() if l.strip()]
                webhook_schemes = ('json://', 'jsons://', 'xml://', 'xmls://', 'form://', 'forms://',
                                   'get://', 'gets://', 'post://', 'posts://', 'put://', 'puts://')
                if any(not h.lower().startswith(webhook_schemes) for h in hooks):
                    flash(gettext('Only webhook addresses (json://, posts:// ...) can be entered here.'), 'error')
                    typed = {'webhook_urls': f.get('webhook_urls', '')}
                else:
                    store(email_url, telegram_url, hooks)
                    if action == 'test_webhook' and hooks:
                        ok, msg = _send_test(hooks)
                        flash(gettext('Saved, and a test was sent to the webhook.') if ok
                              else gettext('Saved, but the webhook test failed: %(msg)s', msg=msg), 'notice' if ok else 'error')
                    else:
                        flash(gettext('Webhook addresses saved.'))
                    return back()

        return render_template(
            "notifications-simple.html",
            email=ss.parse_email_url(email_url),
            telegram=ss.parse_telegram_url(telegram_url),
            webhooks=other,
            typed=typed,
            chats=chats,
            history=history.read(datastore.datastore_path, limit=100),
            # saved versions per website: the change page needs 2, and a deleted website gets no link at all
            versions={u: w.history_n for u, w in datastore.data['watching'].items()},
            all_muted=app_settings.get('all_muted', False),
            muted_watches=sum(1 for w in datastore.data['watching'].values() if w.get('notification_muted')),
        )

    # JSON for the notification setup widget (static/js/notification-setup.js), also used on the
    # watch and group edit pages. See notification/apprise_form.py.
    @notifications_blueprint.route("/apprise/services", methods=['GET'])
    @login_optionally_required
    def apprise_services():
        from changedetectionio.notification.apprise_form import list_services
        return jsonify(list_services(request.args.get('q')))

    @notifications_blueprint.route("/apprise/service/<string:schema>", methods=['GET'])
    @login_optionally_required
    def apprise_service(schema):
        from flask_babel import get_locale
        from changedetectionio.notification.apprise_form import describe_service
        form = describe_service(schema, lang=get_locale())
        if not form:
            return jsonify({'error': gettext('Unknown notification service')}), 404
        return jsonify(form)

    @notifications_blueprint.route("/apprise/build", methods=['POST'])
    @login_optionally_required
    def apprise_build():
        from changedetectionio.notification.apprise_form import build_url
        data = request.get_json(silent=True) or {}
        result = build_url(data.get('schema'), values=data.get('values') or {},
                           secure=data.get('secure', True), extra=data.get('extra') or {})
        return jsonify(result), (400 if 'error' in result else 200)

    @notifications_blueprint.route("/apprise", methods=['GET', 'POST'])
    @login_optionally_required
    def apprise():
        from changedetectionio import forms

        app_settings = datastore.data['settings']['application']
        # Seed the form with the currently stored values so GET (and a failed
        # POST that re-renders) shows what's persisted, not WTForms defaults.
        default = {
            'notification_urls': app_settings.get('notification_urls') or [],
            'notification_title': app_settings.get('notification_title') or '',
            'notification_body': app_settings.get('notification_body') or '',
            'notification_format': app_settings.get('notification_format') or '',
            'base_url': app_settings.get('base_url') or '',
        }

        form = forms.globalSettingsAppriseNotificationForm(
            formdata=request.form if request.method == 'POST' else None,
            data=default,
            extra_notification_tokens=datastore.get_unique_notification_tokens_available(),
        )

        if request.method == 'POST' and form.validate():
            for field in ('notification_urls', 'notification_title', 'notification_body',
                          'notification_format', 'base_url'):
                app_settings[field] = form.data.get(field)
            datastore.commit()
            flash(gettext("Settings updated."))
            return redirect(url_for('settings.notifications.apprise'))
        elif request.method == 'POST':
            flash(gettext("An error occurred, please see below."), "error")

        return render_template(
            "apprise.html",
            form=form,
            emailprefix=os.getenv('NOTIFICATION_MAIL_BUTTON_PREFIX', False),
            extra_notification_token_placeholder_info=datastore.get_unique_notification_token_placeholders_available(),
            settings_application=app_settings,
        )

    return notifications_blueprint

# WebPulse "Job listings" processor (2026, written for the simplified fork of changedetection.io, Apache-2.0).
#
# Same life cycle as the inherited text_json_diff and restock_diff processors: the scheduler queues the watch, a
# worker fetches the page with the normal fetchers (plain HTTP or the browser, proxies, SSRF checks), then calls
# run_changedetection() here. Instead of comparing page text, this reads the individual job openings
# (extract.py), compares them with the known ones by job id (tracker.py), and saves:
#   * jobs.json      the structured state and job history (tracker.py)
#   * a version      one sorted line per active opening, only when an opening was added, removed or changed -
#                    the worker saves it and sends the normal Email/Telegram alert with the difference
import hashlib
import json
import time

from loguru import logger

from ..base import difference_detection_processor
from ..exceptions import ProcessorException
from . import extract, tracker


def _(x): return x
name = _('Job listings (a careers page or job board)')
description = _('Reads each job opening and reports new, removed and changed openings')
list_badge_text = _('Jobs')
del _
processor_weight = 2


class perform_site_check(difference_detection_processor):

    # Read by worker.py: a baseline version (first check, or after the selector/keywords changed) is saved
    # without sending an alert
    suppress_change_notification = False

    def _error(self, message):
        return ProcessorException(message=message, url=self.watch.get('url'), status_code=self.fetcher.get_last_status_code(),
                                  screenshot=self.fetcher.screenshot, xpath_data=self.fetcher.xpath_data)

    def run_changedetection(self, watch, force_reprocess=False):
        from changedetectionio.processors.text_json_diff.processor import FilterConfig

        if not watch:
            raise Exception("Watch no longer exists.")

        now = int(time.time())
        filters = FilterConfig(watch, self.datastore, inject_ldjson_price_selectors=False)
        selectors = filters.include_filters
        keyword_rules = filters.extract_text
        filter_hash = hashlib.md5(json.dumps({'include': sorted(selectors), 'extract': sorted(keyword_rules),
                                              'subtract': sorted(filters.subtractive_selectors)}).encode()).hexdigest()

        self.screenshot = self.fetcher.screenshot
        self.xpath_data = self.fetcher.xpath_data
        self.update_last_raw_content_checksum(self.get_raw_document_checksum())

        try:
            found, strategy, company = extract.extract_jobs(self.fetcher.content or '', watch.link, selectors,
                                                            filters.subtractive_selectors)
        except extract.SelectorMatchedNothing as e:
            raise self._error(f"The page section \"{e}\" was not found on the page, so no job openings were read. "
                              f"Nothing was marked as removed. Check the CSS selector, or remove it to let WebPulse find the jobs itself.")

        html = self.fetcher.content or ''
        empty_reason = None
        if not found:
            # Only an explicit "no openings" signal from the board counts as an empty board. Anything else (blocked
            # page, bot check, redesign, temporary problem) is a failed read - never "every job was removed".
            empty_reason = extract.confirmed_empty(html, selectors)
            if not empty_reason:
                raise self._error("No job openings could be read from this page (the job list was empty or not recognised). "
                                  "Nothing was marked as removed; the next check tries again.")

        matches = extract.keyword_matcher(keyword_rules)
        jobs = [j for j in found if matches(j)]

        state = tracker.load_state(watch.data_dir)
        try:
            event = tracker.apply_check(state, jobs, now, filter_hash, found_total=len(found))
        except tracker.SuspiciousDrop as e:
            tracker.save_state(watch.data_dir, state)   # remembers the drop, so the next identical result confirms it
            raise self._error(f"{e}. This looks like a temporary problem with the page, so nothing was marked as removed yet. "
                              f"If the next check finds the same, the missing openings are marked as removed.")
        state['strategy'] = strategy
        state['company'] = company
        state['declared_total'] = extract.declared_total(html)
        state['empty_reason'] = empty_reason
        tracker.save_state(watch.data_dir, state)

        snapshot = tracker.snapshot_text(state)
        fetched_md5 = hashlib.md5(snapshot.encode('utf-8')).hexdigest()

        changed_detected = False
        if event and event['kind'] == 'change':
            changed_detected = True
        elif event and event['kind'] == 'baseline':
            # Save the baseline as a version (so "View page" shows the openings) but don't alert about it
            changed_detected = watch.get('previous_md5') != fetched_md5
            self.suppress_change_notification = True

        logger.debug(f"Watch UUID {watch.get('uuid')} jobs: {strategy}, {len(found)} found, {len(jobs)} match the keywords, "
                     f"event={event['kind'] if event else None} "
                     f"(+{len(event['added']) if event else 0} -{len(event['removed']) if event else 0} ~{len(event['modified']) if event else 0})")

        update_obj = {
            'last_notification_error': False,
            'last_error': False,
            'previous_md5': fetched_md5,
            'content-type': self.fetcher.get_all_headers().get('content-type', ''),
            'last_check_status': self.fetcher.get_last_status_code(),
        }
        return changed_detected, update_obj, snapshot

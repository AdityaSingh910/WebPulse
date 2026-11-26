# WebPulse "Job listings" processor (2026, written for the simplified fork of changedetection.io, Apache-2.0).
# extract.py reads the openings, tracker.py compares and stores them (jobs.json), processor.py ties it into the
# inherited scheduler/worker/fetcher pipeline. The pages are in blueprint/jobs.

# Processor capabilities (same filter options as the website watcher: page section, keywords, browser steps)
supports_visual_selector = True
supports_browser_steps = True
supports_text_filters_and_triggers = True
supports_text_filters_and_triggers_elements = True
supports_request_type = True

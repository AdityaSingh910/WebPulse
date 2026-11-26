#!/usr/bin/env python3
# Modified 2026 for the simplified (academic) fork of changedetection.io - optional features removed, see CHANGES.md

# run from dir above changedetectionio/ dir
# python3 -m pytest changedetectionio/tests/unit/test_xml_security.py

import pytest
from changedetectionio import html_tools


def _xxe_payload(file_path) -> str:
    # Path.as_uri() gives a valid file URI on every OS: file:///tmp/x on Linux, file:///C:/Users/x on Windows.
    # The old "file://" + str(path) produced file://C:\Users\x on Windows, which lxml rejects as an invalid URI
    # before it ever gets to the entity, so the test failed on Windows without testing the XXE protection.
    return f"""<?xml version="1.0"?>
<!DOCTYPE root [
  <!ENTITY xxe SYSTEM "{file_path.as_uri()}">
]>
<root><item>&xxe;</item></root>"""


def test_xxe_not_expanded_xpath_filter(tmp_path):
    """xpath_filter must not expand external entities (CVE-2026-41895)."""
    sentinel_file = tmp_path / "sentinel.txt"
    sentinel = "xxe_sentinel_should_never_appear_in_output"
    sentinel_file.write_text(sentinel)

    result = html_tools.xpath_filter("//item", _xxe_payload(sentinel_file), is_xml=True)
    assert sentinel not in result


def test_xxe_not_expanded_xpath1_filter(tmp_path):
    """xpath1_filter must not expand external entities (CVE-2026-41895)."""
    sentinel_file = tmp_path / "sentinel.txt"
    sentinel = "xxe_sentinel_should_never_appear_in_output"
    sentinel_file.write_text(sentinel)

    result = html_tools.xpath1_filter("//item", _xxe_payload(sentinel_file), is_xml=True)
    assert sentinel not in result

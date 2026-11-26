# WebPulse (2026): unit tests for the structured job-listing monitor (processors/job_listings).
# The HTML below copies the structure of the real boards used in the demonstration (Lever, Greenhouse,
# python.org) with made-up jobs, so the tests run offline.
import random

import pytest

from changedetectionio.processors.job_listings import extract, tracker
from changedetectionio.blueprint.ui.views import job_keywords_rule


@pytest.fixture(autouse=True)
def prepare_test_function():
    """These are pure-function tests: replace the suite's autouse fixture that starts a live server
    (which cannot start on native Windows, see e2e/known_windows_unit_failures.txt)"""
    yield

LEVER = """<html><head><title>Acme Data</title></head><body>
<nav><a href="https://jobs.lever.co/acme/nav-1">Careers home</a></nav>
<div class="postings-group"><div class="posting-category-title large-category-label">Engineering</div>
 <div class="posting" data-qa-posting-id="aaa-1"><div class="posting-apply"><a class="posting-btn-submit" href="https://jobs.lever.co/acme/aaa-1">Apply</a></div>
  <a class="posting-title" href="https://jobs.lever.co/acme/aaa-1?lever-source=linkedin"><h5 data-qa="posting-name">Backend Engineer</h5>
  <div class="posting-categories"><span class="workplaceTypes">On-site&nbsp;·&nbsp;</span><span class="sort-by-commitment commitment">Full time</span>
  <span class="sort-by-location location">Bangalore, India</span></div></a></div>
 <div class="posting" data-qa-posting-id="aaa-2"><a class="posting-title" href="https://jobs.lever.co/acme/aaa-2"><h5 data-qa="posting-name">Office Manager</h5>
  <div class="posting-categories"><span class="sort-by-location location">Pune</span></div></a></div>
</div>
<footer>Jobs powered by Lever <a href="https://jobs.lever.co/">Lever</a></footer></body></html>"""

GREENHOUSE = """<html><head><title>Jobs at Beta Careers</title></head><body>
<div class="job-posts--table--department"><h3 class="section-header">Engineering</h3><table>
<tr class="job-post"><td class="cell"><a href="https://job-boards.greenhouse.io/beta/jobs/101"><p class="body body--medium">Lead Data Engineer</p>
<p class="body body__secondary body--metadata">Hybrid in Bangalore, India</p></a></td></tr>
<tr class="job-post"><td class="cell"><a href="https://job-boards.greenhouse.io/beta/jobs/102?utm_source=x"><p class="body body--medium">DevOps Engineer II</p>
<p class="body body__secondary body--metadata">Remote</p></a></td></tr></table></div></body></html>"""

PYORG = """<html><head><title>Python Job Board | Python.org</title><meta property="og:site_name" content="Python.org"></head><body>
<header><a href="/jobs/">Jobs</a><a href="/jobs/create/">Post a job</a></header>
<ol class="list-recent-jobs">
<li><h2 class="listing-company"><span class="listing-company-name"><span class="listing-new">New</span>
<a href="/jobs/8219/">Senior Software Engineer</a><br/> Gamma Research Institute</span>
<span class="listing-location"><a href="/jobs/location/detroit/">Detroit, USA</a></span></h2>
<span class="listing-job-type"><a href="/jobs/type/ml/">Machine Learning</a>, <a href="/jobs/type/web/">Web</a></span></li>
<li><h2 class="listing-company"><span class="listing-company-name"><a href="/jobs/8213/">Data Scientist</a><br/> Delta Ltd</span>
<span class="listing-location"><a href="/jobs/location/remote/">Remote</a></span></h2></li>
</ol><footer><a href="/jobs/feed/rss/">RSS</a></footer></body></html>"""

JSONLD = """<html><head><title>Careers - Epsilon</title><script type="application/ld+json">
{"@context":"https://schema.org","@graph":[{"@type":"JobPosting","title":"Python Developer","url":"https://epsilon.example/careers/python-dev",
"hiringOrganization":{"@type":"Organization","name":"Epsilon"},"employmentType":["FULL_TIME"],
"jobLocation":{"@type":"Place","address":{"addressLocality":"Chennai","addressCountry":"IN"}}}]}</script></head><body><p>Join us</p></body></html>"""


def demo_page(jobs):
    items = ''.join(f"<li class='job'><a class='job-title' href='/jobs/{t.lower().replace(' ', '-')}'>{t}</a>"
                    f"<span class='job-location'>{l}</span><span class='job-type'>Full time</span></li>" for t, l in jobs)
    return (f"<html><head><title>DemoCorp Careers</title></head><body><p class='banner'>Visitors today: {random.randint(100, 999)}</p>"
            f"<ul id='job-list'>{items}</ul><footer>generated {random.random()}</footer></body></html>")


# --------------------------------------------------------------------------------------------- extraction
def test_lever_fields_ids_and_team():
    jobs, strategy, company = extract.extract_jobs(LEVER, 'https://jobs.lever.co/acme')
    assert strategy == 'Lever job board' and company == 'Acme Data'
    assert [j['title'] for j in jobs] == ['Backend Engineer', 'Office Manager']
    be = jobs[0]
    assert be['id'] == 'https://jobs.lever.co/acme/aaa-1'          # tracking parameter dropped
    assert be['location'] == 'Bangalore, India'
    assert be['employment_type'] == 'Full time · On-site'
    assert be['team'] == 'Engineering' and be['company'] == 'Acme Data'


def test_lever_selector_keeps_all_and_narrowing_selector_narrows():
    all_jobs, _, _ = extract.extract_jobs(LEVER, 'https://jobs.lever.co/acme', ['.posting-title'])
    assert len(all_jobs) == 2
    one, strategy, _ = extract.extract_jobs(LEVER, 'https://jobs.lever.co/acme', ['div.posting[data-qa-posting-id="aaa-2"]'])
    assert strategy == 'Lever job board' and [j['title'] for j in one] == ['Office Manager']


def test_greenhouse_title_location_team_and_canonical_url():
    jobs, strategy, company = extract.extract_jobs(GREENHOUSE, 'https://job-boards.greenhouse.io/beta', ['.job-post'])
    assert strategy == 'Greenhouse job board' and company == 'Beta'
    assert [(j['title'], j['location'], j['team']) for j in jobs] == [
        ('Lead Data Engineer', 'Hybrid in Bangalore, India', 'Engineering'), ('DevOps Engineer II', 'Remote', 'Engineering')]
    assert jobs[1]['url'] == 'https://job-boards.greenhouse.io/beta/jobs/102'


def test_generic_selector_cards_ignore_location_and_type_links():
    jobs, strategy, _ = extract.extract_jobs(PYORG, 'https://www.python.org/jobs/', ['.list-recent-jobs h2 a'])
    assert strategy == 'Page section (CSS selector)'
    assert [(j['title'], j['location'], j['company']) for j in jobs] == [
        ('Senior Software Engineer', 'Detroit, USA', 'Gamma Research Institute'), ('Data Scientist', 'Remote', 'Delta Ltd')]
    assert jobs[0]['url'] == 'https://www.python.org/jobs/8219'
    assert jobs[0]['employment_type'] == 'Machine Learning, Web'


def test_automatic_mode_skips_header_and_footer_links():
    jobs, strategy, _ = extract.extract_jobs(PYORG, 'https://www.python.org/jobs/')
    assert strategy == 'Job links found on the page'
    assert [j['title'] for j in jobs] == ['Senior Software Engineer', 'Data Scientist']


def test_jsonld_jobposting():
    jobs, strategy, _ = extract.extract_jobs(JSONLD, 'https://epsilon.example/careers')
    assert strategy == 'schema.org JobPosting data'
    assert jobs == [{'title': 'Python Developer', 'company': 'Epsilon', 'location': 'Chennai, IN', 'employment_type': 'Full time',
                     'team': '', 'url': 'https://epsilon.example/careers/python-dev', 'id': 'https://epsilon.example/careers/python-dev'}]


def test_container_selector_reads_each_card_and_ignores_changing_banner():
    html = demo_page([('Backend Engineer', 'Bengaluru'), ('Data Engineer', 'Hyderabad')])
    jobs, strategy, _ = extract.extract_jobs(html, 'http://careers.demo.test/jobs.html', ['#job-list'])
    assert [(j['title'], j['location'], j['employment_type']) for j in jobs] == [
        ('Backend Engineer', 'Bengaluru', 'Full time'), ('Data Engineer', 'Hyderabad', 'Full time')]
    assert all('Visitors' not in j['title'] for j in jobs)


def test_selector_that_matches_nothing_raises():
    with pytest.raises(extract.SelectorMatchedNothing):
        extract.extract_jobs(LEVER, 'https://jobs.lever.co/acme', ['.does-not-exist'])


def test_duplicate_ids_collapse_but_same_title_elsewhere_is_kept():
    html = demo_page([('Solution Engineer', 'Pune'), ('Solution Engineer', 'Pune')]).replace(
        "</ul>", "<li class='job'><a class='job-title' href='/jobs/se-2'>Solution Engineer</a><span class='job-location'>Bengaluru</span></li></ul>")
    jobs, _, _ = extract.extract_jobs(html, 'http://careers.demo.test/jobs.html', ['#job-list'])
    assert [(j['title'], j['location']) for j in jobs] == [('Solution Engineer', 'Pune'), ('Solution Engineer', 'Bengaluru')]


def test_canonical_url_rules():
    c = extract.canonical_url
    assert c('/jobs/1/?utm_source=a&gh_jid=55#apply', 'https://x.example/careers') == 'https://x.example/jobs/1?gh_jid=55'
    assert c('javascript:void(0)', 'https://x.example') is None
    assert c('mailto:hr@x.example', 'https://x.example') is None


def test_keyword_rule_matches_titles_like_the_existing_filter():
    match = extract.keyword_matcher([job_keywords_rule('engineer, intern, data')])
    assert match({'title': 'Software Engineering Intern'})
    assert match({'title': 'Summer Internship'})
    assert match({'title': 'Lead Data Engineer'})
    assert not match({'title': 'Internal Auditor'})
    assert not match({'title': 'Office Manager'})
    assert extract.keyword_matcher([])({'title': 'anything'})
    assert extract.keyword_matcher(['/[unclosed/'])({'title': 'invalid rules are ignored'})
    assert extract.keywords_from_rules([job_keywords_rule('engineer, c++')]) == ['engineer', 'c++']


# --------------------------------------------------------------------------------------------- tracking
def J(title, loc='Pune', jid=None, **kw):
    return extract.make_job(title, jid or f'https://x.example/jobs/{title.lower().replace(" ", "-")}', location=loc, **kw)


def run(state, jobs, t, fh='f1', found=None):
    return tracker.apply_check(state, jobs, t, fh, found_total=len(jobs) if found is None else found)


def test_first_check_is_a_baseline_without_new_jobs():
    s = tracker.empty_state()
    e = run(s, [J('A'), J('B')], 1000)
    assert e['kind'] == 'baseline' and e['active'] == 2 and not e['added']
    assert tracker.summary(s, 1000)['new'] == 0 and tracker.summary(s, 1000)['active'] == 2


def test_new_removed_modified_and_unchanged():
    s = tracker.empty_state()
    run(s, [J('A'), J('B'), J('C')], 1000)
    e = run(s, [J('A'), J('B', loc='Hybrid, Pune'), J('D')], 2000)
    assert [j['title'] for j in e['added']] == ['D']
    assert [j['title'] for j in e['removed']] == ['C']
    assert [(m['title'], m['changes']) for m in e['modified']] == [('B', [{'field': 'location', 'old': 'Pune', 'new': 'Hybrid, Pune'}])]
    sm = tracker.summary(s, 2000)
    assert (sm['active'], sm['new'], sm['removed'], sm['modified'], sm['known']) == (3, 1, 1, 1, 4)
    a = s['jobs'][J('A')['id']]
    assert a['first_seen'] == 1000 and a['last_seen'] == 2000 and a['status'] == 'active'
    assert run(s, [J('A'), J('B', loc='Hybrid, Pune'), J('D')], 3000) is None     # nothing changed
    assert s['jobs'][J('A')['id']]['last_seen'] == 3000


def test_reordering_is_not_a_change_and_snapshot_is_stable():
    s = tracker.empty_state()
    jobs = [J('A'), J('B'), J('C')]
    run(s, jobs, 1000)
    snap = tracker.snapshot_text(s)
    assert run(s, list(reversed(jobs)), 2000) is None
    assert tracker.snapshot_text(s) == snap


def test_duplicate_ids_in_one_check_count_once():
    s = tracker.empty_state()
    run(s, [J('A'), J('A')], 1000)
    assert tracker.summary(s, 1000)['active'] == 1


def test_filter_change_rebaselines_silently():
    s = tracker.empty_state()
    run(s, [J('Engineer'), J('Manager')], 1000, fh='f1')
    e = run(s, [J('Engineer'), J('Data Engineer')], 2000, fh='f2')
    assert e['kind'] == 'baseline' and e['reason'] == 'filters' and not e['added'] and not e['removed']
    assert J('Manager')['id'] not in s['jobs']                        # filtered out: forgotten, not "removed"
    assert not tracker.is_new(s['jobs'][J('Data Engineer')['id']], 2000, 7)


def test_sudden_drop_needs_confirmation():
    s = tracker.empty_state()
    jobs = [J(f'Job {i}') for i in range(12)]
    run(s, jobs, 1000)
    with pytest.raises(tracker.SuspiciousDrop):
        run(s, jobs[:1], 2000)
    assert tracker.summary(s, 2000)['active'] == 12                     # nothing removed yet
    e = run(s, jobs[:1], 3000)                                          # seen twice in a row: accepted
    assert len(e['removed']) == 11 and tracker.summary(s, 3000)['active'] == 1


def test_reopened_job_is_new_again_and_keeps_first_seen():
    s = tracker.empty_state()
    run(s, [J('A'), J('B')], 1000)
    run(s, [J('A')], 2000)
    e = run(s, [J('A'), J('B')], 3000)
    b = s['jobs'][J('B')['id']]
    assert [j['title'] for j in e['added']] == ['B'] and b['first_seen'] == 1000 and b['added_at'] == 3000


def test_new_badge_window():
    s = tracker.empty_state()
    run(s, [J('A')], 0)
    run(s, [J('A'), J('B')], 10 * 86400)
    b = s['jobs'][J('B')['id']]
    assert tracker.is_new(b, 12 * 86400, 7) and not tracker.is_new(b, 20 * 86400, 7) and tracker.is_new(b, 20 * 86400, 0)
    assert [j['title'] for j in tracker.filtered_jobs(s, 'new', 12 * 86400, 7)] == ['B']


def test_state_survives_save_and_load(tmp_path):
    s = tracker.empty_state()
    run(s, [J('A'), J('B')], 1000)
    run(s, [J('A'), J('C')], 2000)
    tracker.save_state(str(tmp_path), s)
    loaded = tracker.load_state(str(tmp_path))
    assert loaded == s
    assert tracker.timeline(loaded) == [(1000, 2, 0, 0, 0), (2000, 2, 1, 1, 0)]
    assert not list(tmp_path.glob('.jobs-*'))                           # no temp files left behind


def test_corrupt_state_file_starts_fresh(tmp_path):
    (tmp_path / tracker.STATE_FILE).write_text('{not json')
    assert tracker.load_state(str(tmp_path)) == tracker.empty_state()


# --------------------------------------------------------------------------------------------- audit additions
GH_NEW_TAG = """<html><head><title>Jobs at Theta</title></head><body><h2 data-testid="job-count-header">1 jobs</h2>
<tr class="job-post"><td class="cell"><a href="https://job-boards.greenhouse.io/theta/jobs/9"><p class="body body--medium">Lead Software Engineer<span class="tag-container"><span class="ellipse"><span class="tag-text">New</span></span></span></p>
<p class="body body__secondary body--metadata">Bengaluru</p></a></td></tr></body></html>"""

SMARTRECRUITERS = """<html><head><title>Iota Careers</title></head><body>
<section class="openings-section opening opening--grouped js-group"><header class="opening-header">Chennai, India 2 jobs</header>
<ul class="opening-jobs"><li class="opening-job job"><a class="link--block details" href="https://jobs.smartrecruiters.com/Iota/7440001-sde-ii?trid=abc">
<h4 class="details-title job-title">SDE II</h4><p class="details-desc job-desc"><span>Full-time</span><spl-tooltip content="Employees work in a hybrid mode"></spl-tooltip></p></a></li>
<li class="opening-job job"><a class="link--block details" href="https://jobs.smartrecruiters.com/Iota/7440002-analyst?trid=abc"><h4 class="job-title">Analyst</h4>
<p class="job-desc"><span>Full-time</span></p></a></li></ul></section></body></html>"""

LEVER_EMPTY = """<html><head><title>Kappa</title></head><body><div class="postings-wrapper"><p class="no-postings-message">No job postings currently open. Check back later!</p></div>
<div class="main-footer">Jobs powered by Lever</div></body></html>"""


def test_greenhouse_new_tag_is_not_part_of_the_title():
    jobs, _, _ = extract.extract_jobs(GH_NEW_TAG, 'https://job-boards.greenhouse.io/theta')
    assert [j['title'] for j in jobs] == ['Lead Software Engineer']
    assert extract.declared_total(GH_NEW_TAG) == 1


def test_smartrecruiters_board():
    jobs, strategy, company = extract.extract_jobs(SMARTRECRUITERS, 'https://careers.smartrecruiters.com/Iota')
    assert strategy == 'SmartRecruiters job board' and company == 'Iota'
    assert [(j['title'], j['location'], j['employment_type'], j['url']) for j in jobs] == [
        ('SDE II', 'Chennai, India', 'Full-time · Hybrid', 'https://jobs.smartrecruiters.com/Iota/7440001-sde-ii'),
        ('Analyst', 'Chennai, India', 'Full-time', 'https://jobs.smartrecruiters.com/Iota/7440002-analyst')]


def test_confirmed_empty_only_on_explicit_signals():
    assert extract.extract_jobs(LEVER_EMPTY, 'https://jobs.lever.co/kappa')[0] == []
    assert 'No job postings currently open' in extract.confirmed_empty(LEVER_EMPTY)
    assert extract.confirmed_empty('<h2 data-testid="job-count-header">0 jobs</h2>') == 'The Greenhouse board states "0 jobs"'
    demo_empty = "<body><h2>Open positions</h2><ul id='job-list'></ul><p class='no-openings'>No open positions right now.</p></body>"
    assert extract.confirmed_empty(demo_empty, ['#job-list'])
    # A bot check, a redesign or a missing list is a failed read, not an empty board
    assert extract.confirmed_empty('<body><h1>Checking your browser</h1><p>Please verify you are a human</p></body>', ['#job-list']) is None
    assert extract.confirmed_empty("<body><ul id='job-list'></ul></body>", ['#job-list']) is None
    assert extract.confirmed_empty('<body><footer>No jobs? Follow us</footer><main></main></body>') is None   # no selector, no platform


def test_confirmed_empty_board_removes_small_lists_but_big_drops_need_two_checks():
    s = tracker.empty_state()
    run(s, [J('A'), J('B')], 1000)
    e = run(s, [], 2000, found=0)
    assert [x['title'] for x in e['removed']] == ['A', 'B'] and tracker.summary(s, 2000)['active'] == 0
    s = tracker.empty_state()
    run(s, [J(f'Job {i}') for i in range(15)], 1000)
    with pytest.raises(tracker.SuspiciousDrop):
        run(s, [], 2000, found=0)
    assert len(run(s, [], 3000, found=0)['removed']) == 15

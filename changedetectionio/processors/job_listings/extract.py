# WebPulse job-listing extraction (2026, written for the simplified fork of changedetection.io, Apache-2.0).
#
# Turns a careers page (HTML already fetched by the normal fetchers) into a list of job openings:
#   {'id', 'title', 'company', 'location', 'employment_type', 'team', 'url'}
#
# Strategies, first match wins:
#   1. Lever job boards        (div.posting[data-qa-posting-id])
#   2. Greenhouse job boards   (.job-post a / div.opening a)
#   3. A CSS / XPath selector the user gave ("Page section"): each matched job card or link is one opening
#   4. schema.org JobPosting   (JSON-LD, used by many company careers pages)
#   5. Automatic: links that look like job pages (/jobs/123, /careers/backend-engineer ...), outside nav/footer
#
# For 1 and 2 a selector, if given, only narrows the result to the openings inside the selected part.
# Identity: the canonical job URL (query string reduced to known job-id parameters, no #fragment), so the
# order of the list and tracking parameters never matter. Pure functions only - no network, no datastore.
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

FIELDS = ('title', 'company', 'location', 'employment_type', 'team')
MAX_JOBS = 2000
MAX_FIELD = 300

# Query parameters that identify a job (kept in the canonical URL); everything else (utm_*, source, ...) is dropped
ID_QUERY_KEYS = {'gh_jid', 'jid', 'id', 'jobid', 'job_id', 'job', 'req', 'reqid', 'requisitionid', 'posting',
                 'postingid', 'pid', 'vacancy', 'vacancyid', 'position', 'positionid', 'opening', 'openingid'}
JOB_HREF_RE = re.compile(r'/(?:jobs?|careers?|positions?|openings?|vacanc\w*|roles?|opportunit\w*|postings?|requisitions?)'
                         r'(?:/|-|_|\?|=)[^/?#]+', re.I)
NOT_JOB_HREF_RE = re.compile(r'/(?:locations?|types?|categor(?:y|ies)|departments?|teams?|tags?|search|page|filter|feed|rss)'
                             r'(?:/|$)', re.I)
NAV_WORDS = {'jobs', 'careers', 'all jobs', 'view all jobs', 'see all jobs', 'open positions', 'apply', 'apply now',
             'next', 'previous', 'back', 'home', 'login', 'sign in', 'search', 'more', 'read more', 'learn more'}
CONTAINER_TAGS = {'body', 'html', 'ul', 'ol', 'table', 'tbody', 'thead', 'main', 'section', 'nav', 'header', 'footer', 'form'}
SEPARATORS = ' \t\r\n ·•–—|,;:-�'
EMPLOYMENT_TYPES = {'FULL_TIME': 'Full time', 'PART_TIME': 'Part time', 'CONTRACTOR': 'Contract', 'TEMPORARY': 'Temporary',
                    'INTERN': 'Internship', 'VOLUNTEER': 'Volunteer', 'PER_DIEM': 'Per diem', 'OTHER': 'Other'}


class SelectorMatchedNothing(Exception):
    pass


def clean(text):
    """Collapse whitespace and strip separators such as '·' from both ends"""
    if text is None:
        return ''
    text = re.sub(r'\s+', ' ', str(text))
    text = re.sub(r'\s+([,;])', r'\1', text).strip(SEPARATORS)
    return text[:MAX_FIELD]


def canonical_url(href, base_url):
    """Absolute http(s) URL without #fragment and without tracking parameters, or None"""
    href = (href or '').strip()
    if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:', 'data:')):
        return None
    try:
        parts = urlsplit(urljoin(base_url or '', href))
    except ValueError:
        return None
    if parts.scheme not in ('http', 'https') or not parts.netloc:
        return None
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if k.lower() in ID_QUERY_KEYS))
    path = parts.path.rstrip('/') or '/'
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ''))


def make_id(url, title, location):
    if url:
        return url
    key = f"{clean(title).lower()}|{clean(location).lower()}"
    return 'text:' + hashlib.md5(key.encode('utf-8')).hexdigest()[:16]


def make_job(title, url=None, location='', employment_type='', team='', company=''):
    title = clean(title)
    if not title:
        return None
    job = {'title': title, 'company': clean(company), 'location': clean(location),
           'employment_type': clean(employment_type), 'team': clean(team), 'url': url or ''}
    job['id'] = make_id(url, title, job['location'])
    return job


def _text(el):
    return clean(el.get_text(' ', strip=True)) if el is not None else ''


def _first_text(root, selector):
    for el in root.select(selector):
        t = _text(el)
        if t:
            return t
    return ''


def _join_unique(values):
    out = []
    for v in values:
        v = clean(v)
        if v and v.lower() not in [o.lower() for o in out]:
            out.append(v)
    return ' · '.join(out)


def page_company(soup):
    """Company name from og:site_name or the page title ("Jobs at HackerRank Careers" -> "HackerRank")"""
    og = soup.find('meta', attrs={'property': 'og:site_name'})
    if og and clean(og.get('content')):
        return clean(og.get('content'))
    title = _text(soup.title) if soup.title else ''
    title = re.split(r'\s[|–—-]\s', title)[0]
    title = re.sub(r'^(?:jobs|careers|open positions|current openings)\s+at\s+', '', title, flags=re.I)
    title = re.sub(r'\s+(?:careers?|jobs|job board|hiring)$', '', title, flags=re.I)
    return clean(title)


# ---------------------------------------------------------------------------------------------- platforms
def _section_heading(el, container_class_re, heading_selector):
    """Department/team heading of the group an opening is listed under"""
    parent = el.find_parent(class_=container_class_re)
    if parent is not None:
        return _first_text(parent, heading_selector)
    return ''


def lever_jobs(soup, base_url):
    jobs = []
    for p in soup.select('div.posting[data-qa-posting-id], div.posting'):
        a = p.select_one('a.posting-title[href]') or p.find('a', href=True)
        title = _first_text(p, '[data-qa="posting-name"], h5, .posting-name')
        if not title or a is None:
            continue
        employment = _join_unique([_first_text(p, '.commitment, .sort-by-commitment'),
                                   _first_text(p, '.workplaceTypes')])
        team = _first_text(p, '.department, .sort-by-team') or \
            _section_heading(p, re.compile(r'postings-group'), '.posting-category-title')
        jobs.append(make_job(title, canonical_url(a.get('href'), base_url),
                             location=_first_text(p, '.location, .sort-by-location'),
                             employment_type=employment, team=team))
    return [j for j in jobs if j]


def greenhouse_jobs(soup, base_url):
    jobs = []
    # Current Greenhouse boards (job-boards.greenhouse.io): <tr class="job-post"><a><p>Title</p><p>Location</p></a>
    for post in soup.select('.job-post'):
        a = post.find('a', href=True)
        if a is None:
            continue
        ps = [_text(p) for p in a.find_all('p')]
        ps = [p for p in ps if p]
        title = ps[0] if ps else _text(a)
        location = ps[1] if len(ps) > 1 else ''
        team = _section_heading(post, re.compile(r'department'), 'h2, h3, h4')
        jobs.append(make_job(title, canonical_url(a.get('href'), base_url), location=location, team=team))
    # Older boards (boards.greenhouse.io): <div class="opening"><a>Title</a><span class="location">..</span></div>
    if not jobs:
        for post in soup.select('div.opening'):
            a = post.find('a', href=True)
            if a is None:
                continue
            team = ''
            section = post.find_parent('section')
            if section is not None:
                team = _first_text(section, 'h2, h3, h4')
            jobs.append(make_job(_text(a), canonical_url(a.get('href'), base_url),
                                 location=_first_text(post, '.location'), team=team))
    return [j for j in jobs if j]


def _ld_items(data):
    if isinstance(data, list):
        for d in data:
            yield from _ld_items(d)
    elif isinstance(data, dict):
        if '@graph' in data:
            yield from _ld_items(data['@graph'])
        if 'itemListElement' in data:
            yield from _ld_items(data['itemListElement'])
        if 'item' in data and isinstance(data['item'], dict):
            yield from _ld_items(data['item'])
        yield data


def _ld_location(job):
    locs = job.get('jobLocation') or []
    locs = locs if isinstance(locs, list) else [locs]
    out = []
    for loc in locs:
        if isinstance(loc, dict):
            addr = loc.get('address') or {}
            if isinstance(addr, dict):
                country = addr.get('addressCountry')
                country = country.get('name') if isinstance(country, dict) else country
                out.append(', '.join(clean(x) for x in (addr.get('addressLocality'), addr.get('addressRegion'), country) if clean(x)))
            elif isinstance(addr, str):
                out.append(clean(addr))
    if str(job.get('jobLocationType') or '').upper() == 'TELECOMMUTE':
        out.append('Remote')
    return ' / '.join(o for o in out if o)


def jsonld_jobs(soup, base_url):
    jobs = []
    for script in soup.find_all('script', attrs={'type': re.compile(r'ld\+json', re.I)}):
        try:
            data = json.loads(script.string or script.get_text() or '')
        except (ValueError, TypeError):
            continue
        for item in _ld_items(data):
            types = item.get('@type')
            types = types if isinstance(types, list) else [types]
            if 'JobPosting' not in types:
                continue
            org = item.get('hiringOrganization') or {}
            company = org.get('name') if isinstance(org, dict) else org
            emp = item.get('employmentType') or ''
            emp = emp if isinstance(emp, list) else [emp]
            employment = _join_unique(EMPLOYMENT_TYPES.get(str(e).upper(), str(e).replace('_', ' ').capitalize()) for e in emp if e)
            url = canonical_url(item.get('url') or '', base_url)
            job = make_job(item.get('title') or item.get('name'), url, location=_ld_location(item),
                           employment_type=employment, company=company or '')
            ident = item.get('identifier')
            if job and not url and isinstance(ident, dict) and clean(ident.get('value')):
                job['id'] = 'ld:' + clean(ident.get('value'))   # no URL: the employer's own job id
            if job:
                jobs.append(job)
    return jobs


# ---------------------------------------------------------------------------------------------- generic
def _is_job_link(a, base_url, strict):
    url = canonical_url(a.get('href'), base_url)
    if not url:
        return None
    text = _text(a)
    if not text or text.lower() in NAV_WORDS or len(text) > 200:
        return None
    path = urlsplit(url).path
    if NOT_JOB_HREF_RE.search(path):
        return None
    if strict and not JOB_HREF_RE.search(url):
        return None
    if base_url and canonical_url(base_url, base_url) == url:
        return None
    return url


def _job_links(root, base_url, strict):
    """Distinct job links inside root (root itself included when it is a link), in page order"""
    seen, out = set(), []
    candidates = ([root] if getattr(root, 'name', None) == 'a' and root.get('href') else []) + root.find_all('a', href=True)
    for a in candidates:
        url = _is_job_link(a, base_url, strict)
        if url and url not in seen:
            seen.add(url)
            out.append((a, url))
    return out


def _card_for(link, base_url, strict):
    """The smallest ancestor that holds this job and no other job link (an <li>, <tr>, <article>, <div>)"""
    node = link
    for _ in range(6):
        parent = node.parent
        if parent is None or parent.name in CONTAINER_TAGS:
            break
        if len(_job_links(parent, base_url, strict)) > 1:
            break
        node = parent
    return node


def _parse_card(card, link, url, company):
    link_blocks = [t for t in (_text(b) for b in link.find_all(['p', 'div', 'span', 'h2', 'h3', 'h4', 'h5', 'h6'], recursive=False)) if t] if link is not None else []
    title = (_first_text(card, '[data-qa="posting-name"], [itemprop="title"], .job-title, .posting-name, .position-title, .job-name')
             or (link_blocks[0] if link_blocks else '')
             or (_text(link) if link is not None else '')
             or _first_text(card, 'h1, h2, h3, h4, h5, h6')
             or next((l for l in (clean(x) for x in card.get_text('\n').split('\n')) if l), ''))
    location = _first_text(card, '[class*="location"], [itemprop="jobLocation"], [data-qa*="location"]')
    if not location and len(link_blocks) > 1:
        location = link_blocks[1]
    if location == title:
        location = ''
    employment = _join_unique(el.get_text(' ', strip=True) for el in card.select(
        '[class*="commitment"], [class*="employment"], [class*="job-type"], [class*="jobtype"], [itemprop="employmentType"], [class*="workplace"]'))
    team = _first_text(card, '[class*="department"], [class*="team"]')
    card_company = ''
    company_el = card.select_one('[class*="company-name"], [class*="company"], [itemprop="hiringOrganization"]')
    if company_el is not None:
        remove = {_text(a) for a in company_el.find_all('a')} | {_text(e) for e in company_el.select('[class*="new"]')}
        parts = [clean(s) for s in company_el.stripped_strings]
        card_company = clean(' '.join(p for p in parts if p and p not in remove and p != title and p.lower() != 'new'))
    return make_job(title, url, location=location, employment_type=employment, team=team, company=card_company or company)


def generic_jobs(elements, base_url, company, strict=False):
    """Each selected element is a job card, a job link, or a container of several jobs"""
    cards, seen = [], set()

    def add(card, link, url):
        key = id(card)
        if key not in seen:
            seen.add(key)
            cards.append((card, link, url))

    for el in elements:
        links = _job_links(el, base_url, strict)
        if not links:
            if el.name == 'a':
                continue   # e.g. a "More jobs in Bengaluru" link the selector also matched
            children = [c for c in el.find_all(['li', 'tr', 'article'], recursive=True) if _text(c)]
            for c in (children or [el]):
                add(c, None, None)
        elif len(links) == 1 and el.name != 'a' and el.name not in CONTAINER_TAGS:
            add(el, links[0][0], links[0][1])
        else:
            for a, url in links:
                add(_card_for(a, base_url, strict), a, url)

    jobs = [_parse_card(card, link, url, company) for card, link, url in cards]
    return [j for j in jobs if j]


def _select(soup, selector):
    """Elements for one CSS or XPath selector (XPath results are re-parsed, so they lose their ancestors)"""
    from bs4 import BeautifulSoup
    selector = selector.strip()
    if selector.startswith(('/', 'xpath:', 'xpath1:')):
        from changedetectionio import html_tools
        expr = re.sub(r'^xpath1?:', '', selector)
        fragment = html_tools.xpath_filter(xpath_filter=expr, html_content=str(soup), append_pretty_line_formatting=False)
        frag = BeautifulSoup(fragment or '', 'html.parser')
        return [c for c in frag.children if getattr(c, 'name', None)]
    return soup.select(selector)


def _strip_chrome(soup):
    for el in soup.select('nav, header, footer, script, style, noscript, template, [role="navigation"], [aria-hidden="true"]'):
        el.decompose()


def extract_jobs(html, base_url, selectors=None, subtractive_selectors=None):
    """-> (jobs, strategy, company). Raises SelectorMatchedNothing when a selector was given but matched nothing."""
    from bs4 import BeautifulSoup
    selectors = [s for s in (selectors or []) if s and s.strip()]
    if subtractive_selectors:
        from changedetectionio import html_tools
        html = html_tools.element_removal(subtractive_selectors, html)
    soup = BeautifulSoup(html or '', 'html.parser')
    company = page_company(soup)

    selected = []
    for s in selectors:
        try:
            selected.extend(_select(soup, s))
        except Exception as e:
            raise SelectorMatchedNothing(f"{s} ({e})")
    if selectors and not selected:
        raise SelectorMatchedNothing(', '.join(selectors))

    jobs, strategy = [], None
    if soup.select_one('div.posting[data-qa-posting-id]'):
        jobs, strategy = lever_jobs(soup, base_url), 'Lever job board'
    elif soup.select_one('.job-post a[href], div.opening a[href]'):
        jobs, strategy = greenhouse_jobs(soup, base_url), 'Greenhouse job board'

    if strategy and selected:
        # Keep only the openings inside the part of the page the user selected
        urls, blob = set(), ' '.join(_text(e) for e in selected).lower()
        for e in selected:
            for _, url in _job_links(e, base_url, strict=False):
                urls.add(url)
        jobs = [j for j in jobs if j['url'] in urls or j['title'].lower() in blob]
    elif selected:
        jobs, strategy = generic_jobs(selected, base_url, company), 'Page section (CSS selector)'
    if not strategy or (not jobs and not selected):
        ld = jsonld_jobs(soup, base_url)
        if ld:
            jobs, strategy = ld, 'schema.org JobPosting data'
    if not jobs and not selected:
        _strip_chrome(soup)
        jobs, strategy = generic_jobs([soup.body or soup], base_url, company, strict=True), 'Job links found on the page'

    # Fill in the company, drop exact duplicates (same id), keep page order
    out, seen = [], set()
    for j in jobs:
        if j['id'] in seen:
            continue
        seen.add(j['id'])
        if not j.get('company'):
            j['company'] = company
        out.append(j)
        if len(out) >= MAX_JOBS:
            break
    return out, strategy or 'none', company


# ---------------------------------------------------------------------------------------------- keywords
def keyword_matcher(rules):
    """The job's title must match one of the watch's "Extract text" rules (the rule "Track jobs" creates from
    "engineer, data, intern"). No rules -> every job matches. Invalid regexes are ignored, not fatal."""
    from changedetectionio import html_tools
    compiled = []
    for r in rules or []:
        r = (r or '').strip()
        if not r:
            continue
        try:
            if re.search(html_tools.PERL_STYLE_REGEX, r, re.I):
                compiled.append(re.compile(html_tools.perl_style_slash_enclosed_regex_to_options(r)))
            else:
                compiled.append(re.compile(re.escape(r), re.I))
        except re.error:
            continue
    if not compiled:
        return lambda job: True
    return lambda job: any(c.search(job.get('title') or '') for c in compiled)


def keywords_from_rules(rules):
    """The words back from a rule made by job_keywords_rule(), for showing them in plain language"""
    words = []
    for r in rules or []:
        m = re.match(r'^/\.\*\\b\(\?:(.*)\)(?:\(\?:s\|es\|ing\|ship\|ships\)\?)?\\b\.\*/i$', r or '')
        if not m:
            return None
        words += [re.sub(r'\\(.)', r'\1', w) for w in m.group(1).split('|')]
    return words

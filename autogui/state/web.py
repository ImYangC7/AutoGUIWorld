# -*- coding: utf-8 -*-
"""Browser (pure-web) page and tab model.

The web counterpart of the desktop window inventory (``desktop_pc.py`` /
``desktop_linux.py``) and the mobile home-screen inventory (``mobile.py``).
Samples a structured active tab + background tabs for a browser OS, and supplies
the web-page content phrases that desktop browser windows draw from.

Static catalog data lives in ``catalog.py``; this module holds only the derived
indices and sampling logic. Re-exported from ``environment.py`` for backward
compatibility.
"""

import random
from urllib.parse import urlparse

from autogui.state.catalog import WEB_CATALOG, WEB_GENERIC_CONTENTS, WEB_SITE_URLS

def _flatten_web_catalog():
    out = list(WEB_GENERIC_CONTENTS)
    for sites in WEB_CATALOG.values():
        for phrases in sites.values():
            out.extend(phrases)
    return out


# Flattened pool (backward compatible): every catalog page + generic pages.
WEB_PAGE_CONTENTS = _flatten_web_catalog()

# Reverse index: content phrase -> site name (None for generic pages).
_PHRASE_TO_SITE = {}
for _sites in WEB_CATALOG.values():
    for _site, _phrases in _sites.items():
        for _p in _phrases:
            _PHRASE_TO_SITE[_p] = _site


def sample_web_content(rng=None, category=None, site=None):
    """Pick one web-page content phrase, optionally constrained.

    - site given:     pick from that site's templates (category optional).
    - category given: pick from any site in that category.
    - neither:        pick from the full flattened pool (generic + all sites).

    category/site are matched case-insensitively. Unknown constraints fail.

    Returns (phrase, site_name) where site_name is None for generic pages.
    """
    if rng is None:
        rng = random.Random()
    if category and not _match_key(WEB_CATALOG, category):
        raise ValueError('Unknown web category')
    if site:
        for cat, sites in WEB_CATALOG.items():
            if category and cat.lower() != category.lower():
                continue
            for s, phrases in sites.items():
                if s.lower() == site.lower():
                    return rng.choice(phrases), s
        raise ValueError('Unknown site or site outside the requested category')
    if category:
        for cat, sites in WEB_CATALOG.items():
            if cat.lower() == category.lower():
                pool = [(p, s) for s, phrases in sites.items() for p in phrases]
                if pool:
                    return rng.choice(pool)
    phrase = rng.choice(WEB_PAGE_CONTENTS)
    return phrase, _PHRASE_TO_SITE.get(phrase)

# === Pure-web (browser OS) page + tab model ===

def _match_key(mapping, value):
    """Case-insensitive key lookup for catalog category / site names."""
    if not value:
        return None
    for key in mapping.keys():
        if key.lower() == value.lower():
            return key
    return None

def web_site_url(site):
    """Return a canonical URL for a catalog site, or None if unknown."""
    if not site:
        return None
    return WEB_SITE_URLS.get(site)

def sample_web_page(rng=None, category=None, site=None, include_generic=False):
    """Pick one STRUCTURED web page from WEB_CATALOG.

    Returns {category, site, url, content}. category/site are matched
    case-insensitively; unknown constraints are rejected.
    Generic (brand-agnostic) pages are only drawn when include_generic=True and
    no explicit category/site matched.
    """
    if rng is None:
        rng = random.Random()

    matched_category = _match_key(WEB_CATALOG, category)
    if category and not matched_category:
        raise ValueError('Unknown web category')
    if site:
        categories = [matched_category] if matched_category else list(WEB_CATALOG.keys())
        for cat in categories:
            if not cat:
                continue
            matched_site = _match_key(WEB_CATALOG[cat], site)
            if matched_site:
                return {
                    'category': cat,
                    'site': matched_site,
                    'url': web_site_url(matched_site),
                    'content': rng.choice(WEB_CATALOG[cat][matched_site]),
                }
        raise ValueError('Unknown site or site outside the requested category')

    if matched_category:
        site_name = rng.choice(list(WEB_CATALOG[matched_category].keys()))
        return {
            'category': matched_category,
            'site': site_name,
            'url': web_site_url(site_name),
            'content': rng.choice(WEB_CATALOG[matched_category][site_name]),
        }

    if include_generic and rng.random() < 0.2:
        return {
            'category': 'Generic',
            'site': None,
            'url': None,
            'content': rng.choice(WEB_GENERIC_CONTENTS),
        }

    cat = rng.choice(list(WEB_CATALOG.keys()))
    site_name = rng.choice(list(WEB_CATALOG[cat].keys()))
    return {
        'category': cat,
        'site': site_name,
        'url': web_site_url(site_name),
        'content': rng.choice(WEB_CATALOG[cat][site_name]),
    }

def sample_browser_tabs(env_state, rng=None, web_category=None, web_site=None,
                        web_url=None, web_content=None):
    """Attach a structured active tab + background tabs to a pure-web browser
    state (the web counterpart of sample_windows / sample_home_screen).

    The active page is the task target surface; background tabs provide fixed
    global context without introducing OS-level windows. Mutates and returns
    env_state with: active_tab, background_tabs, target_app, target_surface.

    When web_url is given, the active tab is pinned to that explicit external URL
    (web_site/web_content optional) — used for real-task seeds. Otherwise the
    active tab is sampled from WEB_CATALOG (optionally constrained by
    web_category / web_site).
    """
    if rng is None:
        rng = random.Random()
    tab_count = max(1, int(env_state.get('open_tabs_count', 1)))
    env_state['open_tabs_count'] = tab_count
    if web_url:
        parsed = urlparse(web_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Web URL must be an HTTP(S) page without embedded login details')
        site_name = (web_site or parsed.netloc or web_url).strip()
        env_state['active_tab'] = {
            'category': web_category or 'External',
            'site': site_name,
            'url': web_url,
            'content': web_content or f'the {site_name} website homepage',
        }
    else:
        if web_content:
            raise ValueError('web_content requires web_url')
        env_state['active_tab'] = sample_web_page(
            rng, category=web_category, site=web_site, include_generic=False,
        )
    env_state['background_tabs'] = [
        sample_web_page(rng, include_generic=False)
        for _ in range(tab_count - 1)
    ]
    env_state['target_app'] = 'Google Chrome'
    env_state['target_surface'] = 'active web page'
    return env_state


BROWSER_APPS = {'Google Chrome', 'Microsoft Edge', 'Safari', 'Firefox'}

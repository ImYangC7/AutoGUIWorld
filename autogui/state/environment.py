# -*- coding: utf-8 -*-
"""Per-OS environment state: schemas, sampling, constraints, and description.

This is the aggregation layer of the state package. It owns the cross-OS pieces:
the per-OS parameter schemas (4th dimension of the state space: runtime state
before the task starts), the sampler + constraint engine, and the state->text
renderer. OS-specific data and samplers live in sibling modules and are
re-exported here so existing ``from autogui.state.environment import X`` callers
keep working:

  - catalog.py        static web tables (WEB_CATALOG, WEB_SITE_URLS, ...)
  - web.py            browser page/tab model (sample_web_page, sample_browser_tabs, ...)
  - desktop_pc.py     Windows 11 + macOS app pools (pc_app_pool)
  - desktop_linux.py  Ubuntu/GNOME app pool + left dock (sample_dock)
  - mobile.py         phone home-screen inventory

Sampling has two modes:
- default (rich=False): use 'default_pool' subset (mild realistic state)
- rich (rich=True):     use full 'options' (covers extreme states)
"""

import os as _os
import random

from autogui.state.mobile import home_screen_to_text
from autogui.state.catalog import (
    WEB_CATALOG, WEB_GENERIC_CONTENTS, WEB_SITE_URLS,
)
from autogui.state.web import (
    WEB_PAGE_CONTENTS, BROWSER_APPS, sample_web_content, sample_web_page,
    sample_browser_tabs, web_site_url,
)
from autogui.state.desktop_pc import (
    WINDOWS11_APP_POOL, MACOS_APP_POOL, pc_app_pool,
)
from autogui.state.desktop_linux import (
    UBUNTU_APP_POOL,
    DEFAULT_DOCK_FAVORITES, PERSONA_DOCK_EXTRAS, sample_dock,
)


# Public surface. Includes symbols re-exported from sibling modules so existing
# ``from autogui.state.environment import X`` callers keep working after the
# split (catalog / web / desktop_pc / desktop_linux).
__all__ = [
    # schemas + sampling + rendering (defined here)
    'OS_ENV_SCHEMAS', 'WINDOW_APP_POOL', 'WINDOW_POSITION_LAYOUTS',
    'ENV_CONSTRAINTS', 'PERSONA_NAMES', 'APP_EXCLUSIVE_GROUPS',
    'sample_environment_state', 'clean_state', 'sample_windows',
    'state_to_descriptive_text', 'has_blocking_state',
    # re-exported: static web data (catalog.py)
    'WEB_CATALOG', 'WEB_GENERIC_CONTENTS', 'WEB_SITE_URLS',
    # re-exported: browser page/tab model (web.py)
    'WEB_PAGE_CONTENTS', 'BROWSER_APPS', 'sample_web_content', 'sample_web_page',
    'sample_browser_tabs', 'web_site_url',
    # re-exported: desktop app pools + dock (desktop_pc.py / desktop_linux.py)
    'WINDOWS11_APP_POOL', 'MACOS_APP_POOL', 'UBUNTU_APP_POOL', 'pc_app_pool',
    'DEFAULT_DOCK_FAVORITES', 'PERSONA_DOCK_EXTRAS', 'sample_dock',
]


# === Per-OS schemas ===

OS_ENV_SCHEMAS = {
    'windows11': {
        # ── User identity ──
        'login_state':     {'options': ['logged_in', 'logged_out', 'lock_screen'],
                            'default_pool': ['logged_in']},
        'user_persona':    {'options': ['student', 'developer', 'office_worker', 'casual', 'designer'],
                            'default_pool': ['office_worker', 'casual', 'student']},
        'identity_locale': {'options': ['chinese', 'english'],
                            'default_pool': ['chinese', 'english']},
        # ── Desktop clutter ──
        'open_apps_count': {'options': [0, 1, 2, 3, 5],
                            'default_pool': [1, 2, 3]},
        'window_layout':   {'options': ['none', 'cascaded', 'tiled_2', 'main_with_bg', 'minimized'],
                            'default_pool': ['main_with_bg', 'cascaded']},
        'taskbar_density': {'options': ['default', 'crowded', 'minimal'],
                            'default_pool': ['default', 'crowded']},
        'desktop_files':   {'options': ['none', 'few', 'many'],
                            'default_pool': ['few', 'many']},
        # ── Notifications ──
        'pending_update':  {'options': [True, False],
                            'default_pool': [False]},
        'system_overlay':  {'options': ['none', 'toast', 'dropdown', 'modal_popup'],
                            'default_pool': ['none', 'toast']},
        # ── System ──
        'wifi_state':      {'options': ['connected', 'disconnected', 'limited'],
                            'default_pool': ['connected']},
        'battery_state':   {'options': ['high', 'medium', 'low', 'charging'],
                            'default_pool': ['high', 'charging']},
        'audio_devices':   {'options': ['none', 'one_connected', 'multi_some_disconnected'],
                            'default_pool': ['none', 'multi_some_disconnected']},
    },

    'macos': {
        'login_state':     {'options': ['logged_in', 'logged_out', 'lock_screen'],
                            'default_pool': ['logged_in']},
        'user_persona':    {'options': ['student', 'developer', 'office_worker', 'casual', 'designer'],
                            'default_pool': ['developer', 'designer', 'casual']},
        'identity_locale': {'options': ['chinese', 'english'],
                            'default_pool': ['english', 'chinese']},
        'open_apps_count': {'options': [0, 1, 2, 3, 5],
                            'default_pool': [2, 3]},
        'window_layout':   {'options': ['none', 'cascaded', 'split_view', 'main_with_bg', 'mission_control'],
                            'default_pool': ['main_with_bg', 'cascaded']},
        'dock_density':    {'options': ['minimal', 'default', 'crowded'],
                            'default_pool': ['default']},
        'menu_bar_extras': {'options': ['few', 'many'],
                            'default_pool': ['few', 'many']},
        'desktop_files':   {'options': ['none', 'few', 'many'],
                            'default_pool': ['few']},
        'system_overlay':  {'options': ['none', 'banner_notification', 'spotlight_open', 'control_center_open'],
                            'default_pool': ['none', 'banner_notification']},
        'wifi_state':      {'options': ['connected', 'disconnected'],
                            'default_pool': ['connected']},
        'battery_state':   {'options': ['high', 'medium', 'low', 'charging'],
                            'default_pool': ['high', 'charging']},
    },

    'ubuntu2404': {
        'login_state':       {'options': ['logged_in', 'logged_out', 'lock_screen'],
                              'default_pool': ['logged_in']},
        'user_persona':      {'options': ['student', 'developer', 'sysadmin', 'casual'],
                              'default_pool': ['developer', 'sysadmin']},
        'identity_locale':   {'options': ['chinese', 'english'],
                              'default_pool': ['english']},
        'open_apps_count':   {'options': [0, 1, 2, 3, 5],
                              'default_pool': [1, 2]},
        'window_layout':     {'options': ['none', 'cascaded', 'tiled_2', 'main_with_bg', 'minimized'],
                              'default_pool': ['main_with_bg', 'cascaded']},
        'workspaces_count':  {'options': [1, 2, 3, 4],
                              'default_pool': [1, 2]},
        'activities_overview':{'options': ['closed', 'open'],
                              'default_pool': ['closed']},
        'top_bar_indicators':{'options': ['minimal', 'standard', 'many_extensions'],
                              'default_pool': ['standard']},
        'dock_size':         {'options': ['minimal', 'default', 'rich'],
                              'default_pool': ['default', 'rich']},
        'desktop_files':     {'options': ['none', 'few'],
                              'default_pool': ['none', 'few']},
        'system_overlay':    {'options': ['none', 'notification', 'modal_dialog'],
                              'default_pool': ['none', 'notification']},
        'wifi_state':        {'options': ['connected', 'disconnected'],
                              'default_pool': ['connected']},
        'battery_state':     {'options': ['high', 'medium', 'low', 'charging', 'desktop_no_battery'],
                              'default_pool': ['charging', 'desktop_no_battery']},
    },

    'chrome_browser': {
        'browser_login':     {'options': ['signed_in', 'guest', 'incognito'],
                              'default_pool': ['signed_in']},
        'user_persona':      {'options': ['student', 'developer', 'shopper', 'researcher'],
                              'default_pool': ['student', 'shopper', 'researcher']},
        'identity_locale':   {'options': ['chinese', 'english'],
                              'default_pool': ['chinese', 'english']},
        'open_tabs_count':   {'options': [1, 3, 5, 10],
                              'default_pool': [3, 5]},
        'tab_groups':        {'options': [True, False],
                              'default_pool': [False]},
        'extensions_count':  {'options': [0, 2, 5],
                              'default_pool': [2]},
        'bookmarks_bar':     {'options': ['hidden', 'shown_few', 'shown_many'],
                              'default_pool': ['shown_few', 'shown_many']},
        'pending_download':  {'options': [True, False],
                              'default_pool': [False]},
        'history_autofill':  {'options': ['empty', 'has_suggestions'],
                              'default_pool': ['has_suggestions']},
        'site_notification': {'options': ['none', 'permission_prompt'],
                              'default_pool': ['none']},
    },

    'android': {
        'login_state':         {'options': ['unlocked', 'lock_screen', 'biometric_prompt'],
                                'default_pool': ['unlocked']},
        'user_persona':        {'options': ['student', 'office_worker', 'casual', 'gamer'],
                                'default_pool': ['casual', 'student', 'office_worker']},
        'identity_locale':     {'options': ['chinese', 'english'],
                                'default_pool': ['chinese']},
        'home_screen_page':    {'options': [0, 1, 2],
                                'default_pool': [0, 1]},
        'notification_drawer': {'options': ['closed', 'partially_open', 'fully_open'],
                                'default_pool': ['closed']},
        'unread_app_badges':   {'options': ['none', 'one_app', 'multiple'],
                                'default_pool': ['one_app', 'multiple']},
        'do_not_disturb':      {'options': [True, False],
                                'default_pool': [False]},
        'connection_state':    {'options': ['wifi_home', 'wifi_office', 'mobile_data', 'no_network'],
                                'default_pool': ['wifi_home', 'mobile_data']},
        'battery_state':       {'options': ['high', 'medium', 'low', 'charging'],
                                'default_pool': ['high', 'medium', 'charging']},
    },

    'ios': {
        'login_state':       {'options': ['unlocked', 'lock_screen', 'face_id_prompt'],
                              'default_pool': ['unlocked']},
        'user_persona':      {'options': ['student', 'office_worker', 'casual', 'creator'],
                              'default_pool': ['casual', 'student']},
        'identity_locale':   {'options': ['chinese', 'english'],
                              'default_pool': ['chinese', 'english']},
        'focus_mode':        {'options': ['off', 'do_not_disturb', 'work', 'sleep'],
                              'default_pool': ['off', 'work']},
        'dynamic_island':    {'options': ['idle', 'active_call', 'active_music', 'timer_running'],
                              'default_pool': ['idle', 'active_music']},
        'home_screen_page':  {'options': [0, 1, 2],
                              'default_pool': [0, 1]},
        'app_library_visible':{'options': [True, False],
                              'default_pool': [False]},
        'unread_app_badges': {'options': ['none', 'one_app', 'multiple'],
                              'default_pool': ['one_app', 'multiple']},
        'connection_state':  {'options': ['wifi_home', 'wifi_office', 'cellular_5G', 'no_network'],
                              'default_pool': ['wifi_home', 'cellular_5G']},
        'battery_state':     {'options': ['high', 'medium', 'low', 'charging'],
                              'default_pool': ['high', 'medium', 'charging']},
    },
}



# Structured window inventory across desktop OSes. Per-platform pools live in
# desktop_pc.py (Windows/macOS) and desktop_linux.py (Ubuntu); merged here so the
# shared sampler below addresses every desktop OS by os_key (unchanged layout).
WINDOW_APP_POOL = {
    'windows11': WINDOWS11_APP_POOL,
    'macos': MACOS_APP_POOL,
    'ubuntu2404': UBUNTU_APP_POOL,
}

WINDOW_POSITION_LAYOUTS = {
    'cascaded':    ['center', 'top-left', 'top-right', 'bottom-right', 'far-background'],
    'main_with_bg':['center', 'partially behind on the left', 'partially behind on the right',
                    'top-right corner', 'bottom-right corner'],
    'tiled_2':     ['left half', 'right half'],
    'split_view':  ['left half', 'right half'],
}


# Same-purpose apps that must not co-occur in one seed: opening two of them makes
# the desktop implausible and, worse, lets the task generator invent absurd
# "convert A into B" tasks between interchangeable tools (e.g. traj_719 asked to
# turn a LibreOffice Impress outline into a PowerPoint deck). Random window fill
# picks at most ONE app per group. Only genuinely redundant same-document-type
# suites are grouped — browsers, Adobe apps, chat clients, and 3D tools legitimately
# run side by side, so they are deliberately NOT listed here.
APP_EXCLUSIVE_GROUPS = [
    {'Microsoft Excel', 'LibreOffice Calc'},        # spreadsheets
    {'Microsoft Word', 'LibreOffice Writer'},       # word processors
    {'Microsoft PowerPoint', 'LibreOffice Impress'},  # presentations
]


def _exclusive_group_of(app):
    """Return the exclusive group containing app, or None."""
    for g in APP_EXCLUSIVE_GROUPS:
        if app in g:
            return g
    return None


# When AUTOGUI_MS_BIAS in (0,1] is set, any exclusive-group slot (spreadsheet /
# word / presentation) is resolved to its Microsoft variant with this probability
# and the LibreOffice variant otherwise. Default 0 disables the bias, keeping the
# legacy fully-random, byte-identical sampling for all other pipelines.
_MS_BIAS = float(_os.environ.get('AUTOGUI_MS_BIAS', '0'))
_MS_VARIANT = {
    frozenset({'Microsoft Excel', 'LibreOffice Calc'}): ('Microsoft Excel', 'LibreOffice Calc'),
    frozenset({'Microsoft Word', 'LibreOffice Writer'}): ('Microsoft Word', 'LibreOffice Writer'),
    frozenset({'Microsoft PowerPoint', 'LibreOffice Impress'}): ('Microsoft PowerPoint', 'LibreOffice Impress'),
}


def _apply_ms_bias(entry, pool, rng):
    """If entry's app is in an exclusive group and AUTOGUI_MS_BIAS is active, return
    the pool entry for the MS variant (prob=_MS_BIAS) or the LibreOffice variant.
    Otherwise return entry unchanged. Consumes one rng.random() only when biasing."""
    if _MS_BIAS <= 0:
        return entry
    g = _exclusive_group_of(entry[0])
    if g is None:
        return entry
    ms_app, lo_app = _MS_VARIANT[frozenset(g)]
    want = ms_app if rng.random() < _MS_BIAS else lo_app
    if want == entry[0]:
        return entry
    swapped = next((e for e in pool if e[0] == want), None)
    return swapped if swapped is not None else entry


def _fill_respecting_exclusives(candidates, fill_n, taken_names, rng):
    """Randomly pick fill_n pool entries, skipping any whose exclusive group is
    already represented (by taken_names or by an earlier pick). Preserves the
    reproducible-per-seed contract: consumes rng.sample over a shuffled order.
    """
    used_groups = set()
    for name in taken_names:
        g = _exclusive_group_of(name)
        if g is not None:
            used_groups.add(frozenset(g))

    order = rng.sample(candidates, len(candidates))  # reproducible shuffle
    picked = []
    for entry in order:
        if len(picked) >= fill_n:
            break
        g = _exclusive_group_of(entry[0])
        if g is not None:
            key = frozenset(g)
            if key in used_groups:
                continue
            used_groups.add(key)
            entry = _apply_ms_bias(entry, candidates, rng)
        picked.append(entry)
    return picked



def sample_windows(os_key, env_state, rng=None, web_category=None, web_site=None):
    """Sample desktop windows, their contents, positions, and stacking order.

    Windows are selected from the platform's application pool. The first sampled
    window is the foreground surface; later windows form the background. Browser
    windows use the shared website catalog and optional site/category constraints.
    Return an empty list for unsupported surfaces or hidden-window layouts.
    """
    if rng is None:
        rng = random.Random()
    pool = WINDOW_APP_POOL.get(os_key)
    if not pool:
        return []
    n = env_state.get('open_apps_count', 0)
    layout = env_state.get('window_layout', 'none')
    if n <= 0 or layout in ('none', 'minimized', 'mission_control'):
        return []

    positions = WINDOW_POSITION_LAYOUTS.get(layout, WINDOW_POSITION_LAYOUTS['cascaded'])

    n = min(n, len(pool))
    chosen = _fill_respecting_exclusives(pool, n, set(), rng)

    windows = []
    for i, (app, contents) in enumerate(chosen):
        position = positions[i] if i < len(positions) else 'in the background'
        win = {
            'app': app,
            'position': position,
            'role': 'foreground' if i == 0 else 'background',
        }
        if app in BROWSER_APPS:
            content, ws = sample_web_content(rng, category=web_category, site=web_site)
            win['content'] = content
            if ws:
                win['web_site'] = ws
        else:
            win['content'] = rng.choice(contents)
        windows.append(win)
    return windows


# Format: list of {'if': {...}, 'then_force': {...}} or 'then_exclude': {...}

ENV_CONSTRAINTS = [
    # logged_out / lock_screen → user-related details are irrelevant for visible state
    {'if': {'login_state': 'logged_out'}, 'then_force': {'window_layout': 'none', 'open_apps_count': 0, 'desktop_files': 'none'}},
    {'if': {'login_state': 'lock_screen'}, 'then_force': {'window_layout': 'none', 'open_apps_count': 0, 'desktop_files': 'none'}},
    {'if': {'login_state': 'unlocked'},   'then_force': {}},  # no-op marker

    # 0 open apps → window_layout must be 'none' (desktop)
    {'if': {'open_apps_count': 0}, 'then_force': {'window_layout': 'none'}},

    # do_not_disturb / focus_mode != off → no foreground notifications
    {'if': {'do_not_disturb': True}, 'then_exclude': {'unread_app_badges': []}},  # badges still visible

    # ios focus modes other than off conflict with active dynamic_island music
    {'if': {'focus_mode': 'sleep'}, 'then_force': {'dynamic_island': 'idle', 'unread_app_badges': 'none'}},

    # incognito has no signed_in identity
    {'if': {'browser_login': 'incognito'}, 'then_force': {'history_autofill': 'empty', 'extensions_count': 0}},

    # mission_control / activities_overview implicitly means no foreground popup
    {'if': {'window_layout': 'mission_control'}, 'then_force': {'system_overlay': 'none'}},
    {'if': {'activities_overview': 'open'}, 'then_force': {'system_overlay': 'none'}},

    # disconnected/no_network → can't be doing things that need network in initial state
    {'if': {'connection_state': 'no_network'}, 'then_exclude': {'unread_app_badges': []}},

    # ubuntu desktop has no battery
    {'if': {'battery_state': 'desktop_no_battery'}, 'then_force': {}},  # marker only
]


def _apply_constraints(sampled, schema):
    """Apply constraint rules to a sampled state. Modifies in place."""
    for rule in ENV_CONSTRAINTS:
        cond = rule['if']
        if all(sampled.get(k) == v for k, v in cond.items()):
            for k, v in rule.get('then_force', {}).items():
                if k in schema:
                    sampled[k] = v
            for k, excluded_vals in rule.get('then_exclude', {}).items():
                if k in schema and sampled.get(k) in excluded_vals:
                    pool = [opt for opt in schema[k]['options'] if opt not in excluded_vals]
                    if pool:
                        sampled[k] = pool[0]
    return sampled


def sample_environment_state(os_key, rich=False, rng=None):
    """Sample a runtime environment state for the given OS.

    Args:
        os_key: target OS (must be in OS_ENV_SCHEMAS)
        rich: if True, sample from full options; if False, from default_pool
        rng: optional random.Random for reproducibility

    Returns:
        dict mapping each schema parameter to a sampled value
    """
    if rng is None:
        rng = random.Random()
    schema = OS_ENV_SCHEMAS[os_key]
    sampled = {}
    for param, spec in schema.items():
        pool = spec['options'] if rich else spec.get('default_pool', spec['options'])
        if not pool:
            pool = spec['options']
        sampled[param] = rng.choice(pool)
    return _apply_constraints(sampled, schema)


def clean_state(os_key):
    """Return a 'clean baseline' env state — used when --skip-state is set."""
    schema = OS_ENV_SCHEMAS[os_key]
    state = {}
    # Pick the first/safest option for each param
    safest = {
        'login_state': 'logged_in', 'browser_login': 'signed_in',
        'open_apps_count': 0, 'open_tabs_count': 1,
        'window_layout': 'none', 'taskbar_density': 'default', 'dock_density': 'default',
        'desktop_files': 'none', 'pending_update': False, 'system_overlay': 'none',
        'wifi_state': 'connected', 'connection_state': 'wifi_home',
        'battery_state': 'high', 'audio_devices': 'none',
        'home_screen_page': 0, 'notification_drawer': 'closed',
        'unread_app_badges': 'none', 'do_not_disturb': False,
        'focus_mode': 'off', 'dynamic_island': 'idle', 'app_library_visible': False,
        'tab_groups': False, 'extensions_count': 0, 'bookmarks_bar': 'hidden',
        'pending_download': False, 'history_autofill': 'empty', 'site_notification': 'none',
        'workspaces_count': 1, 'activities_overview': 'closed', 'top_bar_indicators': 'minimal',
        'menu_bar_extras': 'few', 'identity_locale': 'english',
        'user_persona': 'casual',
    }
    for param, spec in schema.items():
        if param == 'login_state' and 'unlocked' in spec['options']:
            state[param] = 'unlocked'
        else:
            value = safest.get(param, spec['options'][0])
            state[param] = value if value in spec['options'] else spec['options'][0]
    return state


# === Description generation: state dict → English text ===

PERSONA_NAMES = {
    'chinese': {
        'student':       ('Li Wei', 'liwei2002@qq.com'),
        'developer':     ('Charles Wang', '921991830@qq.com'),
        'office_worker': ('Zhang Min', 'zhangmin@company.com'),
        'casual':        ('Wang Fang', 'fangw@163.com'),
        'designer':      ('Lin Yue', 'lin.yue@studio.com'),
        'sysadmin':      ('Liu Hao', 'admin@server.local'),
        'gamer':         ('Chen Kai', 'chenkai@qq.com'),
        'creator':       ('Zhao Yi', 'creator.zhao@gmail.com'),
        'shopper':       ('Sun Yan', 'shopperyan@taobao.com'),
        'researcher':    ('Hu Jing', 'huj@university.edu'),
    },
    'english': {
        'student':       ('Alex Chen', 'alex.chen@stanford.edu'),
        'developer':     ('Marcus Weber', 'marcus.dev@gmail.com'),
        'office_worker': ('Emily Johnson', 'emily.j@corp.com'),
        'casual':        ('Sam Taylor', 'sam.t@outlook.com'),
        'designer':      ('Sophia Rivera', 'sophia@designstudio.io'),
        'sysadmin':      ('Robert Kim', 'rkim@systems.org'),
        'gamer':         ('Jake Patterson', 'jake.gg@hotmail.com'),
        'creator':       ('Olivia Brooks', 'olivia@youtube.com'),
        'shopper':       ('Hannah Lee', 'hannah.lee@gmail.com'),
        'researcher':    ('Daniel Foster', 'd.foster@mit.edu'),
    },
}


def _persona_to_identity(persona, locale):
    """Pick a (name, email) pair for the persona."""
    table = PERSONA_NAMES.get(locale, PERSONA_NAMES['english'])
    return table.get(persona, ('User', 'user@example.com'))


def state_to_descriptive_text(os_key, env_state):
    """Render env_state into a multi-line English description for prompts."""
    lines = []
    cat_desc = {
        'windows11': 'Windows 11 desktop',
        'macos': 'macOS desktop',
        'ubuntu2404': 'Ubuntu 24.04 GNOME desktop',
        'chrome_browser': 'Chrome browser',
        'android': 'Android phone',
        'ios': 'iPhone',
    }.get(os_key, os_key)

    # ── Identity ──
    login = env_state.get('login_state') or env_state.get('browser_login')
    locale = env_state.get('identity_locale', 'english')
    persona = env_state.get('user_persona')
    if login in ('logged_in', 'unlocked', 'signed_in') and persona:
        name, email = _persona_to_identity(persona, locale)
        lines.append(f'• User: signed in as {name} ({email}), persona = {persona}.')
    elif login == 'logged_out':
        lines.append('• User: not logged in. A login screen is currently shown.')
    elif login == 'lock_screen':
        lines.append('• Lock screen is shown (clock visible, login required to proceed).')
    elif login == 'face_id_prompt':
        lines.append('• Face ID prompt overlay is showing.')
    elif login == 'biometric_prompt':
        lines.append('• Fingerprint / face unlock prompt is showing.')
    elif login == 'guest':
        lines.append('• Browser is in Guest mode (no Google account signed in).')
    elif login == 'incognito':
        lines.append('• Browser is in Incognito mode (private window).')

    # ── Mobile home-screen inventory (status bar / wallpaper / grid / dock) ──
    # When present it fully describes the visible mobile state, so the coarse
    # per-field mobile lines below are skipped to avoid duplication. Desktop
    # seeds never carry 'home_screen', so their output is unchanged.
    home_screen = env_state.get('home_screen')
    if home_screen:
        lines.append(home_screen_to_text(home_screen))

    # ── Open apps / tabs ──
    if 'open_apps_count' in env_state:
        n = env_state['open_apps_count']
        layout = env_state.get('window_layout', 'none')
        windows = env_state.get('windows') or []
        if n == 0:
            lines.append('• Desktop is empty (no other apps open in background).')
        elif windows:
            lines.append(f'• {n} window(s) open with layout = {layout}. Window inventory (position : app : content):')
            for w in windows:
                tag = ' [FOREGROUND / target]' if w.get('role') == 'foreground' else ''
                lines.append(f'    - {w["position"]} : {w["app"]} : {w["content"]}{tag}')
            lines.append('  Windows overlap and occlude each other according to the layout above.')
        else:
            lines.append(f'• {n} background app(s) open with layout = {layout}. They are visible behind/around the foreground task target.')
    if 'open_tabs_count' in env_state:
        lines.append(f'• Browser has {env_state["open_tabs_count"]} tab(s) open. Bookmarks bar = {env_state.get("bookmarks_bar","hidden")}.')
        # Pure-web browser OS: render the structured active tab (the task target
        # surface) + background tabs. Desktop browsers carry no active_tab here
        # (their web page lives inside a window in the 'windows' inventory).
        active_tab = env_state.get('active_tab')
        if active_tab:
            site = active_tab.get('site') or 'generic web page'
            url = active_tab.get('url')
            url_note = f' URL = {url};' if url else ''
            lines.append(
                f'• Active tab [TARGET]: {site} ({active_tab.get("category", "Unknown")});'
                f'{url_note} showing {active_tab["content"]}.'
            )
        background_tabs = env_state.get('background_tabs') or []
        if background_tabs:
            lines.append('• Background tabs remain open but are not the task target:')
            for tab in background_tabs:
                site = tab.get('site') or 'generic web page'
                lines.append(f'    - {site} ({tab.get("category", "Unknown")}): {tab["content"]}')

    # ── Ubuntu GNOME left dock (pinned favorites + running indicators) ──
    # Only present on ubuntu2404 logged-in seeds; other OS carry no 'dock' field
    # so this block is a no-op for them.
    dock = env_state.get('dock')
    if dock:
        pinned = dock.get('pinned') or []
        fav = ', '.join(f'{p["app"]}●' if p.get('running') else p['app'] for p in pinned)
        lines.append(
            f'• Left dock (GNOME, vertical, {dock.get("size","default")}): '
            f'pinned favorites = [{fav}].'
        )
        rnp = dock.get('running_not_pinned') or []
        if rnp:
            lines.append(
                '  Running apps not pinned appear after favorites (with a running '
                f'indicator dot): [{", ".join(rnp)}].'
            )
        lines.append('  (● marks an icon with a running-indicator dot.)')

    # ── Files / clutter ──
    if 'desktop_files' in env_state:
        df = env_state['desktop_files']
        lines.append(f'• Desktop file clutter: {df}.')
    if env_state.get('taskbar_density'):
        lines.append(f'• Taskbar density: {env_state["taskbar_density"]}.')
    if env_state.get('dock_density'):
        lines.append(f'• Dock density: {env_state["dock_density"]}.')

    # ── Notifications / overlays ──
    if env_state.get('system_overlay') and env_state['system_overlay'] != 'none':
        lines.append(f'• Active system overlay: {env_state["system_overlay"]} (visible on screen).')
    if env_state.get('pending_update'):
        lines.append('• A pending Windows Update notification is shown.')
    if env_state.get('site_notification') and env_state['site_notification'] != 'none':
        lines.append(f'• Browser shows {env_state["site_notification"]}.')
    if env_state.get('unread_app_badges') and env_state['unread_app_badges'] != 'none' and not home_screen:
        lines.append(f'• Unread app badges: {env_state["unread_app_badges"]}.')
    if env_state.get('notification_drawer') and env_state['notification_drawer'] != 'closed':
        lines.append(f'• Notification drawer is {env_state["notification_drawer"]}.')

    # ── Mobile-specific ──
    if 'home_screen_page' in env_state and not home_screen:
        lines.append(f'• Home screen page index: {env_state["home_screen_page"]}.')
    if env_state.get('focus_mode') and env_state['focus_mode'] != 'off':
        lines.append(f'• Focus mode is active: {env_state["focus_mode"]}.')
    if env_state.get('dynamic_island') and env_state['dynamic_island'] != 'idle' and not home_screen:
        lines.append(f'• Dynamic Island state: {env_state["dynamic_island"]}.')
    if env_state.get('do_not_disturb') and not home_screen:
        lines.append('• Do Not Disturb is enabled.')
    if env_state.get('app_library_visible'):
        lines.append('• App Library is currently visible.')

    # ── System ──
    if env_state.get('wifi_state'):
        lines.append(f'• WiFi: {env_state["wifi_state"]}.')
    if env_state.get('connection_state') and not home_screen:
        lines.append(f'• Network: {env_state["connection_state"]}.')
    if env_state.get('battery_state') and not home_screen:
        lines.append(f'• Battery: {env_state["battery_state"]}.')
    if env_state.get('audio_devices') and env_state['audio_devices'] != 'none':
        lines.append(f'• Audio devices: {env_state["audio_devices"]}.')

    # ── Browser-specific ──
    if env_state.get('extensions_count', 0) > 0:
        lines.append(f'• {env_state["extensions_count"]} browser extension icon(s) visible near address bar.')
    if env_state.get('pending_download'):
        lines.append('• A download is in progress (download bar visible at bottom).')
    if env_state.get('tab_groups'):
        lines.append('• Tab groups (colored labels) are visible above tabs.')

    # ── Linux-specific ──
    if env_state.get('workspaces_count', 1) > 1:
        lines.append(f'• Multiple GNOME workspaces ({env_state["workspaces_count"]}) in use.')
    if env_state.get('activities_overview') == 'open':
        lines.append('• GNOME Activities Overview is currently open.')
    if env_state.get('top_bar_indicators'):
        lines.append(f'• Top-bar indicators: {env_state["top_bar_indicators"]}.')

    # ── Menu bar (macOS) ──
    if env_state.get('menu_bar_extras'):
        lines.append(f'• Menu bar extras (right-side icons): {env_state["menu_bar_extras"]}.')

    return f'Initial environment state of the {cat_desc}:\n' + '\n'.join(lines)


def has_blocking_state(env_state):
    """Check if the state has blockers that require precondition actions before main task.

    Returns list of blocker descriptions (empty if none).
    """
    blockers = []
    login = env_state.get('login_state') or env_state.get('browser_login')
    if login in ('logged_out', 'lock_screen', 'face_id_prompt', 'biometric_prompt'):
        blockers.append(f'login required (current: {login})')
    if env_state.get('system_overlay') == 'modal_popup':
        blockers.append('modal popup must be dismissed first')
    if env_state.get('site_notification') == 'permission_prompt':
        blockers.append('browser permission prompt must be dismissed')
    if env_state.get('connection_state') == 'no_network':
        blockers.append('no network connection — must connect WiFi or mobile data first')
    if env_state.get('wifi_state') == 'disconnected':
        blockers.append('WiFi disconnected — may need to connect first')
    if env_state.get('activities_overview') == 'open':
        blockers.append('GNOME Activities Overview is open — must close first')
    if env_state.get('window_layout') == 'mission_control':
        blockers.append('Mission Control is open — must exit first')
    if env_state.get('notification_drawer') == 'fully_open':
        blockers.append('notification drawer is fully open — close it before task')
    return blockers

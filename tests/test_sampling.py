# -*- coding: utf-8 -*-
"""Offline catalog integrity, platform compatibility, and sampling invariants."""

import os
import random
import unittest

os.environ.setdefault('AUTOGUI_OMNI', '0')   # skip optional OmniParser detector

from autogui.state import catalog as C
from autogui.state import web as W
from autogui.state import desktop_pc as PC
from autogui.state import desktop_linux as LX
from autogui.state import mobile as MB
from autogui.state import environment as E


DESKTOP_OS = ['windows11', 'macos', 'ubuntu2404']
ALL_OS = ['windows11', 'macos', 'ubuntu2404', 'chrome_browser', 'android', 'ios']


def _app_names(pool):
    return [entry[0] for entry in pool]


class WebCatalogCleanlinessTest(unittest.TestCase):
    def setUp(self):
        self.catalog_sites = set()
        for sites in C.WEB_CATALOG.values():
            self.catalog_sites |= set(sites)

    def test_urls_and_catalog_sites_match_exactly(self):
        url_sites = set(C.WEB_SITE_URLS)
        self.assertEqual(url_sites - self.catalog_sites, set(),
                         'WEB_SITE_URLS has sites not present in WEB_CATALOG (dangling URL)')
        self.assertEqual(self.catalog_sites - url_sites, set(),
                         'WEB_CATALOG has sites with no canonical URL')

    def test_no_empty_content_templates(self):
        for cat, sites in C.WEB_CATALOG.items():
            for site, phrases in sites.items():
                self.assertTrue(phrases, f'{cat}/{site} has no content templates')
                for p in phrases:
                    self.assertTrue(p and p.strip(), f'{cat}/{site} has a blank template')

    def test_no_duplicate_site_across_categories(self):
        seen = {}
        for cat, sites in C.WEB_CATALOG.items():
            for site in sites:
                self.assertNotIn(site, seen,
                                 f'site {site!r} appears in both {seen.get(site)} and {cat}')
                seen[site] = cat

    def test_all_urls_well_formed(self):
        for site, url in C.WEB_SITE_URLS.items():
            self.assertTrue(url.startswith('http://') or url.startswith('https://'),
                            f'{site} URL not http(s): {url}')


class DesktopPoolCleanlinessTest(unittest.TestCase):
    POOLS = None

    @classmethod
    def setUpClass(cls):
        cls.POOLS = {
            'windows11': PC.WINDOWS11_APP_POOL,
            'macos': PC.MACOS_APP_POOL,
            'ubuntu2404': LX.UBUNTU_APP_POOL,
        }

    def test_app_names_unique_within_pool(self):
        for os_key, pool in self.POOLS.items():
            names = _app_names(pool)
            dupes = {n for n in names if names.count(n) > 1}
            self.assertEqual(dupes, set(), f'{os_key} pool has duplicate apps: {dupes}')

    def test_every_app_has_nonempty_content(self):
        for os_key, pool in self.POOLS.items():
            for app, contents in pool:
                self.assertTrue(contents, f'{os_key}/{app} has empty content list')
                for c in contents:
                    self.assertTrue(str(c).strip(), f'{os_key}/{app} has blank content')

    def test_entry_shape_is_name_then_content_list(self):
        for os_key, pool in self.POOLS.items():
            for entry in pool:
                self.assertEqual(len(entry), 2, f'{os_key} entry not (name, contents): {entry[0]}')
                self.assertIsInstance(entry[0], str)
                self.assertIsInstance(entry[1], list)

    def test_browser_windows_draw_from_shared_catalog(self):
        # Every browser app in a desktop pool must surface real catalog pages,
        # not bespoke per-OS web strings (keeps web content single-sourced).
        catalog_phrases = set(map(str, W.WEB_PAGE_CONTENTS))
        for os_key, pool in self.POOLS.items():
            for app, contents in pool:
                if app in W.BROWSER_APPS:
                    shared = set(map(str, contents)) & catalog_phrases
                    self.assertGreaterEqual(
                        len(shared), len(W.WEB_PAGE_CONTENTS),
                        f'{os_key}/{app} does not include the full shared web catalog')


class OSDistinctivenessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = set(_app_names(PC.WINDOWS11_APP_POOL))
        cls.mac = set(_app_names(PC.MACOS_APP_POOL))
        cls.ubu = set(_app_names(LX.UBUNTU_APP_POOL))


    def test_cross_os_overlap_is_only_portable_apps(self):
        # Any app shared between two desktop OSes must be genuinely cross-platform
        # (a curated allowlist). A surprising overlap signals a misplaced app.
        # 'Calculator' is an allowed same-name-different-app case: Windows
        # Calculator vs the GNOME Calculator are distinct apps that happen to
        # share the name. Pools are dispatched per-os_key (WINDOW_APP_POOL), so
        # no OS ever samples the wrong one — the shared string is harmless.
        portable = {
            'Google Chrome', 'Microsoft Word', 'Microsoft Excel', 'Microsoft Teams',
            'Slack', 'Zoom', 'Signal', 'Spotify', 'Visual Studio Code', 'Blender', 'VLC',
            'LibreOffice Calc', 'LibreOffice Writer', 'LibreOffice Impress', 'Calculator',
        }
        overlap = (self.win & self.mac) | (self.win & self.ubu) | (self.mac & self.ubu)
        unexpected = overlap - portable
        self.assertEqual(unexpected, set(),
                         f'unexpected cross-OS apps (not known portable): {unexpected}')

    def test_signature_native_apps_present(self):
        # Each OS must actually carry its hallmark native apps (sanity that pools
        # weren't accidentally swapped/emptied).
        self.assertIn('File Explorer', self.win)
        self.assertIn('Windows Terminal', self.win)
        self.assertIn('Finder', self.mac)
        self.assertIn('Safari', self.mac)
        self.assertIn('Files', self.ubu)
        self.assertIn('GNOME Terminal', self.ubu)


class PlatformMisplacementTest(unittest.TestCase):

    def _mobile_apps(self, os_key, locale, n=60):
        seen = set()
        for s in range(n):
            hs = MB.sample_home_screen(
                os_key, {'identity_locale': locale, 'unread_app_badges': 'none'},
                {}, random.Random(s))
            seen |= {t['name'] for t in hs['app_grid']}
            seen |= {d['name'] for d in hs['dock']}
        return seen

    # Hardcoded known-exclusive apps, INDEPENDENT of mobile.py's own _IOS_ONLY /
    # _ANDROID_ONLY sets — so the test fails if those sets are emptied/wrong,
    # rather than trivially passing by intersecting against the thing under test.
    KNOWN_IOS_ONLY = {'App Store', 'Safari'}
    KNOWN_ANDROID_ONLY = {'Google Play', '应用市场'}

    def test_ios_never_shows_android_exclusive_apps(self):
        for loc in ('chinese', 'english'):
            apps = self._mobile_apps('ios', loc)
            leaked = apps & self.KNOWN_ANDROID_ONLY
            self.assertEqual(leaked, set(),
                             f'iOS ({loc}) leaked Android-only apps: {leaked}')

    def test_android_never_shows_ios_exclusive_apps(self):
        for loc in ('chinese', 'english'):
            apps = self._mobile_apps('android', loc)
            leaked = apps & self.KNOWN_IOS_ONLY
            self.assertEqual(leaked, set(),
                             f'Android ({loc}) leaked iOS-only apps: {leaked}')

    def test_each_mobile_keeps_its_own_store_and_browser(self):
        ios_en = self._mobile_apps('ios', 'english')
        and_en = self._mobile_apps('android', 'english')
        self.assertIn('App Store', ios_en)
        self.assertIn('Safari', ios_en)
        self.assertIn('Google Play', and_en)
        # Android dock browser must not be the iOS-only Safari.
        self.assertNotIn('Safari', and_en)


class SamplingInvariantTest(unittest.TestCase):
    def test_clean_state_stays_inside_each_platform_schema(self):
        for os_key in ALL_OS:
            for key, value in E.clean_state(os_key).items():
                self.assertIn(value, E.OS_ENV_SCHEMAS[os_key][key]['options'])

    def test_sampled_state_is_reproducible_per_seed(self):
        for os_key in ALL_OS:
            a = E.sample_environment_state(os_key, rng=random.Random(123))
            b = E.sample_environment_state(os_key, rng=random.Random(123))
            self.assertEqual(a, b, f'{os_key} sampling not reproducible')

    def test_sampled_values_are_in_schema_options(self):
        for os_key in ALL_OS:
            schema = E.OS_ENV_SCHEMAS[os_key]
            for rich in (False, True):
                st = E.sample_environment_state(os_key, rich=rich, rng=random.Random(7))
                for param, value in st.items():
                    self.assertIn(param, schema, f'{os_key}: sampled unknown param {param}')
                    self.assertIn(value, schema[param]['options'],
                                  f'{os_key}.{param}={value!r} not in schema options')

    def test_window_sampler_never_co_occurs_exclusive_apps(self):
        # Same-purpose apps (Excel/Calc, Word/Writer, PowerPoint/Impress) must not
        # land in the same seed via random fill — that produced implausible desktops
        # and creates redundant cross-suite tasks. All window choices use this sampler.
        for os_key in DESKTOP_OS:
            for s in range(200):
                wins = E.sample_windows(
                    os_key, {'open_apps_count': 6, 'window_layout': 'cascaded'},
                    rng=random.Random(s))
                names = {w['app'] for w in wins}
                for group in E.APP_EXCLUSIVE_GROUPS:
                    shared = names & group
                    self.assertLessEqual(
                        len(shared), 1,
                        f'{os_key} seed {s} co-sampled exclusive apps: {shared}')

    def test_window_sampler_only_yields_pool_apps(self):
        for os_key in DESKTOP_OS:
            pool_names = set(_app_names(E.WINDOW_APP_POOL[os_key]))
            wins = E.sample_windows(
                os_key, {'open_apps_count': 5, 'window_layout': 'cascaded'},
                rng=random.Random(7))
            for w in wins:
                self.assertIn(w['app'], pool_names,
                              f'{os_key}: sampled window app {w["app"]} not in pool')

    def test_window_sampler_empty_for_nondesktop(self):
        for os_key in ('chrome_browser', 'android', 'ios'):
            self.assertEqual(
                E.sample_windows(os_key, {'open_apps_count': 3, 'window_layout': 'cascaded'},
                                 rng=random.Random(7)),
                [], f'{os_key} should have no desktop windows')

    def test_dock_only_for_logged_in_ubuntu(self):
        self.assertIsNotNone(E.sample_dock(
            'ubuntu2404', {'login_state': 'logged_in', 'dock_size': 'default',
                           'user_persona': 'developer', 'windows': []},
            rng=random.Random(7)))
        self.assertIsNone(E.sample_dock('windows11', {}, rng=random.Random(7)))
        self.assertIsNone(E.sample_dock(
            'ubuntu2404', {'login_state': 'logged_out'}, rng=random.Random(7)))

    def test_state_text_renders_for_every_os(self):
        for os_key in ALL_OS:
            st = E.sample_environment_state(os_key, rng=random.Random(7))
            text = E.state_to_descriptive_text(os_key, st)
            self.assertIsInstance(text, str)
            self.assertTrue(text.strip(), f'{os_key} produced empty description')


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""Operating System registry and action space definitions.

Each OS defines its fixed physical constraints: image aspect ratio,
design language, UI framework elements, and which action space applies.
"""

OS_REGISTRY = {
    'windows11': {
        'name': 'Windows 11',
        'category': 'desktop',
        'image_size': '1792x1024',
        'design_language': 'Fluent Design',
        'action_space': 'pc',
        'ui_framework': {
            'taskbar': 'bottom, centered icons',
            'window_controls': 'top-right (minimize, maximize, close)',
            'font': 'Segoe UI',
            'corner_radius': '8px rounded',
        },
        'prompt_prefix': 'A screenshot of a Windows 11 desktop.',
    },
    'macos': {
        'name': 'macOS Sequoia',
        'category': 'desktop',
        'image_size': '1792x1024',
        'design_language': 'Apple Human Interface Guidelines',
        'action_space': 'pc',
        'ui_framework': {
            'menu_bar': 'top, global menu bar with Apple logo',
            'window_controls': 'top-left (red/yellow/green traffic lights)',
            'dock': 'bottom, centered',
            'font': 'SF Pro',
            'corner_radius': '10px rounded',
        },
        'prompt_prefix': 'A screenshot of a macOS desktop.',
    },
    'android': {
        'name': 'Android 16',
        'category': 'mobile',
        'ecosystem': 'android',
        'image_size': '1024x2272',
        'design_language': 'Android 16 with Material 3 Expressive (Material You) design',
        'action_space': 'mobile',
        'ui_framework': {
            'status_bar': 'top (time on the left; right cluster: signal, Wi-Fi, battery), translucent',
            'navigation': 'gesture bar (pill home handle); optional 3-button',
            'font': 'Roboto / Roboto Flex',
            'icons': 'real full-color app icons in their native shapes (mostly rounded squares / squircles); brand colors preserved',
            'corner_radius': 'expressive large rounded (28dp+ containers)',
            'theming': 'Material You: home-screen accent/widgets pick up colors from the wallpaper',
            'containers': 'grouped rounded containers, frosted translucent quick-settings',
        },
        'prompt_prefix': 'A screenshot of an Android 16 phone home screen with the Material 3 Expressive (Material You) design, portrait orientation (tall 20:9 aspect ratio).',
    },
    'ios': {
        'name': 'iOS 26',
        'category': 'mobile',
        'ecosystem': 'apple',
        'image_size': '1024x2272',
        'design_language': 'iOS 26 with Apple Liquid Glass design',
        'action_space': 'mobile',
        'ui_framework': {
            'status_bar': 'top (time on the left; right cluster: signal, Wi-Fi, battery), with the pill-shaped Dynamic Island cutout centered at the very top',
            'navigation': 'thin home-indicator bar at the bottom, no back button',
            'font': 'SF Pro',
            'icons': 'real full-color app icons as glossy rounded squircles with a subtle Liquid Glass sheen and soft specular highlight; brand colors preserved',
            'corner_radius': 'large continuous (squircle) rounded corners',
            'material': 'Liquid Glass: translucent, glass-like UI layers that refract and pick up color from the wallpaper behind them',
            'dock': 'a floating translucent Liquid Glass dock pill at the bottom holding 4 icons',
        },
        'prompt_prefix': 'A screenshot of an iPhone home screen running iOS 26 with the Apple Liquid Glass design, portrait orientation (tall 20:9 aspect ratio).',
    },
    'chrome_browser': {
        'name': 'Google Chrome Browser',
        'category': 'browser',
        'image_size': '1792x1024',
        'design_language': 'Web Standards (host OS agnostic)',
        'action_space': 'web',
        'ui_framework': {
            'chrome_ui': 'tab bar, address bar, bookmarks bar',
            'content_area': 'web page below browser chrome',
            'font': 'system default',
        },
        'prompt_prefix': 'A screenshot of a Google Chrome browser window showing a web page.',
    },
    'ubuntu2404': {
        'name': 'Ubuntu 24.04 (GNOME)',
        'category': 'desktop',
        'image_size': '1792x1024',
        'design_language': 'GNOME Adwaita / libadwaita',
        'action_space': 'pc',
        'ui_framework': {
            'top_bar': 'Activities button, clock center, system tray right',
            'dock': 'left side (Ubuntu Dock)',
            'window_controls': 'top-right (close), top-left (none by default)',
            'font': 'Ubuntu / Cantarell',
            'corner_radius': '12px rounded',
        },
        'prompt_prefix': 'A screenshot of an Ubuntu 24.04 GNOME desktop.',
    },
}

ACTION_SPACES = {
    'pc': {
        'actions': [
            {'action': 'click', 'element': 'target element'},
            {'action': 'double_click', 'element': 'target element'},
            {'action': 'right_click', 'element': 'target element'},
            {'action': 'hover', 'element': 'target element'},
            {'action': 'drag', 'from_element': 'source element', 'to_element': 'target element'},
            {'action': 'type_text', 'text': 'content'},
            {'action': 'key_press', 'key': 'Enter'},  # single key: Enter / Escape / Tab / Delete / ArrowDown ...
            {'action': 'scroll', 'value': 'down'},     # value (direction): 'down' | 'up'
            {'action': 'hotkey', 'keys': ['ctrl', 'a']},  # combo, pressed in order & released reverse, e.g. ['ctrl','s'], ['ctrl','shift','n'], ['alt','tab']
            {'action': 'wait'},
            {'action': 'answer', 'status': 'DONE | FAIL', 'text': 'content'},  # DONE = task completed & reporting result; FAIL = task cannot be done (refusal/impossible)
        ],
    },
    'mobile': {
        'actions': [
            {'action': 'tap', 'element': 'target element'},
            {'action': 'long_press', 'element': 'target element'},
            {'action': 'swipe_up'},
            {'action': 'swipe_down'},
            {'action': 'swipe_left'},
            {'action': 'swipe_right'},
            {'action': 'type_text', 'text': 'content'},
            {'action': 'press_back'},
            {'action': 'press_home'},
            {'action': 'wait'},
            {'action': 'answer', 'status': 'DONE | FAIL', 'text': 'content'},  # DONE = task completed & reporting result; FAIL = task cannot be done (refusal/impossible)
        ],
    },

    # Browser-only: same element-based action vocabulary as the pc desktop space
    # (operations stay inside the Chrome window — no OS-level Alt+Tab). Ctrl+L
    # focuses the address bar; Enter is a key_press; answer ends the task.
    'web': {
        'actions': [
            {'action': 'click', 'element': 'target web or browser element'},
            {'action': 'double_click', 'element': 'target text or editable element'},
            {'action': 'right_click', 'element': 'target web element'},
            {'action': 'hover', 'element': 'target menu, tooltip, or card'},
            {'action': 'drag', 'from_element': 'source web element', 'to_element': 'target web element'},
            {'action': 'type_text', 'text': 'content'},
            {'action': 'key_press', 'key': 'Enter'},  # single key: Enter / Escape / Tab / Delete ...
            {'action': 'scroll', 'value': 'down'},     # value (direction): 'down' | 'up'
            {'action': 'hotkey', 'keys': ['ctrl', 'l']},  # Ctrl+L focus address bar; also ['ctrl','a'], ['ctrl','f']
            {'action': 'wait'},
            {'action': 'answer', 'status': 'DONE | FAIL', 'text': 'content'},  # DONE = task completed & reporting result; FAIL = task cannot be done (refusal/impossible)
        ],
    },
}


# Actions that point at a concrete on-screen target and therefore must be drawn
# with a red bounding box in the generated step image. All other actions
# (type_text, key_press, scroll, hotkey, swipe_*, press_*, wait, answer) render
# the resulting UI change WITHOUT any box.
#   - drag is special: it has TWO targets (source + destination) → two boxes.
BBOX_ACTIONS = {
    'click', 'double_click', 'right_click', 'hover', 'drag',  # pc / web
    'tap', 'long_press',                                      # mobile
}
DRAG_ACTIONS = {'drag'}  # require two boxes (from_element + to_element)


# === OS dispatch helpers ===
# Single entry point for category/ecosystem branching so callers never hardcode
# os_key literals (e.g. == 'ios'). Adding a new OS only needs the registry row.

def is_mobile(os_key):
    """True for phone OSes (Android / iOS)."""
    return OS_REGISTRY[os_key]['category'] == 'mobile'


def is_apple_mobile(os_key):
    """True for the Apple phone ecosystem (iOS), version-independent."""
    return is_mobile(os_key) and OS_REGISTRY[os_key].get('ecosystem') == 'apple'


def is_browser(os_key):
    """True for pure-web browser OSes (Chrome). These render an integral-screen
    browser (tab bar + address bar + active web page), not a desktop window."""
    return OS_REGISTRY[os_key]['category'] == 'browser'


def is_desktop(os_key):
    """True for windowed desktop OSes (Windows / macOS / Ubuntu)."""
    return OS_REGISTRY[os_key]['category'] == 'desktop'


def is_windows(os_key):
    """True for the Windows desktop, version-independent."""
    return os_key == 'windows11'


def is_macos(os_key):
    """True for the macOS desktop, version-independent."""
    return os_key == 'macos'


def is_linux_desktop(os_key):
    """True for the Ubuntu / GNOME desktop, version-independent."""
    return os_key == 'ubuntu2404'


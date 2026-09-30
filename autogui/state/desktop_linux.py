# -*- coding: utf-8 -*-
"""Ubuntu 24.04 (GNOME) desktop: window app pool + left-dock inventory.

The Linux desktop is kept separate from the Windows/macOS pools in
``desktop_pc.py`` because GNOME has its own launcher model: a left-side dock of
pinned favorites plus running-app indicator dots, distinct from the Windows
taskbar / macOS dock. The shared window sampler ``sample_windows`` lives in
``environment.py`` and serves this OS via the merged pool assembled there.
"""

import random

from autogui.state.web import WEB_PAGE_CONTENTS

# Window app pool for the GNOME desktop. Each app carries content templates
# describing the view it shows (parallel to desktop_pc.py's pools).
UBUNTU_APP_POOL = [
        ('Files',            ['a folder showing a large grid of image thumbnails with the Recent/Starred/Home sidebar',
                             'the Downloads folder in list view full of PDF and tar.gz files with a path bar',
                             'a folder with a right-click context menu open over the file list',
                             'the Other Locations view listing mounted drives and connected servers',
                             'the Home folder in grid view with bookmarked places in the left sidebar']),
        ('Firefox',          WEB_PAGE_CONTENTS),
        ('Google Chrome',    WEB_PAGE_CONTENTS),
        ('GNOME Terminal',   ['an apt install command with a [Y/n] confirmation prompt and scrolling package list',
                             'git status output and build logs on a dark background with a blinking prompt',
                             'htop showing a process list with per-core CPU and memory bars',
                             'an ls -la listing with file permissions, owners and sizes',
                             'an activated Python venv running a training script with timestamped log lines']),
        ('Text Editor',      ['a Python file with syntax highlighting and line numbers in the Adwaita dark theme',
                             'a Markdown README open with a clean light Adwaita header bar',
                             'a .conf configuration file with the find-and-replace bar open']),
        ('Settings',         ['the Appearance panel with light/dark style toggles and accent-color dots',
                             'the Wi-Fi panel listing available networks with signal icons',
                             'the Displays panel with resolution and fractional-scaling options',
                             'the Users panel showing an account with an avatar and Administrator role',
                             'the Power panel with screen-blank and automatic-suspend dropdowns']),
        ('Software',         ["the Editor's Picks banner with a grid of featured app tiles",
                             'an app detail page with screenshots, a description and a green Install button',
                             'the Updates tab listing available package updates with sizes']),
        ('System Monitor',   ['the Processes tab listing running processes with %CPU and memory columns',
                             'the Resources tab with CPU, memory and network history line graphs']),
        ('LibreOffice Writer', ['a multi-page document with the toolbar, a heading and body paragraphs',
                             'a Find & Replace dialog open over body text',
                             'a Save As dialog listing ODF and DOCX formats over the document']),
        ('LibreOffice Calc', ['a spreadsheet with a table of numbers and a bar chart',
                             'a Format Cells dialog open over a populated data sheet']),
        ('LibreOffice Impress', ['a slide editor with the slide-thumbnail panel and a layouts sidebar']),
        ('GIMP',             ['a photo on the canvas in single-window mode with the toolbox and a Layers panel',
                             'an image with the Colors menu open and a floating Channels dialog']),
        ('Inkscape',         ['a vector canvas with the toolbox, a selected shape and the Fill & Stroke dialog']),
        ('Document Viewer',  ['an academic paper PDF page with a page-thumbnail sidebar']),
        ('Image Viewer',     ['a photo displayed with zoom controls and an image-properties side panel']),
        ('Videos',           ['a video playing with a progress bar and a dark GNOME header bar']),
        ('Rhythmbox',        ['a music library with an album track list and playback controls']),
        ('Disks',            ['a disk partition map with volume info and a Format Partition option']),
        ('Calculator',       ['the Advanced mode with a computed expression and result']),
        ('Calendar',         ['a month view with a few colored events']),
        ('Maps',             ['a city street map with a search result pin and a place info card']),
        ('Visual Studio Code', ['a Python project with the explorer sidebar open and an integrated terminal',
                             'a README markdown file alongside its live rendered preview pane',
                             'multiple Python files split across columns with an outline panel']),
        ('Blender',          ['a dark 3D viewport with a grid floor and the default cube with a transform gizmo',
                             'a textured model with the shader-node material editor and properties tabs']),
        ('Thunderbird',      ['the inbox with a message list and a reading pane showing an email',
                             'the account settings dialog open on the signature text editor',
                             'a folder pane with local folders and a message-filter rules dialog',
                             'a compose window with To/Subject fields and a message body',
                             'the inbox with a right-click context menu over a message']),
        ('VLC',              ['a video playing with the bottom playback control bar and timeline',
                             'the Convert/Save dialog with a codec profile dropdown',
                             'the Preferences window on the interface settings pane',
                             'the playlist view with a queue of media files']),
]


# Favorite launcher entries are sampled after windows so running indicators
# agree with the applications visible in the generated scene.
# Real Ubuntu 24.04 default favorite-apps (org.gnome.shell favorite-apps),
# mapped to our window-pool names. Files / Firefox are treated as near-always
# pinned (kept first when trimming). Yelp/installer aren't in the window pool.
DEFAULT_DOCK_FAVORITES = [
    'Files', 'Firefox', 'Thunderbird', 'Rhythmbox',
    'LibreOffice Writer', 'Software', 'Settings', 'Calculator',
]

# Persona-typical extra pins, keyed by ubuntu2404 schema's user_persona options.
PERSONA_DOCK_EXTRAS = {
    'developer': ['Visual Studio Code', 'GNOME Terminal', 'System Monitor'],
    'sysadmin':  ['GNOME Terminal', 'System Monitor', 'Disks', 'Settings'],
    'student':   ['LibreOffice Calc', 'LibreOffice Impress', 'Calculator', 'Calendar'],
    'casual':    ['VLC', 'Rhythmbox', 'Calculator', 'Calendar', 'Maps'],
}

# Target pinned-icon count per dock_size (±1 jitter applied at sample time).
_DOCK_SIZE_TARGET = {'minimal': 6, 'default': 10, 'rich': 14}


def sample_dock(os_key, env_state, rng=None):
    """Build the Ubuntu GNOME left dock: pinned favorites + running indicators.

    Only meaningful for ubuntu2404 when logged in; returns None otherwise (other
    OS / lock states carry no 'dock' field, so downstream rendering is a no-op).

    dock content has two orthogonal sources:
      - pinned : favorites shown whether running or not. Anchored to the real
                 Ubuntu default set (Files/Firefox near-always) plus a few
                 persona-typical pins. Size governed by env_state['dock_size'].
      - running: apps with an open window (from env_state['windows']). These get
                 a running-indicator dot. running apps already pinned are flagged
                 running=True in place; running-but-not-pinned are appended after
                 favorites (GNOME behavior).

    Call AFTER sample_windows so the running set is known. Returns a dict:
      {position:'left', size, pinned:[{app,running}], running_not_pinned:[app]}.
    """
    if os_key != 'ubuntu2404' or env_state.get('login_state') != 'logged_in':
        return None
    if rng is None:
        rng = random.Random()

    size = env_state.get('dock_size', 'default')
    target = _DOCK_SIZE_TARGET.get(size, 10) + rng.choice([-1, 0, 1])

    # pinned: always Files+Firefox, then rest of defaults, then persona extras.
    pinned, seen = [], set()
    for app in ['Files', 'Firefox']:
        if app not in seen:
            pinned.append(app); seen.add(app)

    rest_defaults = [a for a in DEFAULT_DOCK_FAVORITES if a not in seen]
    rng.shuffle(rest_defaults)
    persona_extras = list(PERSONA_DOCK_EXTRAS.get(env_state.get('user_persona'), []))
    rng.shuffle(persona_extras)
    n_persona = min(len(persona_extras), rng.randint(1, 3))
    candidates = rest_defaults + persona_extras[:n_persona]
    for app in candidates:
        if len(pinned) >= target:
            break
        if app not in seen:
            pinned.append(app); seen.add(app)

    # running: from open windows.
    running = []
    for w in env_state.get('windows') or []:
        if w['app'] not in running:
            running.append(w['app'])
    running_set = set(running)

    pinned_entries = [{'app': a, 'running': a in running_set} for a in pinned]
    running_not_pinned = [a for a in running if a not in seen]

    return {
        'position': 'left',
        'size': size,
        'pinned': pinned_entries,
        'running_not_pinned': running_not_pinned,
    }

# -*- coding: utf-8 -*-
"""Windows 11 + macOS desktop app pools.

The two traditional-PC desktops keep separate app pools but share one
window-sampling model. Platform is dispatched via ``registry.is_windows`` /
``is_macos`` (``pc_app_pool``) — the desktop analogue of how ``mobile.py``
splits iOS vs Android. The Ubuntu/GNOME desktop lives in ``desktop_linux.py``;
the shared sampler ``sample_windows`` lives in ``environment.py`` and serves
every desktop OS via the merged pool assembled there.

Application views describe common editing and navigation functions. Browser
windows draw their page from the shared website catalog.
"""

from autogui.state.web import WEB_PAGE_CONTENTS

# Each app carries a few "content templates" describing what view it shows, so a
# window gets a concrete description instead of a vague "app open" line.
WINDOWS11_APP_POOL = [
        ('Microsoft OneNote', ['a notebook organized into sections with a note page open for editing',
                             'a note page containing a short checklist and a pasted illustration']),
        ('Google Chrome',    WEB_PAGE_CONTENTS),
        ('Microsoft Edge',   WEB_PAGE_CONTENTS,),
        ('File Explorer',    ['a folder with files arranged in a details list and a navigation sidebar',
                             'a folder containing a mix of documents and images with one item selected']),
        ('Visual Studio Code', ['a source file open beside a project file tree',
                             'an editor with an integrated terminal and a search panel']),
        ('Microsoft Word',   ['an editable document with paragraphs and a small table',
                             'a document with a heading selected and formatting controls available']),
        ('Microsoft Excel',  ['a worksheet containing a small budget table with labeled columns',
                             'a worksheet with a selected range and a chart beside the data']),
        ('Microsoft PowerPoint', ['a presentation with several slide thumbnails and an editable title slide',
                             'a content slide with a text box and an inserted image']),
        ('Microsoft Outlook', ['a mail inbox with a message list and a reading pane',
                             'a draft email with recipient, subject, and message fields']),
        ('Windows Settings', ['the system settings window with a category sidebar and display options',
                             'the personalization page showing the current theme and background options']),
        ('Windows Terminal', ['a terminal tab showing a directory listing and a shell prompt',
                             'two terminal panes with recent command output']),
        ('Microsoft Visio',  ['a diagram canvas with connected process shapes and a shapes sidebar',
                             'a flowchart with a selected connector and editable labels']),
        ('Autodesk AutoCAD', ['a drawing workspace with simple lines, dimensions, and a command area',
                             'a two-dimensional floor-plan sketch with layers and drawing tools']),
        ('Autodesk Inventor', ['a part-design workspace showing a simple solid and its feature tree',
                             'a sketch with constrained geometry and a dimension selected']),
        ('SolidWorks',       ['a part model displayed beside a feature tree',
                             'a sketch with lines and circles ready for dimensioning']),
        ('Unreal Engine',    ['a level editor with a viewport, an object list, and an asset browser',
                             'a selected scene object with its properties available for editing']),
        ('Blender',          ['a three-dimensional scene with a selected mesh and its transform controls',
                             'a workspace showing a mesh viewport beside an object-properties panel']),
        ('Adobe Photoshop',  ['an image canvas with several editable layers and the tools panel',
                             'an image selection with adjustment controls and a layers panel']),
        ('Adobe Illustrator', ['an artboard with vector shapes and editable text',
                             'a selected vector object with fill, stroke, and alignment controls']),
        ('Adobe Premiere Pro', ['a video sequence with several clips on a timeline and a preview monitor',
                             'an editing workspace with a media bin and a clip selected on the timeline']),
        ('Stata',            ['a statistical analysis workspace with a command field and results output',
                             'a data editor showing variable columns and observations']),
        ('EViews',           ['a workfile with several named data series',
                             'a spreadsheet view of a series with an associated chart window']),
        ('OriginLab Origin', ['a workbook containing numeric columns and a plotted curve',
                             'a graph with axes, a legend, and editable plot properties']),
        ('FL Studio',        ['a music project with a pattern editor and a playlist',
                             'a piano-roll view with notes and a mixer panel']),
        ('Vivado',           ['an FPGA project with a sources tree and a design workspace',
                             'a project view showing a constraints file and build messages']),
        ('Intel Quartus Prime', ['an FPGA project with design files and compilation tools',
                             'a source editor with the project navigator and status messages']),
        ('VLC media player', ['a video player with a playback timeline and audio controls',
                             'a playlist window listing several local media files']),
        ('Spotify',          ['a music-library page with playlists and playback controls',
                             'a playlist page with a track list and a search field']),
        # Desktop clients of catalog sites (also available as standalone windows,
        # not only as pages inside a browser).
        ('Slack',            ['a workspace with a channel sidebar and a conversation pane',
                             'a channel with recent messages and an empty message composer']),
        ('Zoom',             ['a meeting window with participant tiles and meeting controls',
                             'the application settings window showing audio and video options']),
        ('Microsoft Teams',  ['a chat workspace with a conversation list and message pane',
                             'a calendar page showing scheduled events and meeting controls']),
        ('Signal',           ['a messaging window with a conversation list and an open chat',
                             'an open conversation with a text composer and attachment controls']),
        # --- WAA-coverage built-ins (File Explorer/Edge/Chrome/VSCode/Settings/VLC already above) ---
        ('Notepad',          ['a plain-text document open with a blinking insertion cursor',
                             'a short text file with the find dialog open']),
        ('Microsoft Paint',  ['a drawing canvas with simple shapes and the color palette',
                             'an image open with a selected region and crop controls']),
        ('Calculator',       ['a calculator showing an arithmetic expression and its result',
                             'a calculator with its calculation history visible']),
        ('Clock',            ['a clock application showing a list of alarms',
                             'a timer page with a duration ready to be edited']),
        # --- LibreOffice suite (cross-platform; also installable on Windows).
        # PowerPoint/Impress, Excel/Calc, Word/Writer never co-occur in one seed —
        # see APP_EXCLUSIVE_GROUPS in environment.py. ---
        ('LibreOffice Calc', ['a spreadsheet with a small table, column headings, and sheet tabs',
                             'a worksheet with selected cells and a chart next to the table']),
        ('LibreOffice Writer', ['a document with headings, body text, and a small table',
                             'a text document with a paragraph selected for formatting']),
        ('LibreOffice Impress', ['a presentation editor showing slide thumbnails and a content slide',
                             'an editable slide with text and geometric shapes']),
        # --- High-frequency Windows system & utility apps ---
        ('Snipping Tool',    ['a captured image open with crop and annotation tools',
                             'the capture controls ready for a rectangular screen selection']),
        ('Sticky Notes',     ['several short notes arranged as separate desktop cards',
                             'an editable note containing a reminder checklist']),
        ('Photos',           ['an image library arranged as a thumbnail grid',
                             'a single photo displayed with basic editing controls']),
        ('Task Manager',     ['a process list with CPU and memory usage columns',
                             'a performance page with resource-usage graphs']),
        ('Microsoft PowerToys', ['a settings window listing utility modules and their switches',
                             'a keyboard-remapping configuration page with editable mappings']),
        ('7-Zip',            ['a file-manager view of an archive and its contents',
                             'an archive-creation dialog with format and compression settings']),
]

MACOS_APP_POOL = [
        ('Android Studio',   ['an Android project with source files and a code editor',
                             'a layout editing workspace with a device preview and component tree']),
        ('Google Chrome',    WEB_PAGE_CONTENTS),
        ('Safari',           WEB_PAGE_CONTENTS,),
        ('Finder',           ['a folder displayed in columns with a file-preview area',
                             'a directory containing documents and images with a selected item']),
        ('System Settings',  ['the system settings window with categories in the sidebar',
                             'an appearance page showing theme and accent options']),
        ('Terminal',         ['a terminal window showing shell commands and a prompt',
                             'a terminal tab displaying a short directory listing']),
        ('Visual Studio Code', ['a source file open beside a project file tree',
                             'an editor with an integrated terminal and a search panel']),
        ('PyCharm',          ['a Python project with a source editor and project tree',
                             'an editor with a run-output panel and a selected function']),
        ('DaVinci Resolve',  ['a video-editing workspace with a media pool and timeline',
                             'an editing page with a preview monitor and several arranged clips']),
        ('Final Cut Pro',    ['a video project with a clip browser, viewer, and timeline',
                             'an editable timeline with a clip selected for trimming']),
        ('VMware Fusion',    ['a virtual-machine library with one machine selected',
                             'a virtual-machine configuration window with hardware settings']),
        ('Microsoft Word',   ['an editable document with paragraphs and a small table',
                             'a document with a heading selected and formatting controls available']),
        ('Microsoft Excel',  ['a worksheet containing a small budget table with labeled columns',
                             'a worksheet with a selected range and a chart beside the data']),
        ('MATLAB',           ['a workspace with a script editor and command window',
                             'a numeric array in the workspace and a plotted figure']),
        ('Zotero',           ['a reference library with collections and item metadata',
                             'a selected reference with title, creator, and publication fields']),
        ('Preview',          ['a PDF document with page thumbnails and navigation controls',
                             'an image open with markup tools available']),
        ('Mail',             ['a mail inbox with folders, messages, and a reading pane',
                             'an email composition window with subject and message fields']),
        ('Apple TV',         ['a media library with titles arranged in rows',
                             'a title detail page with playback options']),
        ('Apple Maps',       ['a map with a search field and a place-information panel',
                             'a route-planning view with origin and destination fields']),
        ('Music',            ['a music library showing albums and playback controls',
                             'a playlist with tracks and editable ordering']),
        ('Notes',            ['a notes list with an editable note and formatting controls',
                             'a note containing a checklist and a small table']),
        # Apple iWork / developer / creativity apps. Templates written from real
        # reference screenshots — plain macOS look, not a
        # modernized/beautified interface.
        ('Numbers',          ['a spreadsheet document with a small table on a sheet canvas',
                             'a table with selected cells and an associated chart']),
        ('Keynote',          ['a slide deck with thumbnails and an editable title slide',
                             'a presentation slide with selected text and image objects']),
        ('Pages',            ['a text document with a heading, paragraphs, and a formatting sidebar',
                             'a page layout containing a text box and an image']),
        ('Xcode',            ['an application project with a source file open in the editor',
                             'a project navigator beside code and a debug-output area']),
        ('Automator',        ['a workflow editor showing available actions and an action sequence',
                             'a document workflow with configurable action fields']),
        ('Script Editor',    ['an editable automation script with a results pane',
                             'a script document with run controls and recent output']),
        ('QuickTime Player', ['a local video open with playback controls',
                             'a movie window with the trimming controls visible']),
        # Desktop clients of catalog sites (also available as standalone windows,
        # not only as pages inside a browser).
        ('Slack',            ['a workspace with a channel sidebar and a conversation pane',
                             'a channel with recent messages and an empty message composer']),
        ('Zoom',             ['a meeting window with participant tiles and meeting controls',
                             'the application settings window showing audio and video options']),
        ('Microsoft Teams',  ['a chat workspace with a conversation list and message pane',
                             'a calendar page showing scheduled events and meeting controls']),
        ('Signal',           ['a messaging window with a conversation list and an open chat',
                             'an open conversation with a text composer and attachment controls']),
        ('Spotify',          ['a music-library page with playlists and playback controls',
                             'a playlist page with a track list and a search field']),
]


def pc_app_pool(os_key):
    """Return the window app pool for a PC desktop OS (Windows / macOS).

    Mirrors the iOS/Android split in ``mobile.py``: callers pass an os_key and
    the right platform pool comes back. Returns None for non-PC desktops.
    """
    from autogui.state.registry import is_windows, is_macos
    if is_windows(os_key):
        return WINDOWS11_APP_POOL
    if is_macos(os_key):
        return MACOS_APP_POOL
    return None

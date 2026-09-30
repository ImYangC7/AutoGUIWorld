# -*- coding: utf-8 -*-
"""Per-OS task domain definitions.

Each OS has its own typical apps and interaction scenarios. This shapes
what tasks can plausibly happen on that platform.

Used by autogui.tasks.generator to guide scene-conditioned task generation.
"""

OS_TASK_DOMAINS = {
    'windows11': {
        'description': (
            'Windows 11 desktop environment, mainly mouse + keyboard interaction. Users switch between '
            'the desktop, taskbar, File Explorer, and Start menu, using various productivity apps, '
            'browsers, and media apps. Supports desktop-level operations such as window dragging, '
            'side-by-side multi-window, virtual desktops, and Snap Layout.'
        ),
        'common_apps': [
            'File Explorer', 'Microsoft Edge', 'Microsoft Word', 'Microsoft Excel',
            'PowerPoint', 'Outlook', 'OneNote', 'Teams', 'Notepad', 'Calculator',
            'Settings', 'Control Panel', 'Task Manager', 'Snipping Tool',
            'Windows Terminal', 'PowerShell', 'Visual Studio Code', 'Paint',
            'Photos', 'Media Player', 'Microsoft Store', 'Sticky Notes',
            'Clock', 'LibreOffice Calc', 'LibreOffice Writer', 'LibreOffice Impress',
            'Microsoft PowerToys', '7-Zip',
        ],
        'common_scenarios': [
            'file management (copy/move/rename/zip)',
            'document editing in Office',
            'system settings adjustment',
            'window arrangement and multitasking',
            'screenshot and image annotation',
            'application installation/uninstallation',
            'task scheduling',
            'network and printer setup',
        ],
        # 2-level feature taxonomy: category -> leaf feature points (coverage axis)
        'feature_tree': {
            'File Explorer': ['create/rename folder', 'copy & paste files', 'compress to ZIP', 'change view mode (details/large icons)',
                              'sort & group', 'right-click properties', 'pin to Quick Access'],
            'Office editing': ['text formatting (font/size/bold/color)', 'insert table/image', 'paragraph alignment & bullets',
                               'find & replace', 'save as a specific format', 'insert header & footer'],
            'LibreOffice': ['Calc: fill/format a cell range & autosum', 'Calc: sort or filter a table', 'Calc: insert a chart from data',
                            'Writer: change font / apply a paragraph style', 'Writer: find & replace text', 'Impress: add a slide & edit its layout'],
            'Window management': ['snap window to half screen', 'minimize/maximize', 'side-by-side windows', 'switch virtual desktop', 'Alt+Tab switching'],
            'System settings': ['toggle light/dark theme', 'adjust display scaling/resolution', 'Bluetooth/WiFi toggle', 'change wallpaper', 'adjust volume/brightness'],
            'Taskbar & Start': ['search and open an app', 'pin app to taskbar', 'open notification center', 'check the system tray'],
            'Utilities': ['screenshot and annotate (Snipping Tool)', 'calculator arithmetic', 'calculator date difference', 'unit conversion', 'sticky notes', 'end a process in Task Manager'],
            'Clock': ['start a countdown timer', 'set or toggle an alarm', 'add a world-clock city', 'start a Focus Session'],
            'Media & Photos': ['play/pause a video in VLC', 'take a video snapshot', 'view & crop a photo in Photos', 'rotate an image'],
            'Power tools': ['7-Zip: create or extract an archive', 'PowerToys: set up a FancyZones layout', 'PowerToys: batch-rename files', 'PowerToys Run: launch an app'],
        },
        'complexity_range': (3, 20),
    },
    'macos': {
        'description': (
            'macOS Sequoia desktop environment, trackpad gestures + mouse & keyboard. Users use the Dock, '
            'Spotlight, Mission Control, Finder, etc. Emphasis on the global menu bar, keyboard shortcuts, '
            'Quick Look previews, and deep integration with the Apple ecosystem such as iCloud.'
        ),
        'common_apps': [
            'Finder', 'Safari', 'Mail', 'Messages', 'FaceTime', 'Notes', 'Reminders',
            'Calendar', 'Photos', 'Music', 'TV', 'Podcasts', 'App Store',
            'System Settings', 'Activity Monitor', 'Terminal', 'TextEdit',
            'Preview', 'QuickTime Player', 'Pages', 'Numbers', 'Keynote',
            'Xcode', 'Time Machine', 'Spotlight Search',
        ],
        'common_scenarios': [
            'Spotlight search and quick app launch',
            'Finder file management and tagging',
            'Mission Control and Spaces switching',
            'Safari browsing and bookmark management',
            'iMessage / FaceTime communication',
            'Photos library organization',
            'System Settings adjustment',
            'Terminal command execution',
        ],
        'feature_tree': {
            'Finder': ['create/rename folder', 'apply Tag labels', 'switch icon/list/column view', 'Quick Look preview',
                       'move files into a folder', 'sort & group'],
            'Menu bar & global menus': ['use the top app menu', 'click menu bar icons (WiFi/battery/Control Center)', 'run a command via a menu item'],
            'Window & Spaces': ['snap/resize windows', 'enter Mission Control', 'switch Spaces', 'full screen & Split View'],
            'System Settings': ['toggle light/dark appearance', 'change wallpaper', 'adjust display resolution', 'sound output settings', 'manage Bluetooth devices'],
            'App editing (Pages/Numbers/Notes)': ['text formatting', 'insert table/image', 'create a note & checklist', 'save/export'],
            'Dock & Spotlight': ['open an app via Spotlight search', 'pin app to the Dock', 'launch via Launchpad'],
        },
        'complexity_range': (3, 8),
    },
    'ubuntu2404': {
        'description': (
            'Ubuntu 24.04 LTS GNOME desktop environment, an open-source Linux system. Users operate via '
            'Activities, the Ubuntu Dock, and Files (Nautilus), and frequently use the Terminal command line. '
            'Emphasis on system settings, package management (apt/Snap), and the development toolchain.'
        ),
        'common_apps': [
            'Files (Nautilus)', 'Firefox', 'GNOME Terminal', 'Text Editor (gedit)',
            'Settings', 'Software (App Center)', 'System Monitor', 'Image Viewer',
            'Video Player', 'Rhythmbox', 'LibreOffice Writer', 'LibreOffice Calc',
            'GIMP', 'Inkscape', 'Disks (gnome-disks)', 'Calculator',
            'Screenshot tool', 'Settings (Control Center)',
        ],
        'common_scenarios': [
            'apt/Snap package installation via terminal',
            'file permission and ownership changes',
            'GNOME Settings (display, network, users)',
            'system monitoring and process management',
            'shell scripting and automation',
            'workspace switching',
            'VPN and SSH configuration',
        ],
        'feature_tree': {
            'Files (Nautilus)': ['create/rename folder', 'copy & paste files', 'compress to ZIP',
                                 'switch grid/list view', 'show hidden files (Ctrl+H)',
                                 'open current folder in terminal', 'bookmark a location'],
            'Terminal & shell': ['install a package via apt/snap', 'change file permissions (chmod/chown)',
                                 'navigate with cd/ls', 'run a shell script', 'edit a file with nano/vim',
                                 'pipe & grep command output'],
            'GNOME Settings': ['toggle dark style', 'change wallpaper', 'adjust display resolution & scaling',
                               'configure Wi-Fi / network', 'manage users', 'set default applications',
                               'customize keyboard shortcuts'],
            'Window & workspaces': ['tile window to left/right half (Super+arrow)', 'maximize/minimize',
                                    'switch workspace', 'search in Activities overview', 'Alt+Tab switching'],
            'App editing (LibreOffice / Text Editor)': ['text formatting (font/size/bold)', 'insert table/image',
                                    'find & replace', 'save as a specific format (.odt/.docx)',
                                    'syntax highlighting in the code editor'],
            'Top bar & system': ['open the system menu (power/volume/network)', 'check calendar & notifications',
                                 'take a screenshot', 'adjust volume/brightness', 'open Activities'],
            'Dock & launcher': ['pin an app to the dock (Add to Favorites)', 'remove an app from favorites',
                                'launch an app from the dock', 'open a running app from its dock icon',
                                'reorder dock icons'],
        },
        'complexity_range': (3, 8),
    },
    'chrome_browser': {
        'description': (
            'Google Chrome browser environment, spanning mainstream websites (e-commerce, social, search, '
            'productivity tools, video streaming). Users perform search, navigation, form filling, '
            'login/registration, and multi-tab management. No OS-level GUI is involved; operations happen only '
            'within the browser chrome (tab bar / address bar / bookmarks bar) and the web page content.'
        ),
        'common_apps': [
            'Google Search', 'Gmail', 'Google Drive', 'Google Docs', 'Google Sheets',
            'YouTube', 'Google Maps', 'Google Calendar', 'GitHub', 'Stack Overflow',
            'Amazon', 'Taobao', 'Twitter/X', 'Facebook', 'LinkedIn', 'Reddit',
            'Wikipedia', 'Notion', 'Figma', 'Trello', 'Bilibili', 'Zhihu',
        ],
        'common_scenarios': [
            'web search and result navigation',
            'online form filling (registration, checkout)',
            'email composition and management',
            'collaborative document editing',
            'shopping (search, add to cart, checkout)',
            'video streaming and playlist management',
            'social media posting and interaction',
            'GitHub repository operations (issue, PR, fork)',
            'multi-tab research and bookmarking',
        ],
        'complexity_range': (3, 7),
    },
    'android': {
        'description': (
            'Modern Android phone environment (Material You dynamic color), portrait '
            'touchscreen interaction. Users use various apps for social, '
            'payment, navigation, shopping, and photography. Emphasis on the notification center, control center '
            'pull-down, home screen widgets, app switching, and gesture navigation.'
        ),
        'common_apps': [
            'WeChat', 'WhatsApp', 'Telegram', 'Gmail', 'Chrome (mobile)',
            'YouTube', 'Maps', 'Camera', 'Photos', 'Settings',
            'Play Store', 'Calculator', 'Calendar', 'Clock', 'Files',
            'Alipay', 'Taobao', 'Meituan', 'Didi', 'Bilibili',
            'TikTok', 'Spotify', 'Notes', 'Phone (Dialer)', 'Contacts',
        ],
        'common_scenarios': [
            'messaging (send text/voice/photo)',
            'mobile payment via QR code scanning',
            'navigation and ride-hailing',
            'food delivery ordering',
            'photo capture and editing',
            'notification center pull-down operations',
            'app switching and task management',
            'system settings (WiFi, Bluetooth, brightness)',
            'social media posting (moments, story)',
            'phone call and contact management',
        ],
        'complexity_range': (3, 7),
    },
    'ios': {
        'description': (
            'Modern iPhone environment (translucent glass UI), portrait touchscreen + Dynamic Island + bottom home-indicator gestures. '
            'Users use Apple-ecosystem apps (iMessage, FaceTime, App Store) and third-party apps. '
            'Emphasis on the top-right pull-down Control Center, top-left pull-down Notification Center, '
            'swipe-down Spotlight search, and the swipe-up app switcher gesture.'
        ),
        'common_apps': [
            'iMessage', 'FaceTime', 'Mail', 'Safari', 'Photos', 'Camera',
            'Maps', 'Notes', 'Reminders', 'Calendar', 'Clock', 'Weather',
            'App Store', 'Settings', 'Phone', 'Contacts', 'Music', 'Podcasts',
            'TV', 'Wallet', 'Health', 'Fitness', 'Find My', 'Shortcuts',
            'WeChat', 'WhatsApp', 'Instagram', 'TikTok',
        ],
        'common_scenarios': [
            'iMessage / FaceTime communication',
            'Control Center swipe-down operations',
            'Spotlight search from home screen',
            'Camera and Photos editing/sharing',
            'App Store browsing and installation',
            'Settings adjustment (Focus mode, Privacy)',
            'Wallet payment (Apple Pay)',
            'Reminders and Calendar event creation',
            'Maps navigation and place search',
            'Shortcuts automation',
        ],
        'complexity_range': (3, 7),
    },
}

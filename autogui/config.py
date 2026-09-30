# -*- coding: utf-8 -*-
"""Optional local grounding settings. Model adapters are configured separately."""

import os


def _env(name, default):
    return os.environ.get(name, '').strip() or default


MAI_UI_URL = _env('AUTOGUI_MAI_UI_URL', 'http://localhost:8003/v1/chat/completions')
MAI_UI_MODEL = _env('AUTOGUI_MAI_UI_MODEL', 'MAI-UI-8B')
LOCATE_ANYTHING_URL = _env('AUTOGUI_LA_URL', 'http://localhost:8004')
LOCATE_ANYTHING_URLS = [
    url.strip() for url in _env('AUTOGUI_LA_URLS', LOCATE_ANYTHING_URL).split(',')
    if url.strip()
]

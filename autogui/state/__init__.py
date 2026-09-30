# -*- coding: utf-8 -*-
"""State package: OS metadata, action spaces, and per-OS environment sampling.

Public entry point. Submodules stay importable as before
(``from autogui.state.environment import X``), but the most common symbols are
also surfaced here so callers can do ``from autogui.state import OS_REGISTRY``.

  - registry.py      OS_REGISTRY, ACTION_SPACES, and is_* OS classifiers
  - environment.py   aggregation layer: schemas, samplers, state->text renderer
                     (itself re-exporting catalog / web / desktop_* / mobile)
  - aesthetics.py    visual-style sampling and style directives
"""

from autogui.state.registry import (
    OS_REGISTRY, ACTION_SPACES, BBOX_ACTIONS, DRAG_ACTIONS,
    is_mobile, is_apple_mobile, is_browser,
    is_desktop, is_windows, is_macos, is_linux_desktop,
)
from autogui.state.environment import (
    sample_environment_state, clean_state, sample_windows,
    state_to_descriptive_text, has_blocking_state,
)
from autogui.state.aesthetics import (
    sample_aesthetic, aesthetic_to_style_directive,
)

__all__ = [
    # registry
    'OS_REGISTRY', 'ACTION_SPACES', 'BBOX_ACTIONS', 'DRAG_ACTIONS',
    'is_mobile', 'is_apple_mobile', 'is_browser',
    'is_desktop', 'is_windows', 'is_macos', 'is_linux_desktop',
    # environment sampling + rendering
    'sample_environment_state', 'clean_state', 'sample_windows',
    'state_to_descriptive_text', 'has_blocking_state',
    # aesthetics
    'sample_aesthetic', 'aesthetic_to_style_directive',
]

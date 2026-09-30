# -*- coding: utf-8 -*-
"""Load a model adapter installed separately from the source distribution."""

import importlib
import os
from functools import lru_cache


class BackendError(RuntimeError):
    """A model operation failed without exposing implementation details."""


class BackendConfigurationError(BackendError):
    """The external adapter is missing or does not implement the contract."""


class TransientBackendError(BackendError):
    """Adapters raise this for failures that are safe to retry."""


@lru_cache(maxsize=None)
def _load(name):
    try:
        return importlib.import_module(name)
    except Exception:
        raise BackendConfigurationError('Could not load the configured model adapter') from None


def require_backend(*capabilities):
    name = os.environ.get('AUTOGUI_BACKEND', '').strip()
    if not name:
        raise BackendConfigurationError('Set AUTOGUI_BACKEND to an installed model adapter module')
    adapter = _load(name)
    for capability in capabilities:
        if not callable(getattr(adapter, capability, None)):
            raise BackendConfigurationError(f'Model adapter must implement {capability}()')
    return adapter


def invoke(capability, **kwargs):
    implementation = getattr(require_backend(capability), capability)
    try:
        return implementation(**kwargs)
    except TransientBackendError:
        raise TransientBackendError(f'{capability} temporarily unavailable') from None
    except Exception:
        raise BackendError(f'{capability} operation failed') from None


def usage_fields(result):
    """Keep numeric usage counters only; adapter diagnostics stay outside logs."""
    usage = result.get('usage') if isinstance(result, dict) else None
    if not isinstance(usage, dict):
        return {}
    return {name: value for name, value in usage.items()
            if name in ('prompt_tokens', 'completion_tokens', 'total_tokens')
            and isinstance(value, int) and not isinstance(value, bool) and value >= 0}

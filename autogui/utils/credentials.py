# -*- coding: utf-8 -*-
"""Mask task account fields before text planning, then restore them locally.

Task instructions may contain account fields needed by the generated actions.
Stable placeholders let the planner reason about the task without these values.
"""

import re

_CRED_KEYWORDS = r'(?:password|passwd|pwd|user(?:name)?|account|login|credential)'
_EMAIL = re.compile(r'[\w.\-+]+@[\w\-]+\.[\w.\-]+')
_QUOTED = re.compile(r'`([^`]+)`|"([^"]+)"|\'([^\']+)\'')


def _near_keyword(text, pos, window=50):
    return re.search(_CRED_KEYWORDS, text[max(0, pos - window):pos], re.I) is not None


def mask_credentials(text):
    """Return (masked_text, mapping placeholder->real_value).

    Masks every email address, plus any backtick/quote-delimited token that sits
    just after a credential keyword (password / user / account / login ...).
    Identical values reuse the same placeholder so the mapping round-trips.
    """
    mapping = {}
    counters = {'EMAIL': 0, 'CRED': 0}

    def placeholder(kind, value):
        for ph, v in mapping.items():
            if v == value:
                return ph
        counters[kind] += 1
        ph = f'<{kind}_{counters[kind]}>'
        mapping[ph] = value
        return ph

    text = _EMAIL.sub(lambda m: placeholder('EMAIL', m.group(0)), text)

    def quoted_sub(m):
        if not _near_keyword(text, m.start()):
            return m.group(0)
        value = next(g for g in m.groups() if g is not None)
        if value in mapping:  # already a placeholder (e.g. a masked email)
            return m.group(0)
        # Keep the surrounding delimiter; only the value inside becomes a
        # placeholder, so unmasking restores the original byte-for-byte.
        delim = m.group(0)[0]
        return f'{delim}{placeholder("CRED", value)}{delim}'

    text = _QUOTED.sub(quoted_sub, text)
    return text, mapping


def unmask_credentials(text, mapping):
    """Restore strings recursively after parsing model JSON, preserving escaping."""
    if isinstance(text, dict):
        return {key: unmask_credentials(value, mapping) for key, value in text.items()}
    if isinstance(text, list):
        return [unmask_credentials(value, mapping) for value in text]
    if not isinstance(text, str):
        return text
    for ph, value in mapping.items():
        text = text.replace(ph, value)
    return text

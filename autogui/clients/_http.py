# -*- coding: utf-8 -*-
"""Shared HTTP session factory for API clients.

All clients disable proxy env inheritance (`trust_env = False`) so requests go
directly to the configured endpoints regardless of ambient http(s)_proxy vars.
"""

import requests


def api_error(service, error):
    """Safe diagnostic for logs/meta: no URL, headers or upstream response body."""
    return f'{service} API request failed ({type(error).__name__})'


def check_status(response, service):
    """requests.raise_for_status includes private URLs in the exception text."""
    if 400 <= response.status_code < 600:
        raise requests.HTTPError(f'{service} API returned HTTP {response.status_code}')


def make_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session

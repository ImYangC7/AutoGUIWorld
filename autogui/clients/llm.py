# -*- coding: utf-8 -*-
"""Text and vision generation through a separately installed model adapter."""

import base64
import io
import os
import random
import time
from pathlib import Path
from PIL import Image

from autogui.clients.backend import invoke, usage_fields, BackendError, TransientBackendError
from autogui.utils.cost import get_logger as get_cost_logger
from autogui.utils.ratelimit import RateGate

_RATE_GATE = RateGate(float(os.environ.get('LLM_RATE_PER_MIN', '0')))


def generate_text(messages, *, purpose="llm_chat", max_retries=4, max_tokens=None):
    if max_retries < 1:
        raise ValueError('max_retries must be positive')
    for attempt in range(max_retries):
        _RATE_GATE.wait()
        try:
            result = invoke('chat', messages=messages, purpose=purpose, max_tokens=max_tokens)
        except TransientBackendError:
            if attempt + 1 == max_retries:
                raise
            time.sleep(min(30, 2 ** attempt) + random.uniform(0, 1))
            continue
        if not isinstance(result, dict) or not isinstance(result.get('text'), str):
            raise BackendError('chat must return a mapping with a text string')
        if not result['text'].strip():
            raise BackendError('chat returned empty text')
        get_cost_logger().record(purpose, 'external', {'usage': usage_fields(result)})
        return result['text']


def call_llm(system_prompt: str, user_prompt: str, max_retries: int = 8) -> str:
    return generate_text([
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt},
    ], purpose='llm_chat', max_retries=max_retries)


def _image_data_url(image_path: str | Path) -> str:
    with Image.open(image_path) as frame:
        buffer = io.BytesIO()
        frame.convert('RGB').save(buffer, format='PNG')
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def call_llm_vision(system_prompt: str, user_text: str,
                    image_items: list[tuple[str, str | Path]],
                    max_retries: int = 4, detail: str = 'high',
                    *, purpose: str = 'llm_vision', max_tokens: int | None = None) -> str:
    content = [{'type': 'text', 'text': user_text}]
    for label, image_path in image_items:
        content.append({'type': 'text', 'text': f'Image: {label}'})
        content.append({'type': 'image_url', 'image_url': {
            'url': _image_data_url(image_path), 'detail': detail,
        }})
    return generate_text([
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': content},
    ], purpose=purpose, max_retries=max_retries, max_tokens=max_tokens)

# -*- coding: utf-8 -*-
"""Image generation and editing through a separately installed model adapter."""

import os
import io
import re
from PIL import Image, UnidentifiedImageError
import random
import time
from pathlib import Path

from autogui.clients.backend import invoke, usage_fields, BackendError, TransientBackendError
from autogui.utils.cost import get_logger as get_cost_logger
from autogui.utils.ratelimit import RateGate
from autogui.utils.jsonio import atomic_write_bytes

_MAX_RETRIES = int(os.environ.get('IMAGE_MAX_RETRIES', '6'))
_RATE_GATE = RateGate(float(os.environ.get('IMAGE_RATE_PER_MIN', '20')))


def generate_image(prompt: str, image_bytes: bytes | None = None,
                   size: str = '1024x1024', quality: str = 'high') -> bytes:
    operation = 'edit' if image_bytes is not None else 'generate'
    if _MAX_RETRIES < 0:
        raise ValueError('IMAGE_MAX_RETRIES must be nonnegative')
    if not isinstance(size, str) or not re.fullmatch(r'[1-9]\d*x[1-9]\d*', size):
        raise ValueError('Image size must be positive WIDTHxHEIGHT')
    expected_size = tuple(map(int, size.split('x')))
    for attempt in range(_MAX_RETRIES + 1):
        _RATE_GATE.wait()
        try:
            result = invoke('image', prompt=prompt, operation=operation,
                            image_bytes=image_bytes, size=size, quality=quality)
        except TransientBackendError:
            if attempt == _MAX_RETRIES:
                raise
            time.sleep(min(60, 2 * (2 ** attempt)) + random.uniform(0, 1.5))
            continue
        if not isinstance(result, dict) or not isinstance(result.get('image'), bytes):
            raise BackendError('image must return a mapping with image bytes')
        if not result['image']:
            raise BackendError('image returned empty bytes')
        try:
            with Image.open(io.BytesIO(result['image'])) as frame:
                if frame.format != 'PNG' or frame.size != expected_size:
                    raise ValueError('Image must be PNG with the requested dimensions')
                frame.verify()
            with Image.open(io.BytesIO(result['image'])) as frame:
                frame.load()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
            raise BackendError('image returned invalid image bytes') from None
        get_cost_logger().record(f'image_{operation}', 'external', {'usage': usage_fields(result)})
        return result['image']
    raise ValueError('IMAGE_MAX_RETRIES must be nonnegative')


def edit_with_ref(edit_prompt: str, ref_image_path: str | Path, output_path: str | Path,
                  size: str = '1024x1024', quality: str = 'high') -> str | Path:
    with open(ref_image_path, 'rb') as stream:
        ref_bytes = stream.read()
    image_data = generate_image(edit_prompt, ref_bytes, size, quality)
    atomic_write_bytes(output_path, image_data)
    return output_path

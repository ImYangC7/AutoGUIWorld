# -*- coding: utf-8 -*-
"""JSON I/O helpers shared across the pipeline."""

import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path


def strip_json_fence(raw):
    """Strip a ```json ... ``` (or ``` ... ```) markdown fence, if present."""
    text = raw.strip()
    if '```' in text:
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    return text


@contextmanager
def _atomic_text_writer(path):
    """Replace the target only after the caller's writes and fsync succeed."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         dir=target.parent, prefix='.' + target.name + '.',
                                         delete=False) as stream:
            temporary = Path(stream.name)
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write_json(path, data):
    """Replace a JSON file only after serialization and fsync succeed."""
    with _atomic_text_writer(path) as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def atomic_write_bytes(path, data):
    """Write an image without exposing a partially written destination."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.' + target.name + '.', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def record_id_sort_key(record_id):
    """Sort numbered seed/trajectory IDs numerically, then other IDs by name."""
    try:
        return (0, int(record_id.split('_')[1]), record_id)
    except (IndexError, ValueError):
        return (1, 0, record_id)


def load_jsonl_report(path, id_field):
    """Load a report keyed by its seed or trajectory ID; return {} if absent."""
    target = Path(path)
    if not target.exists():
        return {}
    records = {}
    with target.open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                record = json.loads(line)
                records[record[id_field]] = record
    return records


def write_jsonl_report(path, records):
    """Atomically replace the full report with records ordered by ID."""
    with _atomic_text_writer(path) as stream:
        for record_id in sorted(records, key=record_id_sort_key):
            stream.write(json.dumps(records[record_id], ensure_ascii=False) + '\n')

# -*- coding: utf-8 -*-
"""Thread-safe numeric usage summaries for model calls."""

import os
import threading
from datetime import datetime
from pathlib import Path

from autogui import DATA_DIR
from autogui.clients.backend import usage_fields
from autogui.utils.jsonio import atomic_write_json
import math
import copy


_LOCK = threading.RLock()


class CostLogger:
    """Append-only cost log for the current run."""

    def __init__(self, log_path):
        self.path = Path(log_path)
        self._entries = []

    def record(self, source, model, response_json):
        """Record a single API call's cost.

        Args:
            source: 'llm_chat' / 'llm_vision' / 'image_gen' / 'image_edit'
            model: model identifier string
            response_json: parsed API response dict
        """
        entry = {
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'source': source,
            'model': model,
        }

        # Only recognized numeric fields may enter persistent logs.
        usage = usage_fields(response_json)
        if usage:
            entry['usage'] = usage
        cost_info = response_json.get('cost_info')
        if isinstance(cost_info, dict):
            cost = cost_info.get('cost')
            if isinstance(cost, (int, float)) and not isinstance(cost, bool) and math.isfinite(cost) and cost >= 0:
                entry['cost_info'] = {'cost': cost}

        # Fallback: if neither present, log a marker
        if 'cost_info' not in entry and 'usage' not in entry:
            entry['note'] = 'no cost data in response'

        with _LOCK:
            self._entries.append(entry)

    def flush(self):
        """Write accumulated entries (and summary) to disk."""
        with _LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)

            # Aggregate totals
            entries = copy.deepcopy(self._entries)
            total_calls = len(entries)
            total_cost = 0
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_total_tokens = 0
            per_source = {}

            for e in entries:
                src = e['source']
                per_source.setdefault(src, {'calls': 0, 'cost': 0, 'tokens': 0})
                per_source[src]['calls'] += 1

                ci = e.get('cost_info') or {}
                usage = e.get('usage') or {}

                cost = ci.get('cost', 0) or 0
                total_cost += cost
                per_source[src]['cost'] += cost

                pt = ci.get('prompt_tokens') or usage.get('prompt_tokens') or 0
                ct = ci.get('completion_tokens') or usage.get('completion_tokens') or 0
                tt = ci.get('total_tokens') or usage.get('total_tokens') or (pt + ct)

                total_prompt_tokens += pt
                total_completion_tokens += ct
                total_total_tokens += tt
                per_source[src]['tokens'] += tt

            summary = {
                'generated_at': datetime.now().isoformat(timespec='seconds'),
                'total_calls': total_calls,
                'total_cost_raw': total_cost,
                'total_cost_note': 'Cost units are defined by the external model adapter',
                'total_prompt_tokens': total_prompt_tokens,
                'total_completion_tokens': total_completion_tokens,
                'total_total_tokens': total_total_tokens,
                'per_source': per_source,
            }

            payload = {
                'summary': summary,
                'entries': entries,
            }

            atomic_write_json(self.path, payload)

    def print_summary(self):
        """Print a concise cost summary to stdout."""
        with _LOCK:
            entries = copy.deepcopy(self._entries)
        n = len(entries)
        if n == 0:
            print('💰 Cost: 无 API 调用记录')
            return

        per_source = {}
        total_cost = 0
        total_tokens = 0
        for e in entries:
            src = e['source']
            per_source.setdefault(src, {'calls': 0, 'cost': 0, 'tokens': 0})
            per_source[src]['calls'] += 1
            ci = e.get('cost_info') or {}
            usage = e.get('usage') or {}
            cost = ci.get('cost', 0) or 0
            tokens = (ci.get('total_tokens') or usage.get('total_tokens') or 0)
            per_source[src]['cost'] += cost
            per_source[src]['tokens'] += tokens
            total_cost += cost
            total_tokens += tokens

        print(f'\n💰 API 成本汇总（{n} 次调用）')
        print(f'{"-"*60}')
        for src, stats in per_source.items():
            print(f'  {src:20s}  calls={stats["calls"]:3d}  tokens={stats["tokens"]:6d}  cost_raw={stats["cost"]}')
        print(f'  {"-"*55}')
        print(f'  {"TOTAL":20s}  calls={n:3d}  tokens={total_tokens:6d}  cost_raw={total_cost}')
        print(f'{"-"*60}\n')


# Module-level singleton (one logger per process)
_GLOBAL_LOGGER = None


def get_logger(log_path=None):
    global _GLOBAL_LOGGER
    with _LOCK:
        if _GLOBAL_LOGGER is None:
            if log_path is None:
                log_path = os.path.join(DATA_DIR, '_cost_log.json')
            _GLOBAL_LOGGER = CostLogger(log_path)
    return _GLOBAL_LOGGER

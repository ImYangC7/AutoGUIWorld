# -*- coding: utf-8 -*-
"""Audit TASK <-> SEED relevance across all trajectories.

For each trajectory we send its INITIAL screenshot (obs_00.png = seed initial)
plus the task text + expected foreground app to a multimodal model, which judges
whether the screen provides the task's preconditions (right app + task-specific
content present). Flags generated tasks that do not match their saved seed.

Shares the model adapter and atomic report format with qc_seeds.py; reruns
skip already-judged trajectories.

Usage:
    python -m autogui.analysis.qc_task_seed                 # all trajectories
    python -m autogui.analysis.qc_task_seed --os ubuntu2404
    python -m autogui.analysis.qc_task_seed --traj-id traj_224 --force
    python -m autogui.analysis.qc_task_seed --workers 8

Outputs:
    - data/trajectories/_task_seed_report.jsonl  (full snapshot, one line/traj)
    - console summary: verdict histogram, and the mismatch/partial list.
"""

import os
import json
import argparse
import glob
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime


from autogui.storage.manager import TRAJ_DIR, load_seed
from autogui.state.registry import OS_REGISTRY
from autogui.prompts.task_seed_relevance import build_relevance_prompt, VERDICTS
from autogui.utils.jsonio import (
    load_jsonl_report, record_id_sort_key, strip_json_fence, write_jsonl_report,
)
from autogui.clients.llm import call_llm_vision
from autogui.clients.backend import require_backend, BackendConfigurationError
from PIL import Image

MODEL = 'external-qc'

REPORT_PATH = os.path.join(TRAJ_DIR, '_task_seed_report.jsonl')


def _normalize(result):
    if not isinstance(result, dict):
        raise ValueError('Task relevance QC requires an object')
    for field in ('app_ok', 'content_present'):
        if type(result.get(field)) is not bool:
            raise ValueError('Task relevance QC requires boolean fields')
    v = result.get('verdict')
    if v not in VERDICTS:
        raise ValueError('Unknown task relevance verdict')
    if v == 'match' and not (result['app_ok'] and result['content_present']):
        v = 'partial' if result['app_ok'] else 'mismatch'
    return {
        'verdict': v,
        'app_ok': bool(result.get('app_ok')),
        'content_present': bool(result.get('content_present')),
        'screenshot_shows': str(result.get('screenshot_shows', ''))[:120],
        'reason': str(result.get('reason', ''))[:300],
    }


def judge(img_path, task, target_app, max_retries=3):
    prompt = build_relevance_prompt(task, target_app)
    for attempt in range(max_retries):
        content = call_llm_vision(
            'Return the requested assessment as JSON.', prompt,
            [('initial screenshot', img_path)], max_retries=3,
            purpose='qc', max_tokens=2048,
        )
        try:
            return _normalize(json.loads(strip_json_fence(content)))
        except (TypeError, ValueError, AttributeError):
            if attempt + 1 == max_retries:
                raise RuntimeError('QC returned an invalid assessment') from None
    raise ValueError('max_retries must be positive')


def _collect_targets(os_key=None, traj_id=None):
    """Return [(traj_id, os_key, meta_path, obs00_path, task, fg)]."""
    targets = []
    pattern = os.path.join(TRAJ_DIR, os_key or '*', traj_id or 'traj_*', 'meta.json')
    for meta_path in glob.glob(pattern):
        td = os.path.dirname(meta_path)
        obs00 = os.path.join(td, 'obs_00.png')
        try:
            with open(meta_path, encoding='utf-8') as stream:
                m = json.load(stream)
            if not isinstance(m, dict):
                raise ValueError('Expected metadata object')
        except (OSError, ValueError):
            raise ValueError(f'Invalid trajectory metadata: {os.path.basename(td)}') from None
        task = m.get('task_description')
        if not isinstance(m.get('os_key'), str) or m['os_key'] not in OS_REGISTRY:
            raise ValueError(f'Invalid trajectory platform: {os.path.basename(td)}')
        if not isinstance(task, str) or not task.strip():
            raise ValueError(f'Missing trajectory task: {os.path.basename(td)}')
        fg = None
        try:
            seed = load_seed(m['seed_id'])
            fg = seed.get('global_state', {}).get('target_window')
        except (KeyError, OSError, ValueError):
            raise ValueError(f'Broken seed reference: {os.path.basename(td)}') from None
        targets.append((
            os.path.basename(td), m.get('os_key'), meta_path, obs00,
            task, fg,
        ))
    return targets


def main():
    ap = argparse.ArgumentParser(description='Audit task<->seed relevance per trajectory.')
    ap.add_argument('--os', dest='os_key', choices=list(OS_REGISTRY), help='only this OS subdir')
    ap.add_argument('--traj-id', help='only this trajectory (e.g. traj_224)')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--force', action='store_true', help='re-judge targeted trajectories')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    if args.workers < 1 or args.limit < 0:
        ap.error('workers must be positive and limit nonnegative')

    try:
        targets = _collect_targets(args.os_key, args.traj_id)
    except (ValueError, OSError) as exc:
        ap.error(str(exc))
    if args.traj_id and not targets:
        ap.error('Requested trajectory was not found')
    targets.sort(key=lambda t: record_id_sort_key(t[0]))
    if args.limit:
        targets = targets[:args.limit]

    report = load_jsonl_report(REPORT_PATH, 'traj_id')
    for tid, _, _, image, _, _ in targets:
        if tid not in report:
            continue
        try:
            _normalize(report[tid])
            with Image.open(image) as frame:
                frame.verify()
        except (ValueError, OSError, TypeError):
            report.pop(tid)
    target_ids = {t[0] for t in targets}
    todo = [t for t in targets if args.force or t[0] not in report]
    if todo:
        try:
            require_backend('chat')
        except BackendConfigurationError as exc:
            ap.error(str(exc))
    print(f'trajectories targeted {len(targets)}; '
          f'skipped (already judged) {len(targets) - len(todo)}; to judge {len(todo)}')

    lock = threading.Lock()
    done = [0]
    errors = []

    def work(item):
        tid, os_key, meta_path, obs00, task, fg = item
        try:
            with Image.open(obs00) as frame:
                frame.verify()
            res = judge(obs00, task, fg)
        except Exception as e:  # noqa: BLE001 - one bad item must not kill the run
            with lock:
                done[0] += 1
                errors.append(tid)
                report.pop(tid, None)
                write_jsonl_report(REPORT_PATH, report)
                print(f'  [{done[0]}/{len(todo)}] {tid} {os_key} -> ERROR {str(e)[:80]}')
            return
        rec = {
            'traj_id': tid, 'os_key': os_key, 'target_app': fg,
            'task': task[:400], **res,
            'model': MODEL, 'judged_at': datetime.now().isoformat(timespec='seconds'),
        }
        with lock:
            report[tid] = rec
            write_jsonl_report(REPORT_PATH, report)
            done[0] += 1
            print(f'  [{done[0]}/{len(todo)}] {tid} {os_key} -> {res["verdict"].upper():8s} '
                  f'(app_ok={res["app_ok"]}, content={res["content_present"]}) '
                  f'{res["reason"][:60]}')

    if todo:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(work, todo))

    # === summary over targeted trajectories ===
    records = [report[tid] for tid in target_ids if tid in report]
    vc = Counter(r['verdict'] for r in records)
    by_os = Counter((r['os_key'], r['verdict']) for r in records)
    print('\n' + '=' * 60)
    print(f' Task<->Seed audit: {len(records)} trajectories')
    for v in VERDICTS:
        print(f'   {v:<9} {vc.get(v, 0)}')
    print(' By OS (mismatch/partial only):')
    for (osk, v), c in sorted(by_os.items()):
        if v != 'match':
            print(f'   {osk:<14} {v:<9} {c}')
    print('\n Mismatches:')
    for r in sorted((r for r in records if r['verdict'] == 'mismatch'), key=lambda r: record_id_sort_key(r['traj_id'])):
        print(f'   {r["traj_id"]} [{r["os_key"]}] shows="{r["screenshot_shows"]}" :: {r["reason"][:70]}')
    print(f'\n Report: {REPORT_PATH}')
    print('=' * 60)
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())

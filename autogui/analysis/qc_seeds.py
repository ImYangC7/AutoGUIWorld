# -*- coding: utf-8 -*-
"""Quality-control pass over SEED initial screenshots.

Each seed's initial.png is rendered by the image adapter and may carry generation
artifacts (blurry / garbled text, ghosting, wrong proportions, ...). This script
grades every seed with a configured multimodal model (external model adapter), using
a closed defect taxonomy, then writes the verdict back into the
seed's seed.json under a `qc` field. Nothing is deleted -- annotate only.

Uses the shared model adapter and ThreadPoolExecutor fan-out. The report is a
full snapshot; reruns skip seeds already in it (unless --force re-grades the
targeted ones).

Usage:
    # Model adapter setup is described in docs/backend.md
    python -m autogui.analysis.qc_seeds                 # grade all seeds
    python -m autogui.analysis.qc_seeds --seed-id seed_001
    python -m autogui.analysis.qc_seeds --os macos --workers 8
    python -m autogui.analysis.qc_seeds --image initial_high_quality.png
    python -m autogui.analysis.qc_seeds --force         # re-grade targeted seeds

Outputs:
    - seed.json gains:  "qc": {model, image, verdict, defects, summary, graded_at}
    - data/seeds/_qc_report.jsonl   (full snapshot, one line per graded seed)
    - a console summary: pass/fail counts + defect-type histogram
"""

import os
import json
import argparse
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime


from autogui.state.registry import OS_REGISTRY
from autogui.storage.manager import SEEDS_DIR, seed_dir, list_seeds
from autogui.prompts.seed_qc import build_seed_qc_prompt, DEFECT_TAXONOMY, SEVERITIES
from autogui.utils.jsonio import (
    atomic_write_json, load_jsonl_report, strip_json_fence, write_jsonl_report,
)
from autogui.clients.llm import call_llm_vision
from autogui.clients.backend import require_backend, BackendConfigurationError
from PIL import Image

MODEL = 'external-qc'

QC_REPORT_PATH = os.path.join(SEEDS_DIR, '_qc_report.jsonl')

_VALID_DEFECTS = set(DEFECT_TAXONOMY)
_VALID_SEVERITIES = set(SEVERITIES)
_FAIL_SEVERITIES = {'major', 'critical'}


def _normalize(result):
    """Validate / clean the model's JSON; recompute verdict from severities.

    Reject malformed or unknown defects, and recompute the verdict from valid
    severities rather than accepting the model's own overall verdict.
    """
    if not isinstance(result, dict) or not isinstance(result.get('defects'), list):
        raise ValueError('Seed QC requires a defects list')
    defects = []
    for d in result['defects']:
        if not isinstance(d, dict):
            raise ValueError('Seed QC defects must be objects')
        dtype = d.get('type')
        sev = d.get('severity')
        if dtype not in _VALID_DEFECTS:
            raise ValueError('Seed QC returned an unknown defect type')
        if sev not in _VALID_SEVERITIES:
            sev = 'major'  # unknown severity -> treat conservatively
        defects.append({
            'type': dtype,
            'severity': sev,
            'region': str(d.get('region', ''))[:200],
            'detail': str(d.get('detail', ''))[:300],
        })
    verdict = 'fail' if any(d['severity'] in _FAIL_SEVERITIES for d in defects) else 'pass'
    return {
        'defects': defects,
        'verdict': verdict,
        'summary': str(result.get('summary', ''))[:500],
    }


def grade_seed(img_path, os_name, max_retries=3):
    """Call the VLM and return a normalized QC dict for one image."""
    prompt = build_seed_qc_prompt(os_name)
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


def _write_back(seed_id, qc):
    """Merge the qc result into the seed's seed.json (annotate only)."""
    path = os.path.join(seed_dir(seed_id), 'seed.json')
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    data['qc'] = qc
    atomic_write_json(path, data)


def main():
    ap = argparse.ArgumentParser(description='QC pass over seed initial screenshots.')
    ap.add_argument('--seed-id', help='grade a single seed (e.g. seed_001)')
    ap.add_argument('--os', dest='os_key', choices=list(OS_REGISTRY), help='only grade seeds of this OS')
    ap.add_argument('--image', default='initial.png',
                    help='image filename inside each seed dir to grade')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--force', action='store_true',
                    help='re-grade the targeted seeds even if already in the report')
    ap.add_argument('--limit', type=int, default=0, help='only first N seeds (debug)')
    args = ap.parse_args()
    if args.workers < 1 or args.limit < 0 or os.path.basename(args.image) != args.image:
        ap.error('Invalid workers, limit, or image filename')

    # Resolve the set of seeds to grade.
    if args.seed_id:
        targets = [(args.seed_id, {'os_key': None})]
    else:
        targets = list_seeds(os_key=args.os_key)
    if args.limit:
        targets = targets[:args.limit]

    # `report` is the full snapshot of every seed ever graded — independent of
    # which seeds we target this run. --force only re-grades the TARGETED seeds;
    # other seeds' records are never touched, so --force --seed-id X is safe.
    report = load_jsonl_report(QC_REPORT_PATH, 'seed_id')
    for sid, _ in targets:
        if sid not in report:
            continue
        try:
            _normalize(report[sid])
            if report[sid].get('image', 'initial.png') != args.image:
                raise ValueError('Requested a different image')
            with Image.open(os.path.join(seed_dir(sid), args.image)) as frame:
                frame.verify()
        except (ValueError, OSError, TypeError):
            report.pop(sid)
    target_ids = {sid for sid, _ in targets}
    todo = [(sid, meta) for sid, meta in targets
            if args.force or sid not in report]
    if todo:
        try:
            require_backend('chat')
        except BackendConfigurationError as exc:
            ap.error(str(exc))
    print(f'seeds targeted {len(targets)}; '
          f'skipped (already graded) {len(targets) - len(todo)}; to grade {len(todo)}')

    lock = threading.Lock()
    done = [0]
    failed_ids = []

    def work(item):
        seed_id, meta = item
        try:
            return grade_item(seed_id, meta)
        except Exception as exc:
            with lock:
                failed_ids.append(seed_id)
                report.pop(seed_id, None)
                write_jsonl_report(QC_REPORT_PATH, report)
                print(f'{seed_id}: QC failed ({type(exc).__name__})')

    def grade_item(seed_id, meta):
        sd = seed_dir(seed_id)
        img_path = os.path.join(sd, args.image)
        if not os.path.exists(img_path):
            raise FileNotFoundError('Requested seed image is missing')
        with Image.open(img_path) as frame:
            frame.verify()
        # OS human name for the prompt.
        os_key = meta.get('os_key')
        if not os_key:  # single --seed-id path: read it from seed.json
            with open(os.path.join(sd, 'seed.json'), encoding='utf-8') as f:
                os_key = json.load(f).get('os_key')
        if not isinstance(os_key, str) or os_key not in OS_REGISTRY:
            raise ValueError('Invalid seed platform')
        os_name = OS_REGISTRY.get(os_key, {}).get('name', os_key or 'a computer UI')

        # A single VLM failure (e.g. sustained 429) must not kill the whole
        # ex.map batch: record it as skipped and move on. Unwritten seeds are
        # simply re-targeted on the next run (report-based skip is by presence).
        try:
            qc = grade_seed(img_path, os_name)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f'Seed QC failed ({type(e).__name__})') from None
        qc.update({
            'model': MODEL,
            'image': os.path.basename(img_path),
            'graded_at': datetime.now().isoformat(timespec='seconds'),
        })
        _write_back(seed_id, qc)
        rec = {'seed_id': seed_id, 'os_key': os_key, **qc}
        with lock:
            report[seed_id] = rec
            write_jsonl_report(QC_REPORT_PATH, report)
            done[0] += 1
            tag = 'PASS' if qc['verdict'] == 'pass' else 'FAIL'
            print(f'  [{done[0]}/{len(todo)}] {seed_id} {tag} '
                  f'({len(qc["defects"])} defect(s)) {qc["summary"][:60]}')

    if todo:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(work, todo))
    if failed_ids:
        print(f'\n  ⚠️  {len(failed_ids)} seed(s) failed grading (rerun to retry): '
              f'{", ".join(failed_ids[:10])}{" ..." if len(failed_ids) > 10 else ""}')

    # === Summary over the TARGETED seeds (so --os / --seed-id scope the report) ===
    records = [report[sid] for sid in target_ids if sid in report]
    passed = sum(1 for r in records if r.get('verdict') == 'pass')
    failed = len(records) - passed
    dtypes = Counter(d['type'] for r in records for d in r.get('defects', []))
    print('\n' + '=' * 50)
    print(f' QC complete: {len(records)} seeds | PASS {passed} | FAIL {failed}')
    if dtypes:
        print(' Defect histogram (by occurrence):')
        for t, c in dtypes.most_common():
            print(f'   {t:<18} {c}')
    print(f' Report: {QC_REPORT_PATH}')
    print('=' * 50)
    return int(bool(failed_ids))


if __name__ == '__main__':
    raise SystemExit(main())

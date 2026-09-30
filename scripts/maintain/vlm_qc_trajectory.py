#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full-step VLM quality check for trajectories. Writes a structured verdict into
meta.json (step.qc) for every step, judging grounding correctness, action-vs-
screen consistency, and thought consistency through the vision adapter.

For each step the model sees up to THREE images of the same screen:
  - BEFORE: clean pre-action observation (prev_obs)
  - TARGET: red-box annotated act frame (pointing actions only)
  - AFTER:  post-action observation (obs_frame), for transition consistency
plus task, action, grounded element names, and the step's thinking.

The model's raw verdict is normalized (drop out-of-enum values, RECOMPUTE overall
from dimensions so the rule is enforced consistently). Idempotent/resumable: a
step with valid cached QC is skipped unless --force; error records are retried. Per-step independent —
a step that fails to judge is marked qc.error but does NOT abort the trajectory.

Usage:
  python scripts/maintain/vlm_qc_trajectory.py --os ubuntu2404 --limit 10
  python scripts/maintain/vlm_qc_trajectory.py --os windows11 --workers 200 --rate 1400
"""
import argparse
import base64
import glob
import io
import json
import os
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from autogui import DATA_DIR
from autogui.clients.llm import generate_text
from autogui.pipeline.step_utils import prev_obs_name, element_descs, frame_path
from autogui.state.registry import OS_REGISTRY, BBOX_ACTIONS
from autogui.clients.backend import require_backend, BackendConfigurationError
from autogui.prompts.trajectory_qc import TRAJ_QC_SYSTEM, build_trajectory_qc_prompt
from autogui.utils.jsonio import atomic_write_json, strip_json_fence, write_jsonl_report
from autogui.utils.ratelimit import RateGate

TRAJ_ROOT = os.path.join(DATA_DIR, 'trajectories')

_meta_lock = threading.Lock()
_RATE_GATE = RateGate(0)

# valid enum values per dimension
_ENUMS = {
    'box_hits_target': {'pass', 'warn', 'fail', 'na'},
    'box_tightness': {'pass', 'warn', 'fail', 'na'},
    'target_exists': {'pass', 'fail', 'na'},
    'action_valid_here': {'pass', 'warn', 'fail'},
    'obs_transition_ok': {'pass', 'warn', 'fail', 'na'},
    'thinking_matches_screen': {'pass', 'warn', 'fail', 'na'},
    'thinking_wavering': {'pass', 'fail', 'na'},
}
# dimensions whose 'fail' makes the whole step 'major'
_MAJOR_ON_FAIL = ('box_hits_target', 'target_exists', 'action_valid_here', 'obs_transition_ok')





def _encode_image(path):
    with Image.open(path) as source:
        im = source.convert('RGB')
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('utf-8')


def _action_params(act):
    """Compact string of the non-'action' action fields for the prompt."""
    if not isinstance(act, dict):
        return str(act)
    parts = [f'{k}={v}' for k, v in act.items() if k != 'action' and v not in (None, '')]
    return ', '.join(parts) if parts else '(none)'


def _normalize(raw):
    """Validate enums and RECOMPUTE overall from dimensions (don't trust self-eval)."""
    if not isinstance(raw, dict):
        raise ValueError('Trajectory QC requires an object')
    required = {
        'grounding': ('box_hits_target', 'box_tightness', 'target_exists'),
        'action': ('action_valid_here', 'obs_transition_ok'),
        'thinking': ('thinking_matches_screen', 'thinking_wavering'),
    }
    for group, fields in required.items():
        values = raw.get(group)
        if not isinstance(values, dict):
            raise ValueError('Trajectory QC group is missing')
        for field in fields:
            if not isinstance(values.get(field), str) or values[field] not in _ENUMS[field]:
                raise ValueError('Trajectory QC verdict is missing or invalid')
    g = raw['grounding']
    a = raw.get('action') or {}
    t = raw.get('thinking') or {}
    out_g, out_a, out_t = {}, {}, {}
    flat = {}
    for group, src, dst in (('grounding', g, out_g), ('action', a, out_a), ('thinking', t, out_t)):
        for k in required[group]:
            dst[k] = src[k]
            flat[k] = src[k]
    # recompute overall
    overall = 'ok'
    if any(flat.get(k) == 'fail' for k in _MAJOR_ON_FAIL):
        overall = 'major'
    elif any(v == 'fail' for v in flat.values()) or any(v == 'warn' for v in flat.values()):
        overall = 'minor'
    conf = raw.get('confidence')
    conf = conf if conf in ('high', 'medium', 'low') else 'low'
    return {
        'grounding': out_g,
        'action': out_a,
        'thinking': out_t,
        'overall': overall,
        'confidence': conf,
        'reason': str(raw.get('reason', ''))[:300],
    }


def _call_vlm(system_prompt, user_text, image_urls, max_retries=4):
    content = [{'type': 'text', 'text': user_text}]
    content.extend({'type': 'image_url', 'image_url': {'url': url}} for url in image_urls)
    for attempt in range(max_retries):
        _RATE_GATE.wait()
        text = generate_text([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': content},
        ], purpose='qc', max_tokens=int(os.environ.get('QC_MAX_TOKENS', '2048')),
           max_retries=max_retries)
        try:
            return _normalize(json.loads(strip_json_fence(text)))
        except (ValueError, TypeError, AttributeError):
            if attempt + 1 == max_retries:
                raise RuntimeError('Trajectory QC returned an invalid assessment') from None
    raise ValueError('max_retries must be positive')


def _check_applicability(result, action_name):
    """A visible target or rendered transition requires an actual verdict."""
    if action_name in BBOX_ACTIONS and any(value == 'na' for value in result['grounding'].values()):
        raise ValueError('Pointing-action grounding dimensions cannot be unavailable')
    if action_name != 'answer' and result['action']['obs_transition_ok'] == 'na':
        raise ValueError('A rendered transition requires a transition verdict')


def _process_traj(traj_dir, force):
    """QC every step of one trajectory. Returns (done, skipped, errored, Counter(overall))."""
    mp = os.path.join(traj_dir, 'meta.json')
    with open(mp, encoding='utf-8') as f:
        meta = json.load(f)
    task = meta.get('task_description') or ''
    steps = meta.get('steps') or []

    done = skipped = errored = 0
    verdicts = Counter()
    changed = False
    if not isinstance(steps, list) or not steps or any(not isinstance(step, dict) for step in steps):
        raise ValueError('Trajectory has no valid steps')
    for step in steps:
        try:
            if step.get('status') != 'success':
                raise ValueError('Cannot grade an unfinished generation step')
            act = step.get('action')
            if not isinstance(act, dict):
                raise ValueError('Invalid action metadata')
            name = act.get('action')
            descs = element_descs(step)
            base = prev_obs_name(meta, step.get('step'))
            before = frame_path(traj_dir, base)
            after = frame_path(traj_dir, step.get('obs_frame'))
            paths = [(before, 'BEFORE (pre-action screen)')]
            if name in BBOX_ACTIONS:
                target = frame_path(traj_dir, step.get('act_frame'))
                if target == before or not descs or len(step.get('boxes') or []) != len(descs):
                    raise ValueError('Missing pointing-action annotations')
                paths.append((target, 'TARGET (annotated action frame)'))
            if name != 'answer':
                if after == before:
                    raise ValueError('Nonterminal action is missing its new observation')
                paths.append((after, 'AFTER (screen after the action)'))
            elif after != before:
                raise ValueError('Terminal answer must reuse the previous observation')
            images = [_encode_image(path) for path, _ in paths]
            cached = step.get('qc')
            if isinstance(cached, dict) and not force and not cached.get('error'):
                try:
                    normalized = _normalize(cached)
                    _check_applicability(normalized, name)
                except (ValueError, TypeError, AttributeError):
                    pass
                else:
                    step['qc'] = normalized
                    changed |= normalized != cached
                    skipped += 1
                    verdicts[normalized['overall']] += 1
                    continue
            legend = '\n'.join(f'{i}. {label}' for i, (_, label) in enumerate(paths, 1))
            user_text = build_trajectory_qc_prompt(
                task, name, _action_params(act), step.get('target_element'),
                ', '.join(descs) if descs else '(none)',
                step.get('thought') or step.get('thinking'), legend)
            qc = _call_vlm(TRAJ_QC_SYSTEM, user_text, images)
            _check_applicability(qc, name)
        except Exception as exc:
            print(f'  ! {os.path.basename(traj_dir)} step{step.get("step")} QC error: {type(exc).__name__}')
            step['qc'] = {'error': f'QC input or assessment failed ({type(exc).__name__})'}
            changed = True
            errored += 1
            continue
        step['qc'] = qc
        verdicts[qc['overall']] += 1
        changed = True
        done += 1

    if changed:
        with _meta_lock:
            atomic_write_json(mp, meta)
    return done, skipped, errored, verdicts


_DIMS = ['box_hits_target', 'box_tightness', 'target_exists',
         'action_valid_here', 'obs_transition_ok',
         'thinking_matches_screen', 'thinking_wavering']


def build_report(os_keys, out_prefix):
    """Scan persisted step.qc across trajectories and emit an aggregate report +
    an actionable JSONL of every major-verdict step. Trajectories are unchanged."""
    summary = {}
    actionable = []
    for os_key in os_keys:
        trajs = sorted(glob.glob(os.path.join(TRAJ_ROOT, os_key, 'traj_*')))
        overall_cnt = Counter()
        dim_cnt = {d: Counter() for d in _DIMS}
        conf_cnt = Counter()
        n_steps = n_qc = n_err = 0
        traj_with_major = 0
        for t in trajs:
            mp = os.path.join(t, 'meta.json')
            if not os.path.exists(mp):
                continue
            try:
                with open(mp, encoding='utf-8') as stream:
                    meta = json.load(stream)
                if not isinstance(meta, dict) or not isinstance(meta.get('steps'), list):
                    raise ValueError('Invalid metadata')
            except (OSError, ValueError):
                raise ValueError(f'Cannot summarize invalid metadata: {os.path.basename(t)}') from None
            tid = os.path.basename(t)
            has_major = False
            for s in meta.get('steps') or []:
                if not isinstance(s, dict):
                    raise ValueError(f'Invalid step metadata: {tid}')
                n_steps += 1
                qc = s.get('qc')
                if not qc:
                    continue
                if not isinstance(qc, dict) or qc.get('error'):
                    n_err += 1
                    continue
                try:
                    qc = _normalize(qc)
                except (ValueError, TypeError, AttributeError):
                    n_err += 1
                    continue
                n_qc += 1
                ov = qc.get('overall', '?')
                overall_cnt[ov] += 1
                conf_cnt[qc.get('confidence', '?')] += 1
                for d in _DIMS:
                    for grp in ('grounding', 'action', 'thinking'):
                        if d in (qc.get(grp) or {}):
                            dim_cnt[d][qc[grp][d]] += 1
                if ov == 'major':
                    has_major = True
                    a = s.get('action') or {}
                    actionable.append({
                        'os_key': os_key, 'traj_id': tid, 'step': s.get('step'),
                        'action': a.get('action') if isinstance(a, dict) else a,
                        'target_element': s.get('target_element'),
                        'confidence': qc.get('confidence'),
                        'grounding': qc.get('grounding'), 'action_qc': qc.get('action'),
                        'thinking_qc': qc.get('thinking'), 'reason': qc.get('reason'),
                    })
            if has_major:
                traj_with_major += 1
        summary[os_key] = {
            'trajectories': len(trajs), 'steps': n_steps, 'qc_done': n_qc,
            'qc_error': n_err, 'overall': dict(overall_cnt),
            'confidence': dict(conf_cnt),
            'dimensions': {d: dict(dim_cnt[d]) for d in _DIMS},
            'trajectories_with_major': traj_with_major,
        }

    rep_path = f'{out_prefix}_report.json'
    act_path = f'{out_prefix}_actionable.jsonl'
    atomic_write_json(rep_path, {'summary': summary})
    write_jsonl_report(act_path, {f'{r["traj_id"]}_{r["step"]}': r for r in actionable})

    print('\n=== VLM 质检聚合报告 ===')
    for os_key, v in summary.items():
        ov = v['overall']
        tot = sum(ov.values()) or 1
        print(f'\n[{os_key}] 轨迹={v["trajectories"]} step={v["steps"]} '
              f'已QC={v["qc_done"]} 错误={v["qc_error"]}')
        print(f'  overall: ' + '  '.join(
            f'{k}={ov.get(k,0)}({ov.get(k,0)*100//tot}%)' for k in ('ok', 'minor', 'major')))
        print(f'  含major的轨迹: {v["trajectories_with_major"]}/{v["trajectories"]}')
        print(f'  confidence: {v["confidence"]}')
        print('  各维度 fail 计数:')
        for d in _DIMS:
            fails = v['dimensions'][d].get('fail', 0)
            warns = v['dimensions'][d].get('warn', 0)
            if fails or warns:
                print(f'    {d}: fail={fails} warn={warns}')
    print(f'\n报告 -> {rep_path}')
    print(f'待处理清单(所有major step) -> {act_path}  ({len(actionable)}条)')


def main():
    global _RATE_GATE
    ap = argparse.ArgumentParser()
    ap.add_argument('--os', dest='os_key', default='ubuntu2404', choices=list(OS_REGISTRY))
    ap.add_argument('--limit', type=int, default=0, help='only first N trajectories (0=all)')
    ap.add_argument('--workers', type=int, default=200)
    ap.add_argument('--rate', type=float, default=1400.0, help='global max requests/min (cap 1500)')
    ap.add_argument('--force', action='store_true', help='re-QC even if step.qc exists')
    ap.add_argument('--traj-ids-file', default='',
                    help='JSONL sidecar with a traj_id field; restrict QC to those trajectories only')
    ap.add_argument('--report', action='store_true',
                    help='only build the aggregate report from existing step.qc (no API calls)')
    ap.add_argument('--report-os', nargs='+', default=list(OS_REGISTRY), choices=list(OS_REGISTRY),
                    help='OS keys to include when building the report')
    args = ap.parse_args()

    if args.workers < 1 or args.limit < 0 or not 0 <= args.rate <= 1500:
        ap.error('Invalid worker count, limit, or request rate')

    if args.report:
        try:
            build_report(args.report_os, os.path.join(TRAJ_ROOT, '_vlm_qc'))
        except (ValueError, OSError) as exc:
            ap.error(str(exc))
        return

    _RATE_GATE = RateGate(args.rate)

    trajs = sorted(glob.glob(os.path.join(TRAJ_ROOT, args.os_key, 'traj_*')))
    trajs = [t for t in trajs if os.path.exists(os.path.join(t, 'meta.json'))]
    if args.traj_ids_file:
        try:
            with open(args.traj_ids_file, encoding='utf-8') as stream:
                rows = [json.loads(line) for line in stream if line.strip()]
            keep = {row['traj_id'] for row in rows if row.get('traj_id')}
        except (ValueError, OSError, AttributeError, TypeError) as exc:
            ap.error(f'Invalid trajectory selection file ({type(exc).__name__})')
        trajs = [t for t in trajs if os.path.basename(t) in keep]
    if args.limit:
        trajs = trajs[:args.limit]
    if trajs:
        try:
            require_backend('chat')
        except BackendConfigurationError as exc:
            ap.error(str(exc))
    print(f'VLM质检: {args.os_key}  轨迹={len(trajs)}  workers={args.workers}  '
          f'rate={args.rate}/min  force={args.force}')

    tot_done = tot_skip = tot_err = 0
    grand = Counter()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_process_traj, t, args.force): t for t in trajs}
        for i, fut in enumerate(as_completed(futs), 1):
            t = futs[fut]
            try:
                d, s, e, v = fut.result()
            except Exception as ex_:  # noqa: BLE001
                tot_err += 1
                print(f'  ! {os.path.basename(t)} traj-level error: {ex_}')
                continue
            tot_done += d; tot_skip += s; tot_err += e; grand.update(v)
            print(f'  [{i}/{len(trajs)}] {os.path.basename(t)}: +{d} qc '
                  f'(skip={s} err={e}) {dict(v)}')

    print(f'\n✅ done={tot_done}  skipped={tot_skip}  errored={tot_err}')
    print(f'overall分布: {dict(grand)}')
    return int(tot_err > 0)


if __name__ == '__main__':
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Create seeds, generate tasks per seed, and render independent trajectories.

The three phases use worker pools. Task candidates within one seed and image
transitions within one trajectory remain serial. The process exits nonzero
when any requested seed/task/trajectory is missing or incomplete.
"""

import argparse
import os
import random
import threading
import time
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from autogui.pipeline.seed import create_seed
from autogui.pipeline.trajectory import expand_seed
from autogui.tasks.generator import generate_tasks_for_seed
from autogui.storage.manager import load_seed, trajectory_dir
from autogui.pipeline.step_utils import trajectory_complete
from autogui.clients.backend import BackendError, BackendConfigurationError

_PRINT_LOCK = threading.Lock()

# Attempts for seed-description validation failures. Adapter retries are separate.
SEED_MAX_RETRIES = int(os.environ.get('SEED_MAX_RETRIES', '5'))

# Optional task bias: force in-app interaction instead of system operations.
# Injected via the task directive's 'focus' field when --app-focus is set.
APP_FOCUS = (
    'This task MUST be an in-APP interaction: open one of the real apps on the '
    'home screen (tap its icon, or a folder then the app) and perform a concrete '
    'action INSIDE that app (browse, search, compose, play, add to cart, send a '
    'message, like/post, edit, filter, switch a tab, open a detail page, etc.). '
    'Do NOT make it a pure system operation (no Settings / Control Center / '
    'notification-shade / toggle WiFi-Bluetooth-brightness tasks).'
)

# Long-horizon bias: force a genuinely long, multi-stage workflow so the planner
# emits 15+ distinct actions. Paired with long_horizon=True (forces 'complex'
# difficulty) in generate_tasks_for_seed.
LONG_HORIZON_FOCUS = (
    'This task MUST be a LONG, multi-stage workflow that takes at least 15 '
    'distinct GUI actions to finish. Chain several sub-goals in a sensible order '
    'inside one app (or across a couple of related windows already open): e.g. '
    'create/open something, then make a sequence of edits/configurations through '
    'multiple menus, dialogs and panels, verify or adjust intermediate results, '
    'and finally save/export/apply. Each stage should depend on the previous one. '
    'Do NOT collapse it into a single short operation; it must stay one coherent '
    'task (not a list of unrelated mini-tasks), but a deep, many-step one.'
)


def log(msg):
    with _PRINT_LOCK:
        print(msg, flush=True)


def _create_one_seed(os_key, quality):
    """Create one seed; IDs are allocated after successful image generation."""
    for attempt in range(SEED_MAX_RETRIES):
        try:
            return create_seed(os_key, quality=quality)
        except (BackendError, BackendConfigurationError):
            log(f'{os_key}: model operation failed after adapter retries')
            return None
        except Exception as e:
            if attempt < SEED_MAX_RETRIES - 1:
                delay = min(30, 2 ** attempt) + random.uniform(0, 2)
                log(f'  ⚠️  {os_key} attempt {attempt+1}/{SEED_MAX_RETRIES} '
                    f'failed ({type(e).__name__}: {str(e)[:70]}); retry in {delay:.1f}s')
                time.sleep(delay)
            else:
                log(f'  ⚠️  {os_key} failed after {SEED_MAX_RETRIES} '
                    f'attempts ({type(e).__name__}: {str(e)[:80]}); skip')
    return None


def gen_tasks_for_seed(seed_id, n, dedup_threshold, app_focus=False, long_horizon=False):
    """Phase 1: serially generate n deduped auto-tasks for a seed.

    Returns list of (seed_id, task_dict). Failures (API/dedup) are skipped.
    app_focus biases tasks toward in-app interaction (vs system operations).
    long_horizon forces every task to 'complex' difficulty + a long-workflow
    focus so the planner produces 15+ step trajectories.
    """
    seed = load_seed(seed_id)

    def _log(kind, info):
        if kind == 'skip':
            log(f'  ⚠️  {seed_id} task {info["index"]+1}/{info["total"]}: {info["reason"]}; skip')

    focus = None
    if long_horizon:
        focus = LONG_HORIZON_FOCUS
    elif app_focus:
        focus = APP_FOCUS
    tasks = generate_tasks_for_seed(seed, n, dedup_threshold=dedup_threshold,
                                    focus=focus, on_event=_log,
                                    long_horizon=long_horizon)
    return [(seed_id, t) for t in tasks]


def render_job(seed_id, task, quality, dedup_threshold, act_render='pil', grounder=None):
    """Phase 2 worker: render one trajectory. Dedup already done in phase 1.

    `task` is a task dict from generate_tasks_for_seed (carries 'task' text plus
    optional feasibility fields for infeasible trap tasks).
    """
    text = task['task'] if isinstance(task, dict) else task
    infeasible = isinstance(task, dict) and task.get('feasible') is False
    try:
        tid = expand_seed(seed_id, text, quality=quality,
                          dedup_threshold=dedup_threshold, skip_dedup=True,
                          act_render=act_render, grounder=grounder,
                          infeasible=infeasible,
                          judge_timing=task.get('judge_timing') if isinstance(task, dict) else None,
                          infeasible_reason=task.get('infeasible_reason') if isinstance(task, dict) else None,
                          explore_hint=task.get('explore_hint') if isinstance(task, dict) else None)
        if tid and trajectory_complete(json.loads((Path(trajectory_dir(tid)) / 'meta.json').read_text())):
            log(f'  ✅ {seed_id}: {tid}  «{text[:50]}»')
            return tid
        log(f'{seed_id}: trajectory skipped or partial')
        return None
    except Exception as e:
        log(f'  ⚠️  {seed_id} render failed ({type(e).__name__}: {str(e)[:90]}); skip')
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--os', nargs='+', default=[])
    ap.add_argument('--seeds-per-os', type=int, default=0)
    ap.add_argument('--expand-seeds', nargs='+', default=[])
    ap.add_argument('--traj', type=int, default=3)
    ap.add_argument('--quality', default='high', choices=['low', 'medium', 'high'])
    ap.add_argument('--workers', type=int, default=16, help='parallel render workers (phase 2)')
    ap.add_argument('--dedup-threshold', type=float, default=0.85)
    ap.add_argument('--act-render', default='pil', choices=['pil', 'image2'],
                    help='act-frame red-box renderer: pil (pixel-identical overlay, default) '
                         'or image2 (image-edit repaint). Coordinates always from the grounder.')
    ap.add_argument('--grounder', default=None, choices=['mai_ui', 'gpt55', 'locate_anything'],
                    help='coordinate backend: mai_ui, gpt55, or locate_anything '
                         '(NVIDIA LocateAnything-3B, port 8004). Default: locate_anything '
                         '(override via AUTOGUI_GROUNDER).')
    ap.add_argument('--app-focus', action='store_true',
                    help='bias tasks toward in-app interaction (mobile), not system ops')
    ap.add_argument('--long-horizon', action='store_true',
                    help='force long multi-stage tasks (15+ actions): all-complex difficulty '
                         '+ long-workflow focus')
    args = ap.parse_args()
    if args.workers < 1 or args.traj < 0 or args.seeds_per_os < 0:
        ap.error('workers must be positive; traj and seeds-per-os must be nonnegative')
    if not 0 <= args.dedup_threshold <= 1 or SEED_MAX_RETRIES < 1:
        ap.error('Invalid dedup threshold or SEED_MAX_RETRIES')
    if args.seeds_per_os and not args.os:
        ap.error('--seeds-per-os requires --os')
    if not (args.os and args.seeds_per_os) and not args.expand_seeds:
        ap.error('Specify new seeds or --expand-seeds')
    if args.expand_seeds and args.traj == 0:
        ap.error('--expand-seeds requires --traj greater than zero')
    args.os = list(dict.fromkeys(args.os))
    args.expand_seeds = list(dict.fromkeys(args.expand_seeds))
    for sid in args.expand_seeds:
        try:
            load_seed(sid)
        except (ValueError, FileNotFoundError) as exc:
            ap.error(str(exc))
    from autogui.state.registry import OS_REGISTRY
    if any(os_key not in OS_REGISTRY for os_key in args.os):
        ap.error('Unknown platform; see cli.py seed --help')
    if args.seeds_per_os > 0 or args.expand_seeds:
        from autogui.clients.backend import require_backend, BackendConfigurationError
        try:
            require_backend('chat', 'image')
        except BackendConfigurationError as exc:
            ap.error(str(exc))

    # ── Phase 0 (parallel): create target seeds ──
    # Seed creation is I/O-bound (LLM + image per seed) and independent across
    # seeds, so run it on the same worker pool as the render phases instead of
    # serially. reserve_seed_id keeps ids collision-free under concurrency.
    seeds = []
    total_new = len(args.os) * args.seeds_per_os
    if total_new > 0:
        log(f'\n{"="*64}\n PHASE 0: creating {total_new} seeds '
            f'(parallel, workers={args.workers})\n{"="*64}')
        done0 = [0]
        p0_lock = threading.Lock()

        def _mk(os_key):
            sid = _create_one_seed(os_key, args.quality)
            with p0_lock:
                done0[0] += 1
                if sid:
                    log(f'  [{done0[0]}/{total_new}] ✓ {sid}')
            return sid

        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(_mk, os_key)
                    for os_key in args.os for _ in range(args.seeds_per_os)]
            for f in as_completed(futs):
                sid = f.result()
                if sid:
                    seeds.append(sid)
        log(f'\n  → {len(seeds)}/{total_new} seeds created')
    seeds.extend(args.expand_seeds)

    if args.traj <= 0:
        log(f'\n✅ created {len(seeds)} seeds (no trajectories requested)')
        return int(len(seeds) != total_new)

    # ── Phase 1 (parallel): generate all (seed, task) jobs ──
    # Per-seed dedup is an independent in-memory registry (TaskRegistry(None)),
    # so seeds share no state and task-gen parallelizes safely. Each task is one
    # ~50s LLM call, so going parallel turns a multi-hour serial phase into minutes.
    log(f'\n{"="*64}\n PHASE 1: task generation for {len(seeds)} seeds '
        f'(parallel, workers={args.workers})\n{"="*64}')
    jobs = []
    done1 = [0]
    p1_lock = threading.Lock()

    def _gen_one(sid):
        out = gen_tasks_for_seed(sid, args.traj, args.dedup_threshold,
                                 app_focus=args.app_focus,
                                 long_horizon=args.long_horizon)
        with p1_lock:
            done1[0] += 1
            log(f'  [{done1[0]}/{len(seeds)}] {sid}: {len(out)} task(s)')
        return out

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(_gen_one, sid) for sid in seeds]):
            try:
                jobs.extend(fut.result())
            except Exception as e:  # noqa: BLE001
                log(f'  ⚠️  task-gen failed for a seed ({type(e).__name__}: {str(e)[:90]}); skip')
    log(f'\n  → {len(jobs)} (seed, task) jobs queued')

    # ── Phase 2 (parallel): render trajectories ──
    log(f'\n{"="*64}\n PHASE 2: rendering {len(jobs)} trajectories (workers={args.workers})\n{"="*64}')
    made = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(render_job, sid, task, args.quality, args.dedup_threshold, args.act_render, args.grounder)
                for sid, task in jobs]
        for f in as_completed(futs):
            if f.result():
                made += 1

    log(f'\n{"="*64}\n BATCH DONE: {made}/{len(jobs)} trajectories from {len(seeds)} seeds\n{"="*64}')
    requested_seeds = total_new + len(args.expand_seeds)
    return int(len(seeds) != requested_seeds or made != requested_seeds * args.traj)


if __name__ == '__main__':
    raise SystemExit(main())

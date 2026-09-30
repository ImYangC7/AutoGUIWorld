# -*- coding: utf-8 -*-
"""Command-line entry point for GUI training-data generation.

Commands:
    seed    Sample a GUI state, render initial.png, and save the seed.
    expand  Plan a task and render observation/action frames from a saved seed.
    list    Inspect saved seeds or trajectories.

Examples:
    python cli.py seed --os windows11 --seed 42
    python cli.py seed --os android --batch 3
    python cli.py expand --seed-id seed_001 --task "Open Settings"
    python cli.py expand --seed-id seed_001 --auto-tasks 5
"""

import argparse
import sys

from autogui.state.registry import OS_REGISTRY
from autogui.pipeline.seed import create_seed
from autogui.pipeline.trajectory import expand_seed
from autogui.tasks.generator import generate_tasks_for_seed
from autogui.storage.manager import (
    load_seed, list_seeds, list_trajectories, trajectory_dir,
)
import json
from pathlib import Path
from autogui.pipeline.step_utils import trajectory_complete
from autogui.clients.backend import BackendError


def cmd_seed(args):
    for i in range(args.batch):
        if args.batch > 1:
            print(f'\n>>> Seed batch {i+1}/{args.batch}')
        create_seed(args.os, seed_rng=args.seed + i if args.seed is not None else None,
                    rich_state=args.rich_state, skip_state=args.skip_state,
                    quality=args.quality,
                    web_category=args.web_category, web_site=args.web_site,
                    web_url=args.web_url, web_content=args.web_content)


def cmd_expand(args):
    results = []
    if args.task:
        results.append(expand_seed(args.seed_id, args.task, quality=args.quality,
                    dedup_threshold=args.dedup_threshold, skip_dedup=args.skip_dedup,
                    act_render=args.act_render, grounder=args.grounder))
    elif args.auto_tasks and args.auto_tasks > 0:
        seed = load_seed(args.seed_id)

        def _log(kind, info):
            if kind == 'start':
                print(f'\n>>> Auto-task {info["index"]+1}/{info["total"]} for '
                      f'{args.seed_id} (难度={info["difficulty"]})')
            elif kind == 'skip':
                print(f'  ❌ 跳过：{info["reason"]}')

        tasks = generate_tasks_for_seed(seed, args.auto_tasks,
                                        dedup_threshold=args.dedup_threshold,
                                        on_event=_log)
        for t in tasks:
            infeasible = t.get('feasible') is False
            results.append(expand_seed(args.seed_id, t['task'], quality=args.quality,
                        dedup_threshold=args.dedup_threshold, skip_dedup=True,
                        act_render=args.act_render, grounder=args.grounder,
                        infeasible=infeasible, judge_timing=t.get('judge_timing'),
                        infeasible_reason=t.get('infeasible_reason'),
                        explore_hint=t.get('explore_hint')))
    else:
        print('请指定 --task 或 --auto-tasks N')
        sys.exit(1)
    requested = 1 if args.task else args.auto_tasks
    complete = sum(bool(tid) and trajectory_complete(json.loads(
        (Path(trajectory_dir(tid)) / 'meta.json').read_text())) for tid in results)
    return int(complete != requested)


def cmd_list(args):
    if args.what == 'seeds':
        items = list_seeds(os_key=args.os)
        print(f'共 {len(items)} 个 seeds:')
        for sid, m in items:
            print(f'  {sid}  os={m["os_key"]:15s}  blockers={len(m["blockers"])}  created={m["created_at"]}')
    elif args.what == 'trajectories':
        items = list_trajectories(seed_id=args.seed_id, os_key=args.os)
        print(f'共 {len(items)} 个 trajectories:')
        for tid, m in items:
            print(f'  {tid}  seed={m["seed_id"]}  os={m["os_key"]:15s}  steps={m["steps"]}  task={m["task_description"][:40]}')


def main():
    parser = argparse.ArgumentParser(description='GUI Agent 数据生成（seed + trajectory 模型）')
    sub = parser.add_subparsers(dest='mode', required=True)

    # seed subcommand
    p_seed = sub.add_parser('seed', help='创建一个 seed（采样初始状态+生成 initial.png）')
    p_seed.add_argument('--os', required=True, choices=list(OS_REGISTRY.keys()))
    p_seed.add_argument('--seed', type=int, default=None, help='RNG 种子')
    p_seed.add_argument('--rich-state', action='store_true', help='全集采样（含极端状态）')
    p_seed.add_argument('--skip-state', action='store_true', help='clean baseline')
    p_seed.add_argument('--quality', default='high', choices=['low', 'medium', 'high'])
    p_seed.add_argument('--batch', type=int, default=1, help='一次创建 N 个 seed')
    p_seed.add_argument('--web-category', default=None,
                        help='限定浏览器网页类别 (如 Productivity/Commerce/Finance/News/...)')
    p_seed.add_argument('--web-site', default=None,
                        help='限定浏览器具体站点 (如 Shopify/GitHub/YouTube/Amazon)')
    p_seed.add_argument('--web-url', default=None,
                        help='浏览器 active tab 直接指定外部 URL (真实任务种子)')
    p_seed.add_argument('--web-content', default=None,
                        help='配合 --web-url: active tab 页面内容描述')
    p_seed.set_defaults(func=cmd_seed)

    # expand subcommand
    p_exp = sub.add_parser('expand', help='从 seed 派生一条或多条轨迹')
    p_exp.add_argument('--seed-id', required=True)
    p_exp.add_argument('--task', default=None, help='手动指定任务')
    p_exp.add_argument('--auto-tasks', type=int, default=0, help='自动生成 N 个任务')
    p_exp.add_argument('--quality', default='high', choices=['low', 'medium', 'high'])
    p_exp.add_argument('--skip-dedup', action='store_true')
    p_exp.add_argument('--dedup-threshold', type=float, default=0.85)
    p_exp.add_argument('--act-render', default='pil', choices=['pil', 'image2'],
                       help='how act-frame red boxes are drawn: pil (pixel-identical overlay, '
                            'default) or image2 (image-edit repaint). Box coordinates always '
                            'come from the grounder.')
    p_exp.add_argument('--grounder', default=None, choices=['mai_ui', 'gpt55', 'locate_anything'],
                       help='coordinate backend for act-frame boxes: mai_ui (MAI-UI→OmniParser→CV), '
                            'gpt55 (GPT-5.5 vision + cv2), or locate_anything (NVIDIA '
                            'LocateAnything-3B, port 8004). Default: locate_anything '
                            '(override via AUTOGUI_GROUNDER).')
    p_exp.set_defaults(func=cmd_expand)

    # list subcommand
    p_list = sub.add_parser('list', help='列出 seeds 或 trajectories')
    p_list.add_argument('what', choices=['seeds', 'trajectories'])
    p_list.add_argument('--os', choices=list(OS_REGISTRY), default=None)
    p_list.add_argument('--seed-id', default=None)
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    if args.mode == 'seed' and args.batch < 1:
        parser.error('--batch must be positive')
    if args.mode == 'expand' and (bool(args.task) == (args.auto_tasks > 0)):
        parser.error('Choose exactly one of --task or --auto-tasks N')
    if args.mode == 'expand' and (args.auto_tasks < 0 or not 0 <= args.dedup_threshold <= 1 or (args.task is not None and not args.task.strip())):
        parser.error('Invalid task, task count, or dedup threshold')
    if args.mode in ('seed', 'expand'):
        from autogui.clients.backend import require_backend, BackendConfigurationError
        try:
            require_backend('chat', 'image')
        except BackendConfigurationError as exc:
            parser.error(str(exc))
    try:
        result = args.func(args)
    except (ValueError, FileNotFoundError, FileExistsError, BackendError) as exc:
        parser.error(str(exc))
    return result or 0


if __name__ == '__main__':
    raise SystemExit(main())

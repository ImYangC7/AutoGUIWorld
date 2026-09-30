#!/usr/bin/env python3
"""Check saved seeds, trajectories, frame references, and index links without writes."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from autogui import DATA_DIR
from autogui.state.registry import OS_REGISTRY, BBOX_ACTIONS
from autogui.pipeline.step_utils import effective_actions, element_descs, frame_path, validate_plan
from PIL import Image


def check_integrity(data_dir, os_keys):
    root = Path(data_dir)
    issues = []

    def issue(path, category, detail=''):
        issues.append({'path': str(path.relative_to(root)), 'category': category, 'detail': detail})

    def read_object(path):
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(value, dict):
                raise ValueError('Expected a JSON object')
            return value
        except FileNotFoundError:
            issue(path, 'missing_file')
        except (OSError, ValueError):
            issue(path, 'invalid_json')
        return {}

    indexes = {}
    for kind in ('seeds', 'trajectories'):
        index_path = root / kind / '_index.json'
        indexes[kind] = read_object(index_path) if index_path.exists() else {}
    directories = {kind: {} for kind in indexes}
    for kind, prefix in (('seeds', 'seed_'), ('trajectories', 'traj_')):
        for os_key in os_keys:
            for directory in sorted((root / kind / os_key).glob(f'{prefix}*')):
                if directory.is_dir():
                    if directory.is_symlink():
                        issue(directory, 'linked_directory')
                        continue
                    directories[kind][(os_key, directory.name)] = directory
                    entry = indexes[kind].get(directory.name)
                    if not isinstance(entry, dict) or entry.get('os_key') != os_key:
                        issue(directory, 'missing_or_wrong_index_entry')
        for item_id, entry in indexes[kind].items():
            if not isinstance(entry, dict):
                issue(root / kind / '_index.json', 'invalid_index_entry', item_id)
            elif not isinstance(entry.get('os_key'), str) or entry['os_key'] not in OS_REGISTRY:
                issue(root / kind / '_index.json', 'unknown_platform', item_id)
            elif entry.get('os_key') in os_keys and (entry['os_key'], item_id) not in directories[kind]:
                issue(root / kind / '_index.json', 'indexed_directory_missing', item_id)
        ids = [key[1] for key in directories[kind]]
        for item_id in set(ids):
            if ids.count(item_id) > 1:
                issue(root / kind, 'duplicate_id', item_id)
    if not any(directories.values()):
        issue(root, 'no_data_found')

    def inspect_image(path, metadata):
        if path.is_symlink():
            issue(path, 'linked_frame')
            return
        if not path.is_file():
            issue(path, 'missing_frame')
            return
        try:
            with Image.open(path) as im:
                size = metadata.get('image_size')
                if size and (not isinstance(size, str) or not re.fullmatch(r'[1-9]\d*x[1-9]\d*', size)):
                    issue(path, 'invalid_image_size')
                elif size and im.size != tuple(map(int, size.split('x'))):
                    issue(path, 'wrong_image_size')
                if im.format != 'PNG':
                    issue(path, 'wrong_image_format')
                im.verify()
            with Image.open(path) as im:
                im.load()
        except (OSError, ValueError, SyntaxError):
            issue(path, 'invalid_image')

    backrefs = {}
    seeds_without_trajectories = 0
    for key, directory in directories['seeds'].items():
        seed = read_object(directory / 'seed.json')
        if seed.get('seed_id') != key[1] or seed.get('os_key') != key[0]:
            issue(directory / 'seed.json', 'identity_mismatch')
        inspect_image(directory / 'initial.png', seed)
        links = read_object(directory / 'trajectories.json').get('trajectory_ids')
        if not isinstance(links, list) or any(not isinstance(item, str) for item in links):
            issue(directory / 'trajectories.json', 'invalid_backrefs')
            links = []
        backrefs[key] = links
        if len(set(links)) != len(links):
            issue(directory / 'trajectories.json', 'duplicate_backrefs')
        seeds_without_trajectories += not links
        for tid in links:
            entry = indexes['trajectories'].get(tid)
            if (key[0], tid) not in directories['trajectories'] or not isinstance(entry, dict) or entry.get('seed_id') != key[1]:
                issue(directory / 'trajectories.json', 'broken_trajectory_link', tid)

    for (os_key, tid), directory in directories['trajectories'].items():
        path = directory / 'meta.json'
        meta = read_object(path)
        if meta.get('trajectory_id') != tid or meta.get('os_key') != os_key:
            issue(path, 'identity_mismatch')
        sid = meta.get('seed_id')
        seed_key = (os_key, sid) if isinstance(sid, str) else None
        if seed_key not in backrefs:
            issue(path, 'seed_missing')
        elif tid not in backrefs[seed_key]:
            issue(path, 'seed_backref_missing')
        entry = indexes['trajectories'].get(tid)
        if isinstance(entry, dict) and entry.get('seed_id') != sid:
            issue(path, 'index_seed_mismatch')

        steps = meta.get('steps')
        if not isinstance(steps, list) or not steps or any(not isinstance(step, dict) for step in steps):
            issue(path, 'missing_or_invalid_steps')
            steps = []
        if [step.get('step') for step in steps] != list(range(1, len(steps) + 1)):
            issue(path, 'nonconsecutive_steps')
        if any(step.get('status') != 'success' for step in steps):
            issue(path, 'unfinished_steps')

        plan = meta.get('agent_plan') or meta.get('plan_raw') or {}
        actions = plan.get('actions') if isinstance(plan, dict) else None
        if not isinstance(actions, list) or not actions or any(not isinstance(a, dict) for a in actions):
            issue(path, 'missing_or_invalid_plan')
        else:
            # The renderer stops at the first answer, even if the plan continues.
            expected = effective_actions(plan)
            try:
                validate_plan(dict(plan, actions=expected), os_key)
            except ValueError:
                issue(path, 'invalid_plan_action')
            if len(steps) != len(expected):
                issue(path, 'incomplete_plan')
            if any(step.get('action') != item.get('action') for step, item in zip(steps, expected)):
                issue(path, 'action_plan_mismatch')

        references = {'obs_00.png'}
        previous = 'obs_00.png'
        for step in steps:
            if step.get('status') != 'success':
                continue
            action = step.get('action')
            verb = action.get('action') if isinstance(action, dict) else action
            descs = element_descs(step)
            if not isinstance(verb, str):
                issue(path, 'invalid_step_action', str(step.get('step')))
            if isinstance(verb, str) and verb in BBOX_ACTIONS and not descs:
                issue(path, 'missing_target_description', str(step.get('step')))
            boxes = step.get('boxes') or []
            if descs and (not isinstance(boxes, list) or len(boxes) != len(descs)):
                issue(path, 'missing_grounding_boxes', str(step.get('step')))
            if verb == 'answer' and step.get('obs_frame') != previous:
                issue(path, 'terminal_frame_mismatch')
            if verb != 'answer' and step.get('obs_frame') == previous:
                issue(path, 'unchanged_frame_reference')
            if not descs and step.get('act_frame') != previous:
                issue(path, 'action_frame_mismatch')
            if descs and step.get('act_frame') == previous:
                issue(path, 'missing_annotation_frame')
            for field in ('obs_frame', 'act_frame'):
                name = step.get(field)
                try:
                    frame_path(directory, name)
                except ValueError:
                    issue(path, 'invalid_frame_reference', f"step {step.get('step')}: {field}")
                else:
                    references.add(name)
            previous = step.get('obs_frame') or previous
        for name in sorted(references):
            inspect_image(directory / name, meta)
        for frame in sorted(directory.glob('*.png')):
            if frame.name not in references:
                issue(frame, 'unreferenced_frame')

    return {'seeds': len(directories['seeds']), 'trajectories': len(directories['trajectories']),
            'seeds_without_trajectories': seeds_without_trajectories, 'issues': issues}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--os', nargs='+', choices=list(OS_REGISTRY), default=list(OS_REGISTRY))
    parser.add_argument('--data-dir', type=Path, default=Path(DATA_DIR))
    parser.add_argument('--json', action='store_true', help='Print the complete report as JSON')
    args = parser.parse_args(argv)
    if not args.data_dir.is_dir():
        parser.error('No data directory found; generate data first')
    report = check_integrity(args.data_dir, args.os)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Seeds: {report['seeds']}; trajectories: {report['trajectories']}")
        print(f"Seeds without trajectories: {report['seeds_without_trajectories']}")
        for item in report['issues']:
            print(f"{item['path']}: {item['category']} {item['detail']}".rstrip())
        print(f"Integrity issues: {len(report['issues'])}")
    return int(bool(report['issues']))


if __name__ == '__main__':
    raise SystemExit(main())

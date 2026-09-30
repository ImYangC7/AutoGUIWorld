# -*- coding: utf-8 -*-
"""Shared action-target and observation-frame helpers for generation and QC.

Three concerns, one source of truth each:

  1. element_descs(step_or_action)  -> list[str]
     WHICH element description(s) a step needs a box for. Pointing actions
     (BBOX_ACTIONS) give one; drag gives two (from + to). The number of descs is
     exactly n_boxes. Works on BOTH shapes seen in the data:
       - a planned action  (from/to/target at the top level), and
       - a rendered step     (action nested under 'action', from/to inside it),
     via a two-level lookup (nested action first, then top level).

  2. prev_obs_name(meta, step_no)   -> str
     The act frame of step k is drawn on the BEFORE-action observation: the obs of
     the most recent SUCCESSFUL step before k (the pipeline's `prev_obs`). Not
     obs_{k-1} literally, because a middle error step leaves a gap. Falls back to
     'obs_00.png' (seed initial frame).

  3. norm_step(x)                   -> int
     step numbers are int in some metas, str in others (legacy). Always compare as
     int to avoid 'int < str' TypeErrors.
"""
import copy
import math
from pathlib import Path

from autogui.state.registry import ACTION_SPACES, OS_REGISTRY, BBOX_ACTIONS, DRAG_ACTIONS

INITIAL_OBS = 'obs_00.png'


def frame_path(directory, name):
    """Resolve a frame filename within one trajectory directory."""
    if not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name or not name.endswith('.png'):
        raise ValueError('Invalid or missing frame filename')
    path = Path(directory) / name
    if path.is_symlink():
        raise ValueError('Frame must be stored inside its trajectory directory')
    return path


def norm_step(x):
    """Normalize a step number to int (metas mix int and str). None stays None."""
    return None if x is None else int(x)


def _action_name(obj):
    """The action verb, whether obj is a rendered step (action nested) or a raw
    plan action (action is the verb string or the dict itself)."""
    if not isinstance(obj, dict):
        return None
    a = obj.get('action')
    if isinstance(a, dict):
        return a.get('action')
    if isinstance(a, str):
        return a
    return None


def _lookup(obj, key):
    """Two-level lookup: nested action dict first, then the top level. Covers both
    rendered steps (from/to inside 'action') and raw plan actions (top level)."""
    a = obj.get('action')
    if isinstance(a, dict) and a.get(key):
        return a.get(key)
    return obj.get(key)


def element_descs(step_or_action):
    """Element description(s) to ground for this step/action, in box order.

    drag  -> [from_element (or target_element), to_element]
    bbox  -> [target_element (or action.element)]
    other -> []
    Empty descriptions are dropped, so len(result) == the real box count.
    """
    name = _action_name(step_or_action)
    if not isinstance(name, str):
        return []
    if name in DRAG_ACTIONS:
        descs = [_lookup(step_or_action, 'from_element') or _lookup(step_or_action, 'target_element'),
                 _lookup(step_or_action, 'to_element')]
    elif name in BBOX_ACTIONS:
        a = step_or_action.get('action')
        elem = _lookup(step_or_action, 'target_element') or (a.get('element') if isinstance(a, dict) else None)
        descs = [elem]
    else:
        descs = []
    return [d for d in descs if d]


def validate_plan(plan, os_key):
    """Validate required action fields and normalize top-level pointing targets."""
    if not isinstance(plan, dict) or not isinstance(plan.get('actions'), list):
        raise ValueError('Planner must return an object with an actions list')
    plan = copy.deepcopy(plan)
    allowed = {a['action'] for a in ACTION_SPACES[OS_REGISTRY[os_key]['action_space']]['actions']}
    for number, step in enumerate(plan['actions'], 1):
        if not isinstance(step, dict) or type(step.get('step')) is not int or step['step'] != number:
            raise ValueError('Planner steps must be consecutive integers starting at 1')
        action = step.get('action')
        if not isinstance(action, dict) or not isinstance(action.get('action'), str) or action['action'] not in allowed:
            raise ValueError('Planner returned an unsupported action object')
        name = action['action']
        required = []
        if name in BBOX_ACTIONS:
            targets = element_descs(step)
            count = 2 if name in DRAG_ACTIONS else 1
            if len(targets) != count or any(not isinstance(t, str) or not t.strip() for t in targets):
                raise ValueError('Pointing actions require concrete target descriptions')
            if count == 2:
                action['from_element'], action['to_element'] = targets
            else:
                action['element'] = targets[0]
        elif name == 'type_text':
            required = ['text']
        elif name == 'key_press':
            required = ['key']
        elif name == 'hotkey':
            keys = action.get('keys')
            if keys is None and isinstance(action.get('value'), str):
                keys = action['value'].split('+')
                action['keys'] = keys
            if not isinstance(keys, list) or not keys or any(not isinstance(k, str) or not k.strip() for k in keys):
                raise ValueError('Hotkeys require a nonempty list of key names')
        elif name == 'scroll':
            if action.get('value') not in ('up', 'down'):
                raise ValueError('Scroll direction must be up or down')
        elif name == 'answer':
            if action.get('status') not in ('DONE', 'FAIL'):
                raise ValueError('Answer status must be DONE or FAIL')
            required = ['text']
        if any(not isinstance(action.get(k), str) or not action[k].strip() for k in required):
            raise ValueError(f'{name} requires nonempty text parameters')
        for key in ('duration', 'amount'):
            if key in action and (type(action[key]) not in (int, float) or not math.isfinite(action[key]) or action[key] < 0):
                raise ValueError('Action timing and amounts must be finite and nonnegative')
    return plan


def effective_actions(plan):
    """Actions through the first terminal answer, including that answer."""
    actions = plan.get('actions') or []
    for i, step in enumerate(actions):
        if _action_name(step) == 'answer':
            return actions[:i + 1]
    return actions


def trajectory_complete(meta):
    """Whether all effective planned steps finished with aligned actions."""
    plan = meta.get('agent_plan') or meta.get('plan_raw') or {}
    steps = meta.get('steps') or []
    if not isinstance(plan, dict) or not isinstance(plan.get('actions'), list) or not isinstance(steps, list):
        return False
    actions = effective_actions(plan)
    return bool(actions) and len(steps) == len(actions) and all(
        isinstance(step, dict) and isinstance(action, dict) and
        step.get('step') == action.get('step') and step.get('action') == action.get('action') and
        step.get('status') == 'success' and bool(step.get('obs_frame'))
        for step, action in zip(steps, actions))


def prev_obs_name(meta, step_no):
    """Base frame for step_no's act = obs of the most recent SUCCESSFUL step before
    it (the pipeline's prev_obs). 'obs_00.png' if there is none."""
    step_no = norm_step(step_no)
    prev, best = INITIAL_OBS, -1
    for s in meta.get('steps', []):
        k = norm_step(s.get('step'))
        if k is None or k >= step_no:
            continue
        if s.get('status') == 'success' and s.get('obs_frame') and k > best:
            best, prev = k, s['obs_frame']
    return prev

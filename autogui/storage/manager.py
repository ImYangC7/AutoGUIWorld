# -*- coding: utf-8 -*-
"""Seed and Trajectory storage / lifecycle manager.

Layout:
    data/
    ├── seeds/
    │   ├── _index.json
    │   └── <os_key>/seed_001/
    │       ├── seed.json
    │       ├── initial.png
    │       └── trajectories.json
    ├── trajectories/
    │   ├── _index.json
    │   └── <os_key>/traj_001/
    │       ├── meta.json
    │       ├── obs_00.png  (copy of seed's initial.png)
    │       └── obs_01.png / act_01.png ...
    ├── task_registries/  (per-OS task dedup)
    └── _cost_log.json
"""

import json
import os
import re
import shutil
import threading
from datetime import datetime

from autogui import DATA_DIR
from autogui.utils.jsonio import atomic_write_json, atomic_write_bytes
from autogui.state.registry import OS_REGISTRY
from autogui.pipeline.step_utils import trajectory_complete

SEEDS_DIR = os.path.join(DATA_DIR, 'seeds')
TRAJ_DIR = os.path.join(DATA_DIR, 'trajectories')
TASK_REG_DIR = os.path.join(DATA_DIR, 'task_registries')

# Guards id allocation + dir creation + index/back-ref writes so concurrent
# trajectory workers never collide on the same id or corrupt _index.json.
_STORE_LOCK = threading.RLock()

SEED_INDEX_PATH = os.path.join(SEEDS_DIR, '_index.json')
TRAJ_INDEX_PATH = os.path.join(TRAJ_DIR, '_index.json')


def _ensure_dirs():
    os.makedirs(SEEDS_DIR, exist_ok=True)
    os.makedirs(TRAJ_DIR, exist_ok=True)
    os.makedirs(TASK_REG_DIR, exist_ok=True)


def _load_index(path):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            value = json.load(f)
        if not isinstance(value, dict):
            raise ValueError('Index must be a JSON object')
        return value
    return {}


def _save_index(path, data):
    atomic_write_json(path, data)


# === ID generation (sequential) ===

def _scan_ids(base, prefix):
    """All item dir names under base, scanning the per-OS subfolders.

    Layout is base/<os_key>/<prefix_NNN>. IDs are globally unique across OSes,
    so we flatten one level. Tolerates stray dirs that are not os-subfolders.
    """
    out = []
    if not os.path.isdir(base):
        return out
    for os_key in os.listdir(base):
        sub = os.path.join(base, os_key)
        if not os.path.isdir(sub):
            continue
        out.extend(d for d in os.listdir(sub) if re.fullmatch(re.escape(prefix) + r'\d+', d) and os.path.isdir(os.path.join(sub, d)))
    return out


def _resolve_dir(base, item_id):
    """Find an existing item dir under base/<os_key>/<item_id> (lookup path).

    Returns the path if found; otherwise returns the legacy flat path
    base/<item_id> so callers still get a sensible (possibly missing) path.
    """
    matches = []
    for os_key in os.listdir(base) if os.path.isdir(base) else []:
        cand = os.path.join(base, os_key, item_id)
        if os.path.isdir(cand):
            matches.append(cand)
    if len(matches) > 1:
        raise ValueError('Duplicate data ID across platforms')
    if matches:
        return matches[0]
    return os.path.join(base, item_id)


def _validate_location(item_id, prefix, os_key):
    if not isinstance(item_id, str) or not re.fullmatch(prefix + r'[A-Za-z0-9_-]+', item_id):
        raise ValueError('Invalid data ID')
    if os_key is not None and os_key not in OS_REGISTRY:
        raise ValueError('Unknown platform')


def next_seed_id():
    """Return next seed id like 'seed_001' (globally unique across OSes)."""
    _ensure_dirs()
    ids = _scan_ids(SEEDS_DIR, 'seed_')
    ids.extend(_load_index(SEED_INDEX_PATH))
    nums = [int(re.search(r'seed_(\d+)', d).group(1)) for d in ids if re.search(r'seed_(\d+)', d)]
    next_n = max(nums) + 1 if nums else 1
    return f'seed_{next_n:03d}'


def next_trajectory_id():
    """Return next trajectory id like 'traj_001' (globally unique across OSes)."""
    _ensure_dirs()
    ids = _scan_ids(TRAJ_DIR, 'traj_')
    ids.extend(_load_index(TRAJ_INDEX_PATH))
    nums = [int(re.search(r'traj_(\d+)', d).group(1)) for d in ids if re.search(r'traj_(\d+)', d)]
    next_n = max(nums) + 1 if nums else 1
    return f'traj_{next_n:03d}'


def reserve_trajectory_id(os_key):
    """Atomically allocate a fresh trajectory id AND claim its directory.

    Thread-safe: holding _STORE_LOCK across id-pick + mkdir closes the race where
    two workers read the same max id before either creates its dir. The created
    dir (under the os_key subfolder) is what makes next_trajectory_id() see it
    as taken.
    """
    with _STORE_LOCK:
        _ensure_dirs()
        traj_id = next_trajectory_id()
        os.makedirs(trajectory_dir(traj_id, os_key), exist_ok=False)
        return traj_id


def reserve_seed_id(os_key):
    """Atomically allocate a fresh seed id AND claim its directory.

    Seed counterpart of reserve_trajectory_id: holding _STORE_LOCK across
    id-pick + mkdir closes the race where concurrent workers read the same max
    id. The created dir (base/<os_key>/<seed_id>) makes next_seed_id() see it as
    taken. save_seed() later writes into this same dir (exist_ok=True).
    """
    with _STORE_LOCK:
        _ensure_dirs()
        seed_id = next_seed_id()
        os.makedirs(seed_dir(seed_id, os_key), exist_ok=False)
        return seed_id



# === Seed CRUD ===

def seed_dir(seed_id, os_key=None):
    """Path to a seed dir. With os_key, build base/<os_key>/<seed_id> (for
    creation); without it, resolve the existing dir across OS subfolders."""
    _validate_location(seed_id, 'seed_', os_key)
    if os_key:
        return os.path.join(SEEDS_DIR, os_key, seed_id)
    return _resolve_dir(SEEDS_DIR, seed_id)


def save_seed(seed_id, seed_data, initial_png_bytes):
    """Persist a new seed with its initial screenshot.

    Args:
        seed_id: e.g. 'seed_001'
        seed_data: dict with os_key, aesthetic, env_state, blockers, global_state, image_size
        initial_png_bytes: the rendered initial.png bytes
    """
    sd = seed_dir(seed_id, seed_data['os_key'])
    os.makedirs(sd, exist_ok=True)
    if os.path.exists(os.path.join(sd, 'seed.json')):
        raise FileExistsError('Seed already exists; create a new seed ID')

    # Add timestamp
    seed_data = dict(seed_data)
    seed_data['seed_id'] = seed_id
    seed_data['created_at'] = datetime.now().isoformat(timespec='seconds')

    initial_path = os.path.join(sd, 'initial.png')
    atomic_write_bytes(initial_path, initial_png_bytes)

    # Empty trajectories back-ref
    atomic_write_json(os.path.join(sd, 'trajectories.json'), {'trajectory_ids': []})
    atomic_write_json(os.path.join(sd, 'seed.json'), seed_data)

    # Update central index (read-modify-write under the lock so concurrent
    # seed workers don't clobber each other's entries in _index.json).
    with _STORE_LOCK:
        idx = _load_index(SEED_INDEX_PATH)
        idx[seed_id] = {
            'os_key': seed_data['os_key'],
            'created_at': seed_data['created_at'],
            'image_size': seed_data['image_size'],
            'blockers': seed_data.get('blockers', []),
            'aesthetic': seed_data.get('aesthetic', {}),
        }
        _save_index(SEED_INDEX_PATH, idx)

    return sd


def load_seed(seed_id):
    """Load seed metadata and return as dict."""
    sd = seed_dir(seed_id)
    seed_path = os.path.join(sd, 'seed.json')
    if not os.path.exists(seed_path):
        raise FileNotFoundError(f'Seed not found: {seed_id} at {seed_path}')
    with open(seed_path, encoding='utf-8') as f:
        data = json.load(f)
    data['_dir'] = sd
    data['_initial_png'] = os.path.join(sd, 'initial.png')
    return data


def list_seeds(os_key=None):
    """Return [(seed_id, metadata)] from the index, optionally filtered by os."""
    idx = _load_index(SEED_INDEX_PATH)
    items = sorted(idx.items())
    if os_key:
        items = [(sid, m) for sid, m in items if m.get('os_key') == os_key]
    return items


# === Trajectory CRUD ===

def trajectory_dir(traj_id, os_key=None):
    """Path to a trajectory dir. With os_key, build base/<os_key>/<traj_id> (for
    creation); without it, resolve the existing dir across OS subfolders."""
    _validate_location(traj_id, 'traj_', os_key)
    if os_key:
        return os.path.join(TRAJ_DIR, os_key, traj_id)
    return _resolve_dir(TRAJ_DIR, traj_id)


def init_trajectory(traj_id, seed_id, task_description, meta_extra=None):
    """Create a trajectory directory, copy seed's initial.png as obs_00.png
    (the first clean observation in the obs chain).

    Returns the trajectory directory path.
    """
    seed = load_seed(seed_id)
    td = trajectory_dir(traj_id, seed['os_key'])
    os.makedirs(td, exist_ok=True)
    if os.path.exists(os.path.join(td, 'meta.json')):
        raise FileExistsError('Trajectory already exists')

    # Copy initial as obs_00.png (root of the clean observation chain)
    shutil.copy(seed['_initial_png'], os.path.join(td, 'obs_00.png'))

    meta = {
        'trajectory_id': traj_id,
        'seed_id': seed_id,
        'os_key': seed['os_key'],
        'task_description': task_description,
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'image_size': seed['image_size'],
        'aesthetic': seed.get('aesthetic'),
        'env_state': seed.get('env_state'),
        'blockers': seed.get('blockers', []),
    }
    if meta_extra:
        if set(meta_extra) & set(meta):
            raise ValueError('Extra metadata cannot override trajectory identity or seed fields')
        meta.update(meta_extra)
    atomic_write_json(os.path.join(td, 'meta.json'), meta)

    return td


def finalize_trajectory(traj_id, plan, step_results, extra=None):
    """Update trajectory's meta.json with the generated plan + per-step results
    (obs/act frames), register back-ref to seed, and add to the global index.
    """
    td = trajectory_dir(traj_id)
    meta_path = os.path.join(td, 'meta.json')
    with open(meta_path, encoding='utf-8') as f:
        meta = json.load(f)

    meta['agent_plan'] = plan
    meta['steps'] = step_results
    if extra:
        if set(extra) & {'seed_id', 'trajectory_id', 'os_key', 'agent_plan', 'steps'}:
            raise ValueError('Extra metadata cannot override trajectory identity or results')
        meta.update(extra)
    meta['status'] = 'complete' if trajectory_complete(meta) else 'partial'

    atomic_write_json(meta_path, meta)

    # Update seed back-ref + central index under the lock (concurrent-safe).
    seed_id = meta['seed_id']
    with _STORE_LOCK:
        sd = seed_dir(seed_id)
        back_path = os.path.join(sd, 'trajectories.json')
        if os.path.exists(back_path):
            with open(back_path, encoding='utf-8') as f:
                br = json.load(f)
        else:
            br = {'trajectory_ids': []}
        if traj_id not in br['trajectory_ids']:
            br['trajectory_ids'].append(traj_id)
        atomic_write_json(back_path, br)

        # Update central trajectory index
        idx = _load_index(TRAJ_INDEX_PATH)
        idx[traj_id] = {
            'seed_id': seed_id,
            'os_key': meta['os_key'],
            'task_description': meta['task_description'],
            'created_at': meta['created_at'],
            'steps': len(step_results),
            'status': meta['status'],
        }
        _save_index(TRAJ_INDEX_PATH, idx)


def list_trajectories(seed_id=None, os_key=None):
    """List trajectories, optionally filtered by seed or os."""
    idx = _load_index(TRAJ_INDEX_PATH)
    items = sorted(idx.items())
    if seed_id:
        items = [(tid, m) for tid, m in items if m.get('seed_id') == seed_id]
    if os_key:
        items = [(tid, m) for tid, m in items if m.get('os_key') == os_key]
    return items


# === Task registry path (per-OS, moved to data/task_registries/) ===

def task_registry_path(os_key):
    if os_key not in OS_REGISTRY:
        raise ValueError('Unknown platform')
    _ensure_dirs()
    return os.path.join(TASK_REG_DIR, f'{os_key}.json')

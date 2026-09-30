# -*- coding: utf-8 -*-
"""Red bounding-box extraction for generated step images.

Step images carry a red rectangular outline marking the action target. This
module recovers that box (top-left / bottom-right corners + center) from the
rendered PNG, since the action's `element` field is only a text description and
the real spatial location lives in the red box.

No OpenCV dependency — uses numpy + scipy.ndimage only.

Usage:
    from autogui.analysis.redbox import extract_red_box, extract_trajectory_boxes
    box = extract_red_box("data/trajectories/windows11/traj_006/act_01.png")
    # -> {'found': True, 'top_left': (x0,y0), 'bottom_right': (x1,y1),
    #     'center': (cx,cy), 'width': w, 'height': h, 'confidence': 0.93}
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from autogui import DATA_DIR
from autogui.pipeline.step_utils import frame_path, element_descs


def _red_mask(rgb):
    """Boolean mask of saturated-red pixels (the box outline).

    Tuned to keep a pure red 2-4px stroke while rejecting warm wallpapers /
    UI accents that are merely reddish.
    """
    r = rgb[:, :, 0].astype(int)
    g = rgb[:, :, 1].astype(int)
    b = rgb[:, :, 2].astype(int)
    return (r > 150) & (g < 80) & (b < 80) & (r - g > 90) & (r - b > 90)


def _frame_score(comp_mask, bbox):
    """How 'rectangle-outline-like' a component is, in [0,1].

    A hollow rectangle's pixels sit on its bbox perimeter, so pixel_count
    should be close to perimeter * stroke_thickness and the bbox should be
    largely empty inside. We score by perimeter coverage.
    """
    minr, minc, maxr, maxc = bbox
    h = maxr - minr + 1
    w = maxc - minc + 1
    if h < 8 or w < 8:
        return 0.0
    sub = comp_mask[minr:maxr + 1, minc:maxc + 1]
    # Fraction of each border line that is actually painted red.
    top = sub[0, :].mean()
    bottom = sub[-1, :].mean()
    left = sub[:, 0].mean()
    right = sub[:, -1].mean()
    edge_cov = (top + bottom + left + right) / 4.0
    # Penalize components that fill their bbox (solid blobs, not outlines).
    fill_ratio = sub.mean()
    hollow = 1.0 - min(fill_ratio, 1.0)
    return float(edge_cov * 0.7 + hollow * 0.3)


def _box_dict(bbox, score, W, H):
    minr, minc, maxr, maxc = bbox
    x0, y0, x1, y1 = int(minc), int(minr), int(maxc), int(maxr)
    return {
        'found': True,
        'top_left': (x0, y0),
        'bottom_right': (x1, y1),
        'center': ((x0 + x1) // 2, (y0 + y1) // 2),
        'width': x1 - x0,
        'height': y1 - y0,
        'confidence': round(float(score), 3),
        'image_size': (W, H),
    }


def _find_boxes(rgb, min_side, min_score):
    """Return all qualifying red-frame components as (bbox, score), sorted by
    score descending. bbox is (minr, minc, maxr, maxc)."""
    H, W = rgb.shape[:2]
    mask = _red_mask(rgb)
    if mask.sum() < 4 * min_side:
        return [], (W, H)
    labels, n = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return [], (W, H)
    cands = []
    for idx in range(1, n + 1):
        comp = labels == idx
        ys, xs = np.where(comp)
        if xs.size < 2 * min_side:
            continue
        bbox = (ys.min(), xs.min(), ys.max(), xs.max())
        minr, minc, maxr, maxc = bbox
        if (maxr - minr) < min_side or (maxc - minc) < min_side:
            continue
        score = _frame_score(comp, bbox)
        if score >= min_score:
            cands.append((bbox, score))
    cands.sort(key=lambda t: t[1], reverse=True)
    return cands, (W, H)


def _load_rgb(image):
    if isinstance(image, (str, Path)):
        with Image.open(image) as source:
            return np.array(source.convert('RGB'))
    return np.asarray(image)[:, :, :3]


def extract_red_box(image, min_side=20, min_score=0.35):
    """Extract THE single best red bounding box from a step image.

    Returns dict: found, top_left, bottom_right, center, width, height,
    confidence, image_size.
    """
    rgb = _load_rgb(image)
    cands, (W, H) = _find_boxes(rgb, min_side, min_score)
    empty = {
        'found': False, 'top_left': None, 'bottom_right': None,
        'center': None, 'width': None, 'height': None,
        'confidence': 0.0, 'image_size': (W, H),
    }
    if not cands:
        return empty
    bbox, score = cands[0]
    return _box_dict(bbox, score, W, H)


def extract_red_boxes(image, max_boxes=2, min_side=20, min_score=0.35,
                      iou_dedup=0.6):
    """Extract up to `max_boxes` red bounding boxes (for multi-box actions
    like drag). Returns dict:
        found: bool (at least one box)
        count: int number of boxes returned
        boxes: list of box dicts (each like extract_red_box output)
        image_size: (W, H)
    Boxes are the top-`max_boxes` highest-scoring components, with near-duplicate
    overlaps removed (IoU > iou_dedup).
    """
    rgb = _load_rgb(image)
    cands, (W, H) = _find_boxes(rgb, min_side, min_score)

    def iou(a, b):
        ar0, ac0, ar1, ac1 = a
        br0, bc0, br1, bc1 = b
        ir0, ic0 = max(ar0, br0), max(ac0, bc0)
        ir1, ic1 = min(ar1, br1), min(ac1, bc1)
        ih, iw = max(0, ir1 - ir0), max(0, ic1 - ic0)
        inter = ih * iw
        if inter == 0:
            return 0.0
        area_a = (ar1 - ar0) * (ac1 - ac0)
        area_b = (br1 - br0) * (bc1 - bc0)
        return inter / float(area_a + area_b - inter)

    kept = []
    for bbox, score in cands:
        if any(iou(bbox, kb) > iou_dedup for kb, _ in kept):
            continue
        kept.append((bbox, score))
        if len(kept) >= max_boxes:
            break

    boxes = [_box_dict(b, s, W, H) for b, s in kept]
    return {
        'found': len(boxes) > 0,
        'count': len(boxes),
        'boxes': boxes,
        'image_size': (W, H),
    }



def extract_trajectory_boxes(traj_dir):
    """Extract red boxes from a trajectory's act frames, routing by box count.

    Reads meta.json's `steps`; for each step:
      - n_boxes == 2 (drag)      -> extract TWO boxes from its act frame
      - n_boxes == 1 (pointing)  -> extract ONE box from its act frame
      - n_boxes == 0 (other)     -> no act frame to check; reported as expected=0

    Returns list of (act_filename, box_dict). box_dict carries 'expected' (0/1/2);
    multi-box frames add a 'boxes' list, single-box frames the flat fields, and
    no-box steps carry skipped=True.
    """
    meta_path = os.path.join(traj_dir, 'meta.json')
    with open(meta_path, encoding='utf-8') as stream:
        meta = json.load(stream)
    if not isinstance(meta, dict):
        raise ValueError('Trajectory metadata must be an object')
    steps = meta.get('steps')
    if not isinstance(steps, list) or not steps or any(not isinstance(s, dict) for s in steps):
        raise ValueError('Missing or invalid trajectory steps')

    out = []
    for s in steps:
        n = s.get('n_boxes', 0)
        if type(n) is not int or not 0 <= n <= 2:
            raise ValueError('Invalid annotation count')
        n = max(len(element_descs(s)), n)
        act_frame = s.get('act_frame')
        # Non-pointing step: its act frame is just the before-observation (no box).
        if n == 0:
            out.append((act_frame, {
                'found': False, 'skipped': True, 'expected': 0,
                'top_left': None, 'bottom_right': None, 'center': None,
                'width': None, 'height': None, 'confidence': 0.0,
            }))
            continue
        try:
            path = frame_path(traj_dir, act_frame)
            if not act_frame.startswith('act_'):
                raise ValueError('Pointing action lacks annotation frame')
            res = extract_red_boxes(path, max_boxes=n)
            res['expected'] = n
        except (ValueError, OSError):
            res = {'found': False, 'count': 0, 'boxes': [], 'expected': n, 'error': 'Missing or invalid annotation image'}
        out.append((act_frame, res))
    return out


def stability_report(traj_dir):
    """Check red-box detection per trajectory, action-type aware.

    A frame is 'matched' when the number of detected boxes equals what its
    action implies (1 for pointing actions, 2 for drag). Box-free frames are
    skipped. Geometry stats are aggregated over all detected boxes (single- and
    multi-box frames alike).
    """
    results = extract_trajectory_boxes(traj_dir)
    considered = [(fn, b) for fn, b in results if not b.get('skipped')]

    def n_found(b):
        return b.get('count', 1 if b.get('found') else 0)

    matched = [b for _, b in considered if n_found(b) == b.get('expected', 1)]
    rate = len(matched) / len(considered) if considered else 0.0

    # Collect every detected box (flatten multi-box frames) for geometry stats.
    all_boxes = []
    for _, b in considered:
        if 'boxes' in b:
            all_boxes.extend(b['boxes'])
        elif b.get('found'):
            all_boxes.append(b)

    report = {
        'trajectory': Path(traj_dir).name,
        'steps': len(results),
        'boxed_steps': len(considered),
        'skipped_boxless': len(results) - len(considered),
        'matched_steps': len(matched),
        'match_rate': round(rate, 3),
        'total_boxes': len(all_boxes),
        'per_step': results,
    }
    if all_boxes:
        confs = np.array([b['confidence'] for b in all_boxes])
        report['confidence_mean'] = round(float(confs.mean()), 3)
        report['confidence_min'] = round(float(confs.min()), 3)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect red-box geometry in saved action frames.')
    parser.add_argument('path', nargs='?', type=Path, default=Path(DATA_DIR) / 'trajectories',
                        help='Image, trajectory folder, platform folder, or trajectory root')
    base = parser.parse_args(argv).path
    if not base.exists():
        parser.error(f'Path does not exist: {base}')
    if base.is_file():
        result = extract_red_box(base)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(not result['found'])
    else:
        trajectories = ([base] if (base / 'meta.json').is_file() else
                        sorted(path.parent for path in base.rglob('meta.json')
                               if path.parent.name.startswith('traj_')))
        if not trajectories:
            print('No trajectory metadata found.')
            return 1
        failures = 0
        for td in trajectories:
            try:
                rep = stability_report(td)
            except (ValueError, OSError, TypeError) as exc:
                print(f'{td.name}: invalid metadata ({type(exc).__name__})')
                failures += 1
                continue
            failures += rep['matched_steps'] != rep['boxed_steps']
            print(f"\n=== {rep['trajectory']}  match {rep['matched_steps']}/{rep['boxed_steps']} "
                  f"(rate={rep['match_rate']}, {rep['total_boxes']} boxes, "
                  f"skipped {rep['skipped_boxless']} box-free) ===")
            for fn, b in rep['per_step']:
                if b.get('skipped'):
                    print(f"  {fn}: (skipped — no box expected)")
                elif 'boxes' in b:  # multi-box (drag)
                    print(f"  {fn}: expected {b['expected']}, found {b['count']}")
                    for i, bx in enumerate(b['boxes']):
                        print(f"      box{i+1}: TL={bx['top_left']} BR={bx['bottom_right']} "
                              f"C={bx['center']} conf={bx['confidence']}")
                elif b['found']:
                    print(f"  {fn}: TL={b['top_left']} BR={b['bottom_right']} "
                          f"C={b['center']} conf={b['confidence']}")
                else:
                    print(f"  {fn}: (no box found)")
            if 'confidence_mean' in rep:
                print(f"  -> conf mean={rep['confidence_mean']} min={rep['confidence_min']}")
        return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())

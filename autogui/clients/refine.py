# -*- coding: utf-8 -*-
"""Approach A — point-to-box refinement via local CV (no extra model).

MAI-UI returns a center point; we snap a tight box to the real element extent
around that point using OpenCV flood-fill (color-region growth) plus an edge /
morphology fallback. If the recovered box looks implausible we keep the original
fixed-fraction box, so this never makes things worse than the baseline.

Public API:
    refine_box(image_path, center_xy, fallback_bbox) -> [x0, y0, x1, y1]
"""

import cv2
import numpy as np

Box = list[int]
Point = tuple[float, float] | list[float]


# Search window around the point (fraction of image w/h) — element must fit here.
_WIN_FRAC = (0.18, 0.14)
# Accepted refined-box size bounds (fraction of image) to reject runaway fills.
_MIN_FRAC = (0.01, 0.01)
_MAX_FRAC = (0.30, 0.12)
_FLOOD_TOL = 18   # per-channel color tolerance for flood fill


def _flood_box(img: np.ndarray, cx: int, cy: int) -> Box | None:
    """Flood-fill from (cx, cy) by color similarity; return filled bbox or None."""
    h, w = img.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    lo = (_FLOOD_TOL,) * 3
    hi = (_FLOOD_TOL,) * 3
    flags = 4 | (255 << 8) | cv2.FLOODFILL_FIXED_RANGE | cv2.FLOODFILL_MASK_ONLY
    cv2.floodFill(img.copy(), mask, (cx, cy), 0, lo, hi, flags)
    ys, xs = np.where(mask[1:-1, 1:-1] > 0)
    if len(xs) < 8:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def _edge_box(gray: np.ndarray, cx: int, cy: int) -> Box | None:
    """Edge + dilate + connected component containing (cx, cy); bbox or None."""
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(edges, connectivity=8)
    lbl = labels[cy, cx]
    if lbl == 0:  # point landed on background; pick nearest non-bg comp
        return None
    x, y, ww, hh, _ = stats[lbl]
    return [int(x), int(y), int(x + ww), int(y + hh)]


def refine_box(image_path: str, center_xy: Point, fallback_bbox: Box) -> Box:
    """Snap a tight box to the element under center_xy. Returns [x0,y0,x1,y1] px.

    Falls back to fallback_bbox when the refined box is missing or implausible.
    """
    img = cv2.imread(str(image_path))       # BGR
    if img is None:
        return fallback_bbox
    H, W = img.shape[:2]
    cx, cy = int(center_xy[0]), int(center_xy[1])
    cx = max(0, min(W - 1, cx)); cy = max(0, min(H - 1, cy))

    # crop a local search window so global structures don't bleed in
    wx, wy = max(1, int(_WIN_FRAC[0] * W)), max(1, int(_WIN_FRAC[1] * H))
    x0w, y0w = max(0, cx - wx), max(0, cy - wy)
    x1w, y1w = min(W, cx + wx), min(H, cy + wy)
    crop = img[y0w:y1w, x0w:x1w]
    lcx, lcy = cx - x0w, cy - y0w

    box = _flood_box(crop, lcx, lcy)
    if box is None:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        box = _edge_box(gray, lcx, lcy)
    if box is None:
        return fallback_bbox

    # back to full-image coords
    bx0, by0, bx1, by1 = box[0] + x0w, box[1] + y0w, box[2] + x0w, box[3] + y0w
    bw, bh = bx1 - bx0, by1 - by0

    # plausibility gates: must contain the point and be a sane size
    if not (bx0 <= cx <= bx1 and by0 <= cy <= by1):
        return fallback_bbox
    if not (_MIN_FRAC[0] * W <= bw <= _MAX_FRAC[0] * W):
        return fallback_bbox
    if not (_MIN_FRAC[1] * H <= bh <= _MAX_FRAC[1] * H):
        return fallback_bbox
    return [bx0, by0, bx1, by1]

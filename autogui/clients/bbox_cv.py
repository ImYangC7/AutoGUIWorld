# -*- coding: utf-8 -*-
"""Computer-vision helpers for extracting red annotation boxes."""

from pathlib import Path

Box = list[float]


def _bbox_center_xy(bbox: Box) -> tuple[float, float]:
    x1, y1, x2, y2 = [float(v) for v in bbox]
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def _bbox_iou(a: Box, b: Box) -> float:
    ax1, ay1, ax2, ay2 = [float(v) for v in a]
    bx1, by1, bx2, by2 = [float(v) for v in b]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def _expanded_bbox(bbox: Box, img_w: int, img_h: int, ratio: float = 0.75,
                   min_pad: float = 80) -> Box:
    x1, y1, x2, y2 = [float(v) for v in bbox]
    pad_x = max(float(min_pad), (x2 - x1) * float(ratio))
    pad_y = max(float(min_pad), (y2 - y1) * float(ratio))
    return [
        max(0.0, x1 - pad_x),
        max(0.0, y1 - pad_y),
        min(float(img_w), x2 + pad_x),
        min(float(img_h), y2 + pad_y),
    ]


def _candidates_from_mask(mask, img_w: int, img_h: int,
                          min_area_ratio: float = 0.00002, min_side: int = 8) -> list[dict]:
    import cv2

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    min_area = max(20, int(img_w * img_h * min_area_ratio))
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        if bw < min_side or bh < min_side:
            continue
        if bw >= img_w * 0.98 and bh >= img_h * 0.98:
            continue
        candidates.append({
            'area': float(area),
            'bbox': [int(x), int(y), int(x + bw), int(y + bh)],
            'image_size': [int(img_w), int(img_h)],
        })
    return candidates


def _choose_candidate(candidates: list[dict], hint_bbox: Box | None = None,
                      require_hint: bool = False) -> list[int] | None:
    if not candidates:
        return None
    if hint_bbox and len(hint_bbox) == 4:
        img_w, img_h = candidates[0]['image_size']
        search_bbox = _expanded_bbox(hint_bbox, img_w, img_h)
        hx, hy = _bbox_center_xy(hint_bbox)
        diag = max(1.0, (float(img_w) ** 2 + float(img_h) ** 2) ** 0.5)
        hinted = []
        for item in candidates:
            bbox = item['bbox']
            cx, cy = _bbox_center_xy(bbox)
            distance = ((cx - hx) ** 2 + (cy - hy) ** 2) ** 0.5 / diag
            near = _bbox_iou(bbox, search_bbox) > 0 or (search_bbox[0] <= cx <= search_bbox[2] and search_bbox[1] <= cy <= search_bbox[3])
            if near:
                item = dict(item)
                item['score'] = (_bbox_iou(bbox, hint_bbox) * 8.0) + (1.0 - min(distance, 1.0)) + min(item['area'] / max(1.0, img_w * img_h * 0.02), 1.0)
                hinted.append(item)
        if hinted:
            return max(hinted, key=lambda item: item['score'])['bbox']
        if require_hint:
            return None
    return max(candidates, key=lambda item: item['area'])['bbox']


def detect_new_red_bbox(reference_path: str | Path, annotated_path: str | Path,
                        min_area_ratio: float = 0.00002, min_side: int = 8,
                        hint_bbox: Box | None = None, require_hint: bool = False) -> list[int] | None:
    """Return the newly added red bbox by comparing clean before vs annotated.

    This is safer than scanning annotated.png alone because many real websites
    contain native red UI. Only saturated red pixels that changed from the clean
    reference are considered annotation candidates.
    """
    import cv2

    ref = cv2.imread(str(reference_path))
    ann = cv2.imread(str(annotated_path))
    if ref is None:
        raise RuntimeError(f'Failed to read image: {reference_path}')
    if ann is None:
        raise RuntimeError(f'Failed to read image: {annotated_path}')
    if ref.shape[:2] != ann.shape[:2]:
        raise RuntimeError(f'Image size mismatch for bbox delta detection: {reference_path} vs {annotated_path}')

    h, w = ann.shape[:2]
    hsv = cv2.cvtColor(ann, cv2.COLOR_BGR2HSV)
    red = cv2.inRange(hsv, (0, 120, 120), (10, 255, 255)) | cv2.inRange(hsv, (170, 120, 120), (180, 255, 255))
    changed = cv2.cvtColor(cv2.absdiff(ref, ann), cv2.COLOR_BGR2GRAY)
    _, changed = cv2.threshold(changed, 25, 255, cv2.THRESH_BINARY)
    candidates = _candidates_from_mask(red & changed, w, h, min_area_ratio=min_area_ratio, min_side=min_side)
    return _choose_candidate(candidates, hint_bbox=hint_bbox, require_hint=require_hint)

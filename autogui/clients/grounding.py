# -*- coding: utf-8 -*-
"""Act-frame annotation: locate target element(s) on a clean obs frame and draw
red bounding box(es) onto a pixel-identical copy.

Two halves (so the act frame's RENDERING can be swapped without changing the
LABELS — see autogui/clients/box_backends.py):
  - ground_boxes(obs, descs)        → box coords (the authoritative labels)
  - draw_boxes_pil(obs, act, boxes) → PIL overlay render (pixel-identical to obs)

Grounding chain (MAI-UI point → OmniParser box → CV refine → fixed box):
  1. MAI-UI (vision) returns the element's CENTER POINT (accurate localization).
  2. OmniParser (YOLOv8 icon detector) gives real element boxes; we pick the
     box that contains the point → true element extent.
  3. If OmniParser finds no containing box, a local CV flood-fill / edge pass
     snaps a box to the element under the point.
  4. If both fail, fall back to a fixed-fraction box around the point.

The PIL act frame equals the obs frame except for the added red box(es), so we
do NOT use image-edit (which repaints the scene); we draw with PIL.

For drag, two targets (source + destination) are located and boxed.
"""
import base64
import json
import io
import math
import os
import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from autogui.config import MAI_UI_URL, MAI_UI_MODEL, LOCATE_ANYTHING_URL, LOCATE_ANYTHING_URLS
from autogui.clients._http import make_session, api_error, check_status
from autogui.clients.refine import refine_box
from autogui.utils.cost import get_logger as get_cost_logger
from autogui.utils.jsonio import atomic_write_bytes

if TYPE_CHECKING:
    from autogui.clients.omni_detect import OmniDetector

_HTTP = make_session()

# Round-robin across the grounding instances (one per GPU). itertools.cycle +
# a lock gives a thread-safe rotating pick so 40 render workers spread their
# /ground calls evenly over all replicas instead of hammering one server.
import itertools as _itertools
import threading as _threading
_LA_CYCLE = _itertools.cycle(LOCATE_ANYTHING_URLS or [LOCATE_ANYTHING_URL])
_LA_LOCK = _threading.Lock()


def _next_la_url() -> str:
    with _LA_LOCK:
        return next(_LA_CYCLE)

# A box record is the uniform dict every grounder backend returns:
# {element, source, point_px, bbox_norm, bbox_px}.
BoxRecord = dict
Box = list[int]

_GROUND_SYSTEM = (
    'You are a GUI grounding agent. \n'
    '## Task\n'
    "Given a screenshot and the user's grounding instruction. Your task is to "
    'accurately locate a UI element based on the user\'s instructions.\n'
    'First, you should carefully examine the screenshot and analyze the user\'s '
    'instructions,  translate the user\'s instruction into a effective reasoning '
    'process, and then provide the final coordinate.\n'
    '## Output Format\n'
    'Return a json object with a reasoning process in '
    '<grounding_think></grounding_think> tags, a [x,y] format coordinate within '
    '<answer></answer> XML tags:\n'
    '<grounding_think>...</grounding_think>\n'
    '<answer>\n{"coordinate": [x,y]}\n</answer>'
)

_BOX_COLOR = (255, 0, 0)
_BOX_WIDTH = 3
# fallback half-size around the grounded point (fraction of image w, h) when
# neither OmniParser nor CV refine yields a usable box.
_BOX_HALF_FRAC = (0.035, 0.025)

# Lazy OmniParser singleton. Set AUTOGUI_OMNI=0 to disable.
_OMNI = None
_OMNI_FAILED = False   # set once if construction raised, so we don't retry it
_OMNI_LOCK = threading.Lock()
_OMNI_DISABLED = os.environ.get('AUTOGUI_OMNI', '1') == '0'


def _get_omni() -> "OmniDetector | None":
    global _OMNI, _OMNI_FAILED
    if _OMNI_DISABLED or _OMNI_FAILED:
        return None
    if _OMNI is None:
        with _OMNI_LOCK:
            if _OMNI is None and not _OMNI_FAILED:   # double-checked: construct once
                try:
                    from autogui.clients.omni_detect import OmniDetector
                    device = int(os.environ.get('AUTOGUI_OMNI_DEVICE', '0'))
                    _OMNI = OmniDetector(device=device)
                except Exception as e:
                    print(f'OmniParser unavailable ({type(e).__name__}); using CV refinement')
                    _OMNI_FAILED = True
    return _OMNI


def _extract_point(text: str) -> list[float] | None:
    """Pull the [x, y] coordinate out of MAI-UI's <answer>{...}</answer> block."""
    m = re.search(r'<answer>(.*?)</answer>', text, re.DOTALL)
    chunk = m.group(1).strip() if m else text
    j = re.search(r'\{.*\}', chunk, re.DOTALL)
    if not j:
        return None
    try:
        coord = json.loads(j.group(0)).get('coordinate')
        if isinstance(coord, list) and len(coord) == 2 and all(type(v) in (int, float) and math.isfinite(v) for v in coord):
            return [float(coord[0]), float(coord[1])]
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
        print('MAI-UI returned an invalid point')
    return None


def ground_point(image_path: str | Path, element_desc: str, W: int, H: int) -> list[int] | None:
    """Return the element's center point in PIXELS (cx, cy) via MAI-UI, or None."""
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()
    body = {
        'model': MAI_UI_MODEL,
        'messages': [
            {'role': 'system', 'content': [{'type': 'text', 'text': _GROUND_SYSTEM}]},
            {'role': 'user', 'content': [
                {'type': 'text', 'text': element_desc + '\n'},
                {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_b64}'}},
            ]},
        ],
        'max_tokens': 2048,
        'temperature': 0.0,
        'top_p': 1.0,
        'seed': 42,
        'stream': False,
    }
    try:
        resp = _HTTP.post(MAI_UI_URL, headers={'Content-Type': 'application/json'},
                          json=body, timeout=120)
        check_status(resp, 'MAI-UI')
        result = resp.json()
    except Exception as e:
        raise RuntimeError(api_error('MAI-UI', e)) from None
    get_cost_logger().record('mai_ground', MAI_UI_MODEL, result)
    try:
        point = _extract_point(result['choices'][0]['message']['content'])
    except (KeyError, IndexError, TypeError):
        return None
    if point is None:
        return None
    # MAI-UI reports a 0–1000 normalized coordinate on each axis.
    nx, ny = point[0] / 1000.0, point[1] / 1000.0
    if not (0.0 <= nx <= 1.0 and 0.0 <= ny <= 1.0):
        return None
    return [min(W - 1, int(nx * W)), min(H - 1, int(ny * H))]


def _fixed_box(cx: int, cy: int, W: int, H: int) -> Box:
    hx, hy = max(1, int(_BOX_HALF_FRAC[0] * W)), max(1, int(_BOX_HALF_FRAC[1] * H))
    return [max(0, cx - hx), max(0, cy - hy), min(W - 1, cx + hx), min(H - 1, cy + hy)]


def _box_for_point(image_path: str | Path, cx: int, cy: int, W: int, H: int,
                   omni_boxes: list[Box] | None) -> tuple[Box, str]:
    """Chain: OmniParser box containing point → CV refine → fixed box."""
    fixed = _fixed_box(cx, cy, W, H)
    # 2) OmniParser: smallest detected box containing the point
    if omni_boxes:
        containing = [b for b in omni_boxes if b[0] <= cx <= b[2] and b[1] <= cy <= b[3]]
        if containing:
            return min(containing, key=lambda b: (b[2] - b[0]) * (b[3] - b[1])), 'omni'
    # 3) CV refine: snap a box to the element under the point
    cv = refine_box(image_path, [cx, cy], fixed)
    if cv != fixed:
        return cv, 'cv'
    # 4) fixed fallback
    return fixed, 'fixed'


def _box_record(desc: str, px: Box, W: int, H: int, source: str,
                point_px: list[int] | None = None) -> BoxRecord:
    """Uniform box record shared by every grounder backend."""
    return {
        'element': desc,
        'source': source,
        'point_px': point_px,
        'bbox_norm': [round(px[0] / W, 4), round(px[1] / H, 4),
                      round(px[2] / W, 4), round(px[3] / H, 4)],
        'bbox_px': [int(px[0]), int(px[1]), int(px[2]), int(px[3])],
    }


def _ground_boxes_mai_ui(obs_path: str | Path, element_descs: list[str],
                         W: int, H: int) -> list[BoxRecord]:
    """Original grounder: MAI-UI point → OmniParser box → CV refine → fixed box.

    OmniParser is detected ONCE per frame and shared across all descs.
    """
    omni = _get_omni()
    omni_boxes = omni.detect(obs_path) if omni else None

    boxes = []
    for desc in element_descs:
        pt = ground_point(obs_path, desc, W, H)
        if pt is None:
            continue
        px, source = _box_for_point(obs_path, pt[0], pt[1], W, H, omni_boxes)
        boxes.append(_box_record(desc, px, W, H, source, point_px=pt))
    return boxes


def _ground_boxes_gpt55(obs_path: str | Path, element_descs: list[str],
                        W: int, H: int) -> list[BoxRecord]:
    """GPT-5.5 vision grounder: ask GPT-5.5 to return the element bbox on the
    clean obs frame, then verify/refine it via a local PIL-draw + cv2 detection
    of the newly added red rectangle (so the recorded box matches what a renderer
    would actually draw, and native website red is filtered out).

    Same record shape as the MAI-UI grounder. Elements GPT-5.5 fails to locate
    are skipped (omitted), so the list may be shorter than element_descs.
    """
    from autogui.clients.llm import call_llm_vision
    from autogui.prompts.grounding_gpt55 import (
        GROUND_GPT55_SYSTEM, build_ground_gpt55_prompt,
    )
    from autogui.utils.jsonio import strip_json_fence

    boxes = []
    for desc in element_descs:
        prompt = build_ground_gpt55_prompt(
            element=desc, action_name='click', description='', image_size=f'{W}x{H}',
        )
        try:
            raw = call_llm_vision(GROUND_GPT55_SYSTEM, prompt,
                                  [('BEFORE clean pre-action screenshot', obs_path)])
            payload = json.loads(strip_json_fence(raw))
            bbox = payload.get('bbox')
            if not (isinstance(bbox, list) and len(bbox) == 4):
                continue
            hint = _clamp_box(bbox, W, H)
        except Exception as e:
            print(f'  ⚠️  GPT-5.5 grounding failed for {desc!r}: {e}')
            continue
        # Verify the suggested box by drawing it on a scratch copy and re-detecting
        # the new red rectangle (filters native red; snaps to what gets drawn).
        verified = _verify_box_with_cv2(obs_path, hint, W, H)
        px = verified or hint
        source = 'gpt55_cv2' if verified else 'gpt55'
        boxes.append(_box_record(desc, px, W, H, source))
    return boxes


def _clamp_box(box: list[float], W: int, H: int) -> Box:
    if not isinstance(box, (list, tuple)) or len(box) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in box):
        raise ValueError('Grounding box must contain four finite numbers')
    x1, y1, x2, y2 = box
    x1, x2 = sorted((max(0, min(x1, W - 1)), max(0, min(x2, W - 1))))
    y1, y2 = sorted((max(0, min(y1, H - 1)), max(0, min(y2, H - 1))))
    result = [int(x1), int(y1), int(x2), int(y2)]
    if result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError('Grounding box must have positive area within the image')
    return result


def _ground_boxes_locate_anything(obs_path: str | Path, element_descs: list[str],
                                  W: int, H: int) -> list[BoxRecord]:
    """NVIDIA LocateAnything-3B grounder (local FastAPI service, port 8004).

    For each element we ask the service for a box ('Locate the region ...'). The
    model returns the element's true extent directly (0-1000 normalized → pixels
    server-side), so — unlike the MAI-UI point→OmniParser chain — no box recovery
    is needed; we record source 'la' and clamp to the frame.

    If the model returns only a point (no box), we fall back to the shared
    point→box chain (OmniParser → CV refine → fixed) so the act frame still gets a
    real element box, recording the chain's own source ('omni'/'cv'/'fixed').

    Same record shape {element, source, point_px, bbox_norm, bbox_px} as the other
    backends. Elements the service fails to locate are skipped.
    """
    with open(obs_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()

    omni_boxes = None       # detected once, lazily, only if a point→box fallback is hit
    omni_checked = False

    boxes = []
    for desc in element_descs:
        try:
            resp = _HTTP.post(
                f'{_next_la_url()}/ground',
                json={'image_b64': img_b64, 'phrase': desc, 'output_type': 'box'},
                timeout=180,
            )
            check_status(resp, 'LocateAnything')
            data = resp.json()
        except Exception as e:
            print(f'  ⚠️  LocateAnything grounding failed for {desc!r}: {api_error("LocateAnything", e)}')
            continue

        try:
            la_boxes = data.get('boxes') or []
            if la_boxes:
                px = _clamp_box(la_boxes[0], W, H)
                boxes.append(_box_record(desc, px, W, H, 'la'))
                continue
            pts = data.get('points') or []
            if not pts:
                continue
            point = pts[0]
            if len(point) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in point):
                raise ValueError('Invalid point')
            if not (0 <= point[0] <= W and 0 <= point[1] <= H):
                raise ValueError('Point outside image')
            cx, cy = min(W - 1, int(point[0])), min(H - 1, int(point[1]))
        except (ValueError, TypeError, IndexError, KeyError, AttributeError):
            print('LocateAnything returned invalid coordinates; target skipped')
            continue
        if not omni_checked:
            omni = _get_omni()
            omni_boxes = omni.detect(obs_path) if omni else None
            omni_checked = True
        px, source = _box_for_point(obs_path, cx, cy, W, H, omni_boxes)
        boxes.append(_box_record(desc, px, W, H, source, point_px=[cx, cy]))
    return boxes


def _verify_box_with_cv2(obs_path: str | Path, hint_box: Box, W: int, H: int) -> Box | None:
    """Draw hint_box on a temp copy of obs, then recover it via before/after CV
    diff (filters native website red). Returns the detected box, or None."""
    import tempfile
    from autogui.clients.bbox_cv import detect_new_red_bbox
    tmp = tempfile.NamedTemporaryFile(prefix='autogui_ground_', suffix='.png', delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        with Image.open(obs_path) as original:
            im = original.convert('RGB')
        draw = ImageDraw.Draw(im)
        draw.rectangle(hint_box, outline=_BOX_COLOR, width=_BOX_WIDTH)
        im.save(tmp_path)
        detected = detect_new_red_bbox(obs_path, tmp_path, hint_bbox=hint_box, require_hint=True)
        return _clamp_box([float(v) for v in detected], W, H) if detected else None
    except Exception as e:
        print(f'  ⚠️  cv2 box verification failed ({e}); falling back to the raw hint box')
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# Grounder backends. Each maps (obs_path, element_descs, W, H) -> list of box
# records. Add a new backend by registering it here — callers stay unchanged.
GROUNDERS = {
    'mai_ui': _ground_boxes_mai_ui,
    'gpt55': _ground_boxes_gpt55,
    'locate_anything': _ground_boxes_locate_anything,
}
DEFAULT_GROUNDER = os.environ.get('AUTOGUI_GROUNDER', 'locate_anything')


def ground_boxes(obs_path: str | Path, element_descs: list[str],
                 grounder: str | None = None) -> list[BoxRecord]:
    """Locate each element on the obs frame and return box records (NO drawing).

    grounder selects the backend: 'mai_ui' (MAI-UI point → OmniParser → CV refine →
    fixed box), 'gpt55' (GPT-5.5 vision bbox → cv2 verify), or 'locate_anything'
    (default: NVIDIA LocateAnything-3B service → element box directly, point→box
    chain fallback). All return the same record shape {element, source, point_px,
    bbox_norm, bbox_px}; these records are the single source of truth for box
    coordinates regardless of how the act frame is later rendered (PIL overlay
    or image-edit).

    Elements that fail to ground are skipped, so the list may be shorter than
    element_descs.
    """
    name = grounder or DEFAULT_GROUNDER
    backend = GROUNDERS.get(name)
    if backend is None:
        raise ValueError(f'unknown grounder {name!r}; choose from {sorted(GROUNDERS)}')
    with Image.open(obs_path) as im:
        W, H = im.size
    records = backend(obs_path, element_descs, W, H)
    valid = []
    for record in records:
        try:
            px = _clamp_box(record['bbox_px'], W, H)
            valid.append(_box_record(record['element'], px, W, H, record['source'], record.get('point_px')))
        except (KeyError, TypeError, ValueError):
            continue
    return valid


def draw_boxes_pil(obs_path: str | Path, act_path: str | Path,
                   boxes: list[BoxRecord]) -> str | Path:
    """Render an act frame = obs pixels + one red rectangle per box, pixel-identical
    to obs except for the boxes. Pure PIL, no generation model.

    `boxes` is a list of records carrying 'bbox_px' (e.g. from ground_boxes).
    Returns act_path.
    """
    with Image.open(obs_path) as source:
        im = source.convert('RGB')
    draw = ImageDraw.Draw(im)
    for b in boxes:
        draw.rectangle(b['bbox_px'], outline=_BOX_COLOR, width=_BOX_WIDTH)
    encoded = io.BytesIO()
    im.save(encoded, format='PNG')
    atomic_write_bytes(act_path, encoded.getvalue())
    return act_path

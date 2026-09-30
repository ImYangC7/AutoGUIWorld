# -*- coding: utf-8 -*-
"""Pluggable act-frame annotation: orthogonal GROUNDER and RENDER axes.

The trajectory pipeline marks each pointing action with a red box on the
before-action observation. Two independent, decoupled concerns:

  1. WHERE the box goes — the label/coordinates, chosen by ``grounder``:
       - 'locate_anything' (default): NVIDIA LocateAnything-3B returns the element
                  box directly, with a point→OmniParser→CV→fixed chain fallback.
       - 'mai_ui': MAI-UI point → OmniParser box → CV refine → fixed.
       - 'gpt55': GPT-5.5 vision returns the element bbox, verified/snapped by a
                  local PIL-draw + cv2 before/after diff (filters native red).
     Either way ``grounding.ground_boxes`` is the single source of truth, computed
     on the clean obs frame the RL policy actually sees, preserving drag from/to
     order. The recorded ``bbox_px`` is identical regardless of renderer.

  2. HOW the act frame is drawn — chosen by ``render``:
       - 'pil'   (default): copy obs pixels + PIL rectangle(s). Pixel-identical to
                  obs except for the red box(es).
       - 'image2': re-render the scene with image-edit, asking the model to paint
                  the red rectangle(s) at the grounded region(s). The act frame is
                  then a generated image (NOT pixel-identical) — useful when a
                  baked-in box is wanted, e.g. visual QA. Coordinates still come
                  from the grounder, so training labels are unaffected.

Because coordinates are decoupled from rendering, every (grounder, render)
combination returns the same ``boxes`` shape for storage and quality checks.
"""

from pathlib import Path

from PIL import Image

from autogui.clients.grounding import ground_boxes, draw_boxes_pil, BoxRecord
from autogui.clients.image import edit_with_ref


def _location_phrase(bbox_norm: list[float]) -> str:
    """Turn a normalized bbox into a coarse on-screen location phrase to guide
    the image-edit model (e.g. 'in the upper-left area'). Coordinates are the
    authoritative label; this is only a textual hint for rendering."""
    cx = (bbox_norm[0] + bbox_norm[2]) / 2
    cy = (bbox_norm[1] + bbox_norm[3]) / 2
    vert = 'upper' if cy < 0.33 else ('lower' if cy > 0.66 else 'middle')
    horiz = 'left' if cx < 0.33 else ('right' if cx > 0.66 else 'center')
    if vert == 'middle' and horiz == 'center':
        return 'in the center'
    return f'in the {vert}-{horiz} area'


def _image_size_str(obs_path: str | Path, image_size: str | None) -> str:
    """Image-edit needs a 'WxH' size. Use the caller's value, else read the obs."""
    if image_size:
        return image_size
    with Image.open(obs_path) as im:
        w, h = im.size
    return f'{w}x{h}'


def _draw_boxes_image2(obs_path: str | Path, act_path: str | Path, boxes: list[BoxRecord],
                       image_size: str | None, quality: str) -> str | Path:
    """Render the act frame by asking image-edit to paint red rectangle(s) at the
    already-grounded region(s). Whole-scene repaint (not pixel-identical)."""
    marks = []
    for b in boxes:
        marks.append(
            f'a 2px solid red rectangle outline (no text label) tightly around the '
            f'{b["element"]} {_location_phrase(b["bbox_norm"])}'
        )
    if len(marks) == 1:
        box_instr = f'Draw {marks[0]}.'
    else:
        box_instr = 'Draw ' + '; and '.join(marks) + '.'
    edit_prompt = (
        'Reproduce the previous screenshot exactly — same layout, text, icons, '
        'colors, and typography — then add only red bounding box annotation(s): '
        f'{box_instr} Do not change, move, or restyle any other element, and add '
        'nothing else besides the red rectangle(s).'
    )
    edit_with_ref(edit_prompt, obs_path, act_path,
                  size=_image_size_str(obs_path, image_size), quality=quality)
    return act_path


def annotate_act_frame(obs_path: str | Path, act_path: str | Path, element_descs: list[str], *,
                       grounder: str | None = None, render: str = 'pil',
                       image_size: str | None = None, quality: str = 'high') -> list[BoxRecord]:
    """Locate element(s) on obs (grounding) and render the act frame.

    Two orthogonal, decoupled axes:
      - grounder: WHERE the box is — 'locate_anything' (default: LocateAnything-3B
        → element box, point→box fallback), 'mai_ui' (MAI-UI→OmniParser→CV) or
        'gpt55' (GPT-5.5 vision bbox → cv2 verify). Selects the coordinate source.
      - render: HOW the act frame is drawn — 'pil' (pixel-identical overlay) or
        'image2' (image-edit repaint). Selects the rendering only.
    Box coordinates always come from the grounder, so the returned records are
    identical in shape regardless of render.

    Args:
        obs_path: clean before-action observation.
        act_path: output path for the boxed act frame.
        element_descs: element descriptions to locate (1 for pointing, 2 for drag
            in from/to order).
        grounder: coordinate backend ('locate_anything' | 'mai_ui' | 'gpt55');
            None uses the default.
        render: 'pil' (default) or 'image2'.
        image_size / quality: forwarded to image-edit when render='image2'.

    Returns the grounded box records (same shape for both renderers); each has
    'element', 'source', 'point_px', 'bbox_norm', 'bbox_px'. May be shorter than
    element_descs if some elements failed to ground.
    """
    if render not in ('pil', 'image2'):
        raise ValueError('Unknown action-frame renderer')
    boxes = ground_boxes(obs_path, element_descs, grounder=grounder)
    if render == 'image2' and boxes:
        _draw_boxes_image2(obs_path, act_path, boxes, image_size, quality)
    else:
        # 'pil' default; also the fallback when no box grounded (image-edit would
        # have nothing to draw, so just write the clean copy via PIL).
        draw_boxes_pil(obs_path, act_path, boxes)
    return boxes

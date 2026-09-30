# -*- coding: utf-8 -*-
"""GPT-5.5 vision grounding prompt.

Given a clean BEFORE screenshot plus the semantic step context, GPT-5.5 returns
the pixel bbox of the element the action should target. The box is drawn locally
on BEFORE and recovered with cv2 (see autogui/clients/bbox_cv.py), so the LLM's
job is element identification, not pixel-perfect coordinates.
"""

GROUND_GPT55_SYSTEM = (
    'You are a precise GUI click-target bbox annotator. '
    'Return strict JSON only. Do not include Markdown or chain-of-thought.'
)

GROUND_GPT55_USER_TEMPLATE = """You are a GUI click-target bbox annotator for an existing trajectory step.

You will receive exactly one image:
1. BEFORE: the clean screenshot before the current GUI action.

Identify, on the BEFORE image coordinate system, the visible UI element that the
action should target. The bbox will be drawn locally on BEFORE to create an
annotated image, and cv2 will then detect the red rectangle to compute the final
bbox and click center.

Target element from planner: {element}
Action: {action_name}
Description: {description}
Attached BEFORE image size: {image_size}

Rules:
- Return coordinates in the attached BEFORE image coordinate system.
- Use full-image absolute pixel coordinates: origin (0,0) at top-left, x rightward, y downward.
- Return [x1, y1, x2, y2] as the top-left and bottom-right corners of the visible UI element.
- Box the actual interactive element (button, tab, link, checkbox, input field, menu item, result card, icon button), not a broad panel, full row, section, table, form, or surrounding whitespace.
- If the hit area is a small icon button, box the full button hit area tightly, not only the glyph.
- If the target is text inside a larger clickable control, box the whole clickable control tightly.
- Do not add padding for aesthetics; a red rectangle will be drawn exactly around your bbox.
- Output strict JSON only. No Markdown, no chain-of-thought.

Output schema:
{{
  "bbox": [x1, y1, x2, y2],
  "target_element": "short visible click target description",
  "confidence": "high|medium|low"
}}
"""


def build_ground_gpt55_prompt(element, action_name, description, image_size):
    return GROUND_GPT55_USER_TEMPLATE.format(
        element=element or '(unspecified)',
        action_name=action_name or 'click',
        description=description or '',
        image_size=image_size or 'unknown',
    )

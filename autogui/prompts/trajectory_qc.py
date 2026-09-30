# -*- coding: utf-8 -*-
"""Trajectory step VLM quality-check prompt.

Given up to three images of one trajectory step (BEFORE = clean pre-action
observation, TARGET = red-box annotated frame marking the grounded element(s),
AFTER = post-action observation) plus the semantic context (task, action,
grounded element names, thinking), a multimodal model judges the step across
three groups: grounding correctness, action-vs-screen consistency, and thinking
consistency. It returns strict JSON with per-dimension pass/warn/fail verdicts.
"""

TRAJ_QC_SYSTEM = (
    'You are a meticulous GUI trajectory quality inspector. You are shown a '
    'single step of a GUI agent trajectory and must judge whether the red box '
    'targets the right element, whether the action fits the screen, and whether '
    'the reasoning matches what is visible. Be strict and literal about what the '
    'images actually show. Return strict JSON only, no Markdown, no extra prose.'
)

TRAJ_QC_USER_TEMPLATE = """You are quality-checking ONE step of a GUI agent trajectory.

Overall task the agent is doing:
{task}

This step:
- action type: {action_name}
- action parameters: {action_params}
- planner target element: {target_element}
- grounded box element name(s): {box_elements}
- agent thinking for this step: {thinking}

Images provided (in order):
{image_legend}

Judge each dimension below from what the images ACTUALLY show. Use "na" only when the dimension does not apply (e.g. grounding checks for a non-pointing action, or transition check when no AFTER image).

GROUNDING (only for pointing actions that have a red box):
- box_hits_target: does the red box enclose the UI element the action intends to operate on (the planner target)? fail if it boxes a different element or empty space.
- box_tightness: is the box a reasonable tight fit around the interactive element? warn if far too large (whole panel/row) or too small (only part of the glyph). "na" if no box.
- target_exists: is the planner's target element actually visible on the BEFORE screen? fail if that element is NOT present on screen (so any box is necessarily wrong).

ACTION vs SCREEN (all steps):
- action_valid_here: given the BEFORE screen state, is this action sensible and executable now? fail if it makes no sense (e.g. type_text with no focused input, click a control that isn't there).
- obs_transition_ok: comparing BEFORE and AFTER, did the screen change in a way consistent with this action? warn if the change looks unrelated; "na" if no AFTER image or a non-visual action (wait/answer).

THINKING (only if thinking text is provided):
- thinking_matches_screen: does the thinking describe elements/state that are actually visible? fail if it hallucinates UI not present.
- thinking_wavering: does the thinking contradict itself or express confusion about what to do (e.g. "but wait", "actually", second-guessing the target)? fail if it wavers, pass if it is a clean single decision.

Then give:
- overall: "ok" (all good), "minor" (only warnings or a thinking wobble), "major" (any of box_hits_target/target_exists/action_valid_here/obs_transition_ok is fail).
- confidence: your confidence in this judgment (high/medium/low) given image clarity.
- reason: ONE short sentence naming the single most serious problem, or "clean" if none.

Output strict JSON only, exactly this shape:
{{
  "grounding": {{"box_hits_target": "pass|warn|fail|na", "box_tightness": "pass|warn|fail|na", "target_exists": "pass|fail|na"}},
  "action": {{"action_valid_here": "pass|warn|fail", "obs_transition_ok": "pass|warn|fail|na"}},
  "thinking": {{"thinking_matches_screen": "pass|warn|fail|na", "thinking_wavering": "pass|fail|na"}},
  "overall": "ok|minor|major",
  "confidence": "high|medium|low",
  "reason": "<one sentence>"
}}
"""


def build_trajectory_qc_prompt(task, action_name, action_params, target_element,
                               box_elements, thinking, image_legend):
    return TRAJ_QC_USER_TEMPLATE.format(
        task=task or '(unspecified)',
        action_name=action_name or '(unknown)',
        action_params=action_params or '(none)',
        target_element=target_element or '(none)',
        box_elements=box_elements or '(none)',
        thinking=thinking or '(none)',
        image_legend=image_legend,
    )

# -*- coding: utf-8 -*-
"""System prompt for TRAJECTORY planning given a fixed seed initial state.

Used in 'expand' mode: takes a seed (with already-fixed initial state and
existing initial.png) + a task description, asks the model adapter to plan only
the action sequence (no need to redescribe initial state).
"""

import json


# === Precondition rules (category-specific) =====================
# Desktop/browser clear blockers with window/overlay operations; mobile clears
# them with gestures. Selected by os_config['category'] so a mobile plan never
# carries desktop window wording (and vice versa).
DESKTOP_PRECONDITION_RULES = """## Precondition Handling Rules

If the Initial State contains Blockers, you must first emit phase="precondition" actions to clear them:
- lock screen / login_required → unlock and log in first
- modal_popup / permission_prompt → dismiss it first
- mission_control / activities_overview / fully_open_drawer → exit it first
- no_network and the task needs network → connect first

Only after all blockers are cleared do you enter phase="main". If there are no Blockers, all actions are phase="main"."""

MOBILE_PRECONDITION_RULES = """## Precondition Handling Rules

If the Initial State contains Blockers, you must first emit phase="precondition" actions to clear them:
- lock_screen / biometric_prompt / face_id_prompt → unlock first (swipe up from the bottom, then authenticate)
- notification_drawer fully open → swipe up / press_home to close it first
- no_network and the task needs network → no UI to fix it on the home screen; pick the closest task that does not need network, OR open Settings if Settings is visible on the home screen
- any open app / not on the home screen → press_home to return to the home screen first

Only after all blockers are cleared do you enter phase="main". If there are no Blockers, all actions are phase="main"."""

WEB_PRECONDITION_RULES = """## Precondition Handling Rules

If the Initial State contains Blockers, you must first emit phase="precondition" actions to clear them:
- site permission prompt (location / notifications) → dismiss or block it first
- modal dialog / login wall blocking the page → close or sign in first
- not signed in but the task needs an account → sign in first only if the task requires it

Do NOT plan steps to dismiss cookie banners or cookie/privacy consent dialogs — seeds are generated
without them. Only after all blockers are cleared do you enter phase="main". If there are no Blockers,
all actions are phase="main"."""


# === Element grounding rules (category-specific) ================
DESKTOP_GROUNDING_RULES = """## Element Grounding Rules (CRITICAL — a vision model must locate every pointing target)

Each pointing target (`target_element`, and for drag `from_element` / `to_element`) is fed to a
GUI grounding model to draw a box on the screenshot. It can ONLY locate a **concrete, visible UI
element**. Therefore:

1. Every pointing target MUST be a specific, named, currently-visible element
   (e.g. "Create Project button", "Music window title bar", "file icon 'report.pdf'").
2. FORBIDDEN as targets — abstract / relative / empty regions that have no concrete element:
   "empty desktop area", "opposite corner", "the same row/line", "blank space beside X",
   "area enclosing the icons", "somewhere below". These cannot be grounded.
3. **drag** must connect two concrete elements: `from_element` = a real element you grab,
   `to_element` = a real element / well-defined drop slot (e.g. drag file "a.png" onto folder
   "Review Queue", drag the window title bar to the "right screen edge snap zone"). Do NOT plan
   marquee/rubber-band selections that drag across empty space — there is no element to box.
4. If a target element is **occluded** by a foreground window (hidden behind another app), you may
   NOT operate on it directly. First emit an action that reveals it (minimize / move / switch the
   covering window, or click its taskbar/dock icon), then operate on it once visible.
5. If the task as written cannot be done only with concrete visible elements (e.g. it requires
   elements that are hidden or do not exist in the Initial State), choose the closest achievable
   interpretation using visible elements rather than inventing abstract regions."""

MOBILE_GROUNDING_RULES = """## Element Grounding Rules (CRITICAL — a vision model must locate every pointing target)

Each pointing target (`target_element`) is fed to a GUI grounding model to draw a box on the
screenshot. It can ONLY locate a **concrete, visible UI element**. The initial screenshot is a
phone HOME SCREEN, so the only things visible at step 1 are the status bar, the app-icon grid
(each app icon with its label), the dock icons, and the page indicator. Therefore:

1. The FIRST main action must tap something that is actually on the home screen: an app icon or a
   dock icon **named exactly as listed in the Initial State**. Never tap an app that is
   not on the listed home screen.
2. Only use app names that appear in the Initial State (grid or dock).
3. After tapping into an app, you have NOT seen its inner screen — assume a realistic landing
   screen, and from then on only target elements that would plausibly be visible there
   (a named button, tab, list row, text field…).
4. FORBIDDEN as targets — abstract / empty regions with no concrete element: "blank area",
   "middle of the screen", "below the last icon", "empty grid slot", "somewhere in the list".
   These cannot be grounded.
5. Navigation uses gestures, not windows: `press_back` to go back, `press_home` to return to the
   home screen, `swipe_up`/`swipe_down` to scroll a list or open the app drawer, `swipe_left`/
   `swipe_right` to change home pages. There are no draggable windows, no taskbar, no minimize.
6. If the task cannot be done with the apps/elements actually present, pick the closest achievable
   interpretation using the visible apps rather than inventing a non-existent app or icon."""


WEB_GROUNDING_RULES = """## Element Grounding Rules (CRITICAL — a vision model must locate every pointing target)

Each pointing target (`target_element`, and for drag `from_element` / `to_element`) is fed to a GUI
grounding model to draw a box on the screenshot. It can ONLY locate a **concrete, visible UI
element**. The screenshot is a pure Chrome browser window: the only things visible are the browser
chrome (tab bar, address bar, bookmarks bar, extension icons) and the ONE active web page. Therefore:

1. Every pointing target MUST be a specific, named, currently-visible element — either a browser
   chrome control (e.g. "address bar", "the active tab 'GitHub'", "reload button", a named bookmark)
   or a concrete element on the active page (e.g. "search input field", "Sign in button",
   "first product card", "Direct flights checkbox", "video thumbnail in the first row").
2. Stay INSIDE the browser: operate only in the active tab and Chrome chrome. Do NOT use OS-level
   actions — no Alt+Tab, no desktop/taskbar/Dock/Start menu, no other application windows.
3. FORBIDDEN as targets — abstract / relative / empty regions with no concrete element: "blank area
   of the page", "top of the screen", "somewhere below", "empty space beside X". These cannot be grounded.
4. After navigating (click a link, submit a search, open a result), you have NOT seen the next page —
   assume its realistic landing layout, and from then on only target elements that would
   plausibly be visible there.
5. **drag** must connect two concrete page elements (e.g. drag a Kanban card onto another column,
   drag a slider handle to a tick). Do not drag across empty page space — there is no element to box.
6. Use the page's visible controls (search fields, date pickers, filters, tabs, menus, result cards)
   rather than fabricating deep-link/encoded URLs. Address-bar navigation (focus via Ctrl+L, then
   type_text + Enter) is only for user-requested navigation to a known URL, or when the active site
   is completely unrelated to the task.
7. Do NOT create cookie banners, cookie/privacy consent dialogs, or newsletter popups; seeds are
   generated without them, so never plan a step that dismisses one.
8. If the task cannot be done with elements actually visible on the active page, pick the closest
   achievable interpretation using visible controls rather than inventing elements."""


# Per-category (precondition_rules, grounding_rules) pairs. Browser is its own
# surface, parallel to desktop/mobile (no os_key literals); desktop is the default.
_CATEGORY_RULES = {
    'mobile':  (MOBILE_PRECONDITION_RULES, MOBILE_GROUNDING_RULES),
    'browser': (WEB_PRECONDITION_RULES, WEB_GROUNDING_RULES),
}


TRAJECTORY_PLANNER_TEMPLATE = """You are a GUI agent action planner.

The environment's **initial state is already fixed and has been captured as a screenshot**. Your job is to plan an atomic action sequence for the given task, based on that fixed initial state.

Even when the task is phrased as a question or a request for advice ("What are…?", "How do I…?", "Is there a way to…?"), treat it as an instruction to **accomplish the underlying goal through GUI operations** — navigate, change the setting, run the command, edit the file. The `answer` action is a terminal signal only: use it to report completion **after** the operations, or — if and only if the task is genuinely impossible in this environment — as a standalone refusal. Never use `answer` in place of actually performing the task. Every `answer` step MUST carry a `status` field: `"DONE"` when the task was completed (you are reporting the result), or `"FAIL"` when the task cannot be done (a refusal, or an impossible/infeasible request). Put the explanation in `text`, not the status marker.
{infeasible_directive}
## Operating System Environment

{os_json}

## Visual Style (must carry over into every step's image)

{style_directive}

## Fixed Initial State (do NOT re-describe it)

{env_state_text}

## Fixed Initial Screenshot Description (for reference)

{seed_global_state_prompt}

{blocker_section}

## Action Space

Each step must choose exactly one action from the following:

{action_space_str}

{precondition_rules}

{grounding_rules}
## Output Format

First decide the `high_level_plan`: one or two sentences stating the overall strategy to accomplish this task (the general approach or stages), NOT the click-by-click steps. Then plan the concrete `actions` that carry out that strategy.

Output a strict JSON object only (no Markdown, no ```json fences):

```
{{
  "task": "the user task",
  "scenario": "{category}",
  "high_level_plan": "one or two sentences describing the OVERALL strategy for accomplishing this task (the general approach / stages), independent of the concrete click-by-click steps",
  "actions": [
    {{
      "step": 1,
      "phase": "precondition" | "main",
      "description": "brief English description",
      "action": <JSON conforming to the Action Space>,
      "target_window": "...",
      "target_element": "short English name of a CONCRETE VISIBLE element (required for pointing actions; no abstract/empty regions)",
      "from_element": "concrete visible element grabbed at drag start (drag only)",
      "to_element": "concrete visible element / drop target at drag end (drag only)",
      "state_before": "...",
      "state_after": "...",
      "must_not_render": "<INFEASIBLE-explore only, optional: imperative naming what MUST NOT appear on this step's screen + which real options exist; omit otherwise>"
    }},
    ...
  ]
}}
```

**Note**: Do NOT generate global_state again; output only actions[]. For an `answer` action, the `action` object must include `"status"`: `"DONE"` (task completed) or `"FAIL"` (task cannot be done), e.g. `{{"action": "answer", "status": "FAIL", "text": "..."}}`.

## Rules for writing `description` (a concise one-line intent per step)

You do NOT write image prompts. The system renders each frame separately by looking at the REAL previous screenshot plus your action; your job is only to plan correct actions and, in `description`, state the intent of this step in one clear line — what the action does and its expected result (e.g. "Open the Edit menu", "Type the report command into the terminal", "Snap the terminal to the right half"). Keep it short; do not describe the wallpaper, dock, fonts, or unrelated background — the renderer already sees them in the real frame.

- Pointing actions (click/double_click/right_click/hover/tap/long_press/drag): fill in `target_element` accurately (drag also needs `from_element`/`to_element`). The system overlays a red box on the before-action frame to mark the operation location — never mention red boxes/annotations yourself.
- Other actions (type_text/key_press/scroll/hotkey/swipe_*/press_*/wait/answer): no coordinates needed; the system draws no box.

## Key Requirements

- Each step must be a real, executable, minimal GUI action
- Every pointing target must be a concrete, currently-visible element (see Element Grounding Rules); occluded elements must be revealed first
- Steps must be logically connected (state_after of step N == state_before of step N+1)
- The whole sequence must stay consistent with the Initial State
- Output JSON only
"""


def build_trajectory_planner_prompt(os_config, style_directive, env_state_text,
                                    seed_global_state_prompt, blockers, action_space_actions,
                                    infeasible=False, judge_timing=None, infeasible_reason=None,
                                    explore_hint=None):
    """Build prompt for trajectory expansion given a fixed seed.

    infeasible=True marks a task generated as impossible in the sampled scene
    (e.g. a requested option, application, or device is unavailable).
    The planner cannot infer this from the instruction text alone,
    so we inject an explicit refusal directive. HOW the refusal looks depends on
    judge_timing:

      - "upfront": impossibility is knowable a priori (e.g. "Python4" was never
        released). Output ONE `answer` step (status=FAIL), no GUI actions.
      - "explore": impossibility can only be confirmed by inspecting the UI
        (e.g. a "Blue" theme that turns out not to be in the theme list). Plan a
        SHORT natural exploration into the relevant surface, THEN a final
        `answer` step (status=FAIL). explore_hint tells the planner which
        surface to open and what options actually exist there.

    Older callers pass only infeasible=True with no judge_timing; that falls
    back to the upfront (single-answer) behaviour for backward compatibility.
    """
    action_lines = '\n'.join(json.dumps(a, ensure_ascii=False) for a in action_space_actions)

    if blockers:
        blocker_section = '## Blockers (must be resolved by precondition actions)\n\n' + \
                          '\n'.join(f'- {b}' for b in blockers)
    else:
        blocker_section = '## Blockers\n\n(No blockers; all actions go straight to phase="main".)'

    infeasible_directive = ''
    if infeasible:
        reason_clause = f' Reason: {infeasible_reason}' if infeasible_reason else ''
        if judge_timing == 'explore':
            hint_clause = f'\nWhere to look: {explore_hint}' if explore_hint else ''
            infeasible_directive = (
                '\n**This task is INFEASIBLE, but that can only be confirmed by inspecting '
                f'the UI.**{reason_clause}{hint_clause}\n'
                'Plan a SHORT, natural exploration — typically 2-5 real GUI steps — that '
                'opens the relevant surface named above (e.g. open the settings/preferences '
                'panel, expand the option list, scroll to where the requested option would '
                'be). After confirming the requested option/capability is genuinely absent, '
                'output a FINAL `answer` step with `status: "FAIL"` that explains exactly which '
                'locations you checked and why the task cannot be completed. Take the natural '
                'minimum number of steps — do NOT pad the trajectory with filler steps.\n'
                '**Negative constraint field (critical):** the renderer draws each frame '
                'from the real screen, so you must tell it what NOT to show. For every step '
                'whose screen is where the requested option should appear but does not (e.g. '
                'the step that opens the theme list, the language list, the mode menu), add a '
                '`must_not_render` field to that step: a short imperative naming exactly what '
                'MUST NOT appear and which real options DO exist there (e.g. "Do NOT show a '
                '\'Blue\' theme entry; the theme list has ONLY System, Light, Dark."). This '
                'guarantees the frame genuinely lacks the option you are about to report as '
                'missing. Omit `must_not_render` on steps where the missing option is '
                'irrelevant (e.g. just opening a menu bar).\n')
        else:
            # upfront (default / backward-compatible)
            infeasible_directive = (
                '\n**This task is INFEASIBLE in this environment** (the requested option, '
                f'application, or capability does not exist here).{reason_clause}\n'
                'This is knowable upfront without any exploration. Do not plan any GUI '
                'operations. Output exactly ONE `answer` step with `status: "FAIL"` that '
                'politely declines and briefly explains why it cannot be done.\n')

    # Precondition + grounding rules by OS category (desktop is the default).
    category = os_config.get('category')
    precondition_rules, grounding_rules = _CATEGORY_RULES.get(
        category, (DESKTOP_PRECONDITION_RULES, DESKTOP_GROUNDING_RULES),
    )

    return TRAJECTORY_PLANNER_TEMPLATE.format(
        os_json=json.dumps(os_config, ensure_ascii=False, indent=2),
        style_directive=style_directive,
        env_state_text=env_state_text,
        seed_global_state_prompt=seed_global_state_prompt,
        blocker_section=blocker_section,
        infeasible_directive=infeasible_directive,
        action_space_str=action_lines,
        precondition_rules=precondition_rules,
        grounding_rules=grounding_rules,
        category=os_config['category'],
        prompt_prefix=os_config['prompt_prefix'],
    )


# Observation prompts produce clean states; box_backends annotates action frames.

# Edit instruction to produce the next clean observation from the previous one.
_OBS_EDIT = (
    'Based on the previous screenshot, render the next state of the GUI workflow '
    'after this action: {desc}. Keep the same visual style, colors, fonts and '
    'layout; only change what this action changes. The image must contain only '
    'the GUI interface with no red box or annotation. Do not add cookie banners, '
    'cookie/privacy consent dialogs, newsletter popups, permission prompts, modal '
    'overlays, bounding boxes, arrows, labels, or annotation overlays unless this '
    'action explicitly creates one.'
)


def render_edit_prompt(desc):
    """Wrap a render description in the image-edit instruction that turns the
    previous observation into the next one. Single entry point so callers never
    format the private _OBS_EDIT template themselves."""
    return _OBS_EDIT.format(desc=(desc or 'the next state').rstrip())


# Voyager reads the current clean screenshot and full action, then produces
# the agent's thought, action summary, and next-state rendering description.

VOYAGER_SYS = (
    'You play TWO roles for one GUI step. You SEE the real CURRENT frame (before '
    'this action) and are given the exact ACTION about to happen as a JSON object '
    'conforming to the action space (with all its fields). Produce THREE outputs:\n'
    '(1) as the ACTING AGENT, looking at the current screen BEFORE acting: a '
    'first-person "thought" (why you take this action now) and a one-sentence '
    'imperative "action_abstract" (what to do plus the purpose it serves, no coordinates);\n'
    '(2) as the RENDERER: a detailed "voyager_prompt" describing the NEXT frame, '
    'i.e. the screen AFTER the action.\n'
    'PERSPECTIVE (important): thought and action_abstract are BEFORE-action, agent '
    'point of view (present/future tense, "I see… I will…"); voyager_prompt is '
    'AFTER-action, the resulting screen. Do not mix them up.\n'
    'HOW TO RENDER EACH ACTION TYPE (read the action JSON to know which):\n'
    '- click / double_click / right_click / hover / tap / long_press: show the '
    'result of operating the "element" — menu expands, dialog opens, item selected/'
    'focused/highlighted, page navigates, etc.\n'
    '- drag: show the interface AFTER the element named in "from_element" has been '
    'moved to "to_element" (card dropped in the new column, slider at the new tick, '
    'file inside the target folder).\n'
    '- type_text: the literal "text" appears in the focused field/terminal (see the '
    'verbatim rule below).\n'
    '- key_press: show the effect of the "key" (Enter runs/submits, Tab moves focus, '
    'Esc closes). For an Enter that executes a shell command, render the command\'s '
    'concrete output lines.\n'
    '- hotkey: show the effect of the "keys" combo (Ctrl+S → save dialog, Ctrl+L → '
    'focused address bar, Ctrl+A → all selected).\n'
    '- scroll: move content in the "value" direction (down/up); swipe_* similarly.\n'
    '- press_back / press_home: navigate back / to the home screen.\n'
    '- wait: a loading or just-loaded state of the same screen.\n'
    'VERBATIM TEXT (critical): if the action types text or runs a command, the NEXT '
    'frame MUST show that literal text/command in the target field or terminal — '
    'quote it verbatim so the image model renders the actual characters, not a vague '
    '"a command was typed". Carry over everything else in the current frame '
    'unchanged. No red boxes/annotations.\n'
    'REFERENCE FIELD (advisory, not authoritative): "planner_description" is a '
    'one-line intent for this step. Use it to understand what the action is meant '
    'to achieve, but the REAL current frame you see is the source of truth — if it '
    'conflicts with what is actually on screen, follow the real frame.\n'
    'GLOBAL CONTEXT (advisory): "high_level_plan" is the overall strategy of the '
    'whole task. Use it to understand where THIS step fits and keep the frame '
    'coherent with the goal — but render ONLY the result of the current action; '
    'never jump ahead and render the outcome of later steps.\n'
    'NEGATIVE CONSTRAINT: if the action carries a "must_not_render" field, your '
    'next-frame description MUST obey it — never render the named element/option, '
    'render only the real options it lists. This matters most when the trajectory '
    'is proving a requested option does not exist: the frame that would show it '
    'must genuinely NOT contain it.\n'
    'THOUGHT quality rules — write it as a first-person reasoning that weaves in '
    'THREE things (natural prose, ~2-4 sentences, not labeled bullet points):\n'
    '  (a) Reflection: if there was a previous step, judge from the CURRENT frame '
    'whether it landed as expected (the current screen IS the result of the last '
    'action — e.g. "I clicked Settings and it is now open, as intended"); on the '
    'first step there is nothing to reflect on.\n'
    '  (b) Progress assessment: using "high_level_plan" and "progress" (current_step '
    'of total_steps, steps_done_so_far), state how much of the overall plan is done '
    'and what remains (e.g. "Settings and the Wi-Fi page are open; the network '
    'details and the Metered switch are still ahead").\n'
    '  (c) Next action: name the on-screen element you are about to act on and why '
    'it advances the task.\n'
    'Ground everything in what is visible on the CURRENT screen; do NOT mention '
    'coordinates, red boxes, that the action was given to you, or invent UI not '
    'visible.\n'
    'ACTION_ABSTRACT is ONE imperative sentence: the concrete on-screen action PLUS '
    'the immediate purpose it serves, joined with "to ..." (e.g. "Click the Filters '
    'menu to access the filter categories", "Press Ctrl+O to open the file dialog so '
    'the image can be selected"). Name the concrete target, no coordinates.\n'
    'Reply strict JSON: {"thought":"<first-person reasoning: reflection + progress '
    '+ next action, before acting>", '
    '"action_abstract":"<one imperative sentence: action + immediate purpose, no coordinates>", '
    '"voyager_prompt":"<detailed next-frame description, after acting>"}'
)


def voyager_user_prompt(action_step, prompt_prefix, high_level_plan=None,
                        step_index=None, total_steps=None, steps_done=None):
    """User text for the closed-loop Voyager call: the whole action about to happen
    (its full action-space JSON, so every field — text/key/element/from_element/
    to_element/value/keys — reaches the renderer, not just a hand-picked subset),
    plus advisory planner intent and (optionally) the task's high_level_plan for
    global context. Paired with the real previous frame as the image.

    step_index / total_steps / steps_done give Voyager a sense of PROGRESS: which
    step this is out of how many, and the one-line abstracts of everything done so
    far. This feeds the thought's Reflection (was the last step's effect as
    expected, judged from the current frame) and Progress Assessment (how much of
    the high_level_plan is done). All optional; absent → lean single-step payload.

    Passing the entire action dict (rather than cherry-picking fields) is what keeps
    this robust: adding a new action type to the action space needs no change here,
    and no drag/scroll/hotkey parameter can be silently dropped."""
    a = action_step.get('action') or {}
    if not isinstance(a, dict):
        a = {'action': a}
    payload = {}
    if high_level_plan:
        payload['high_level_plan'] = high_level_plan
    if step_index is not None:
        payload['progress'] = {
            'current_step': step_index,
            'total_steps': total_steps,
            'steps_done_so_far': steps_done or [],
        }
    payload.update({
        # Full action JSON — carries text/key/element/from_element/to_element/
        # value/keys/status for whatever action type this is.
        'action': a,
        # Grounding-level element names live at the step top level too; surface them
        # so the renderer has them even if the planner only filled the top level.
        'target_element': action_step.get('target_element'),
        'from_element': action_step.get('from_element'),
        'to_element': action_step.get('to_element'),
        'planner_description': action_step.get('description'),
    })
    # Drop empty top-level element hints so the payload stays lean for non-pointing
    # actions (they live inside `action` when present anyway).
    payload = {k: v for k, v in payload.items() if v is not None}
    # Negative constraint (INFEASIBLE-explore): omit unless the planner set it.
    if action_step.get('must_not_render'):
        payload['must_not_render'] = action_step['must_not_render']
    return ('The image is the CURRENT frame (before the action). The action about to '
            'happen:\n' + json.dumps(payload, ensure_ascii=False) +
            f'\nBegin the voyager_prompt with "{prompt_prefix}".')

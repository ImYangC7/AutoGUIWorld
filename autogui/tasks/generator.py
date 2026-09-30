# -*- coding: utf-8 -*-
"""Heuristic task generator with OS-domain constraints and dedup.

Pipeline:
1. Load OS task domain (apps, scenarios, description) + existing task registry
2. Build history-aware prompt: domain hints + few-shot existing tasks + diversity instruction
3. Call the model adapter to generate one new task
4. Check embedding similarity against registry
5. If duplicate, retry with stronger diversity hint (up to N attempts)
6. Persist accepted tasks to registry

Tasks are generated per-seed via `cli.py expand --auto-tasks N` (or in bulk by
`batch_generate.py`), which calls `generate_one_task` with the seed's real
elements and a per-call directive (difficulty / sentence style / verbs to avoid).
"""

import json

from autogui.state.registry import OS_REGISTRY
from autogui.tasks.domains import OS_TASK_DOMAINS
from autogui.tasks.dedup import get_registry_for_os, TaskRegistry
from autogui.clients.llm import call_llm
from autogui.utils.jsonio import strip_json_fence


TASK_GEN_SYSTEM_PROMPT = """You design GUI tasks for a supplied initial screen.

You must generate a **diverse, concrete, executable** GUI operation task description for the specified operating system platform.
The task must fit that platform's real-world usage scenarios and avoid existing tasks (no semantic duplication).

## Task Format Requirements

- Output a **strict JSON object**. No Markdown, no ```json fences.
- The JSON must contain the fields:
  - "task": a one-sentence English task description (no more than 25 words)
  - "app": the main app being operated on (from the given app list)
  - "category": the task category (from the given scenario list)
  - "complexity": "simple" | "medium" | "complex"
  - "feasible": true | false  (whether the task can actually be completed on this platform)
- When "feasible" is false, you MUST also include:
  - "judge_timing": "upfront" | "explore"
  - "infeasible_reason": one sentence explaining why it cannot be done
  - "explore_hint" (ONLY when judge_timing == "explore"): which UI surface to open to confirm
    the option is absent, and what options actually exist there instead.

## Feasibility (feasible / infeasible trap tasks)

Most tasks should be genuinely completable ("feasible": true). When this generation is
directed to produce an INFEASIBLE trap task, design a request that a user might plausibly
make but that CANNOT be done on this platform, and classify HOW an agent would find out:

- "judge_timing": "upfront" — impossibility is knowable a priori, without touching the UI
  (the requested thing was never released / is a category error).
  e.g. "Set the default Python version to Python 4" (Python 4 does not exist);
       "Convert this PNG to a true vector SVG in GIMP" (raster editor cannot vectorize).
- "judge_timing": "explore" — impossibility can only be confirmed by inspecting the UI:
  the option would live in a specific panel/menu but is not actually there.
  e.g. "Change the GIMP color theme to 'Blue'" — explore_hint:
       "Open Edit->Preferences->Interface->Theme; the list offers only System/Light/Dark, no Blue.";
       "Change Chrome's interface language to Xenothian" — explore_hint:
       "Open Settings->Languages->Add languages; only real languages are listed, no Xenothian."

An infeasible task must still be a realistic-sounding request; do NOT make it obviously absurd.

## Diversity Principles

- Do not reuse the same app too many times
- Different apps should cover different scenario categories
- The task statement must be specific (e.g. "turn on Bluetooth in Settings", not "open Settings")
- Avoid being semantically similar to existing tasks in verb, target, or action flow

## Quality Rules (all must hold, otherwise the task is invalid)

1. **Describe the GOAL, not the METHOD**: state only "what result to achieve", do not write specific function names, menu paths, or shortcuts
   (e.g. ✅ "format column B as currency"  ❌ "use Format → Cells → Number to set currency").
   Exception: GUI features like pivot tables and conditional formatting are themselves the learning target, so they may be named.
2. **At least one GUI interaction**: must involve click/drag/menu/dialog/right-click or similar UI operation;
   it cannot be just typing a formula or plain text.
3. **Clear, self-contained instruction**: specific to one executable workflow; not vague, not open-ended, not dependent on undefined external information.
4. **Only operate on elements that actually exist in the initial interface**: if "current real visible elements" are given below, the task **must** be designed
   only around those elements; **inventing** non-existent files, windows, or icons is forbidden.
   (This applies to FEASIBLE tasks. An infeasible trap task may reference a plausible-sounding
   target that turns out not to exist — that absence is the point of the trap.)

## Important

- Output the JSON object only, with no explanatory text
- A feasible task must be genuinely completable on this platform; do not invent things.
- An infeasible task must be genuinely impossible for the stated reason; do not mislabel a
  task that is actually doable.
"""


TASK_GEN_USER_TEMPLATE = """## Target Platform

{os_name} ({os_category})

### Platform Characteristics

{description}

### Common App List

{apps_list}

### Common Scenario Categories

{scenarios_list}

### Task Step Complexity Range

{complexity_min}-{complexity_max} steps
{seed_section}{directive_section}
## Existing Tasks ({existing_count}; avoid semantic duplication with these)

{existing_tasks_str}

## Please generate one new task

Requirements:
- Clearly different from the existing tasks above in semantics, verb, and operation flow
- Try to use apps and scenarios not yet seen in existing tasks
- The task must be specific to one executable workflow"""


# 5 instruction sentence styles (rotated to increase phrasing diversity)
SENTENCE_STYLES = [
    'imperative (a direct command, e.g. "Set the font size of A1 to 14")',
    'request (a polite question, e.g. "Could you change column B to currency format?")',
    'situational (describe the context first, then the need, e.g. "I have a list of temperatures in column C — round them to one decimal")',
    'goal-oriented (state the desired effect, e.g. "I want the header row to stand out: bold, 16pt, blue background")',
    'problem-fixing (describe the current problem and ask for a fix, e.g. "The dates show as the number 45678 — change them to MM/DD/YYYY")',
]

# Difficulty calibration (bound to the action-space step count)
DIFFICULTY_GUIDE = (
    'simple = a 1-2 action everyday operation; '
    'medium = 3-5 actions, or one complex operation requiring a menu/dialog; '
    'complex = a long multi-stage workflow of 15+ distinct actions spanning '
    'several menus/dialogs/components, with clear ordering between stages '
    '(e.g. configure several settings in sequence, or build something up step by '
    'step then save/export it). Make it genuinely long-horizon, not just 5-6 steps.'
)
# Default difficulty distribution ~30/40/30
DIFFICULTY_WEIGHTS = {'simple': 0.30, 'medium': 0.40, 'complex': 0.30}

# Default feasibility distribution: mostly feasible tasks, a minority of
# infeasible trap tasks split between the two judge_timing kinds. Trap tasks
# teach the agent to recognise impossibility and refuse (upfront) or explore
# then refuse (explore), instead of hallucinating a completion.
FEASIBILITY_WEIGHTS = {'feasible': 0.85, 'infeasible_upfront': 0.08, 'infeasible_explore': 0.07}


def _build_seed_section(seed):
    """Render the seed's real visible elements into a prompt section, or '' if no seed."""
    if not seed:
        return ''
    gs = seed.get('global_state', {})
    visible = gs.get('visible_elements') or []
    env_state = seed.get('env_state') or {}
    windows = env_state.get('windows') or []
    home_screen = env_state.get('home_screen')
    active_tab = env_state.get('active_tab')
    lines = ['\n## Current Real Visible Elements (the task may only operate on these; inventing others is forbidden)\n']
    if windows:
        lines.append('### Open windows')
        for w in windows:
            tag = ' (foreground)' if w.get('role') == 'foreground' else ''
            lines.append(f'- {w["app"]}{tag}: {w["content"]} (located at {w["position"]})')
    if active_tab:
        # Pure-web browser: the visible surface is the active tab's page + the
        # background tabs. List them so the task only targets the real site/page.
        site = active_tab.get('site') or 'a web page'
        lines.append('### Browser tabs')
        lines.append(f'- Active tab (target): {site} — {active_tab.get("content", "")}')
        for tab in env_state.get('background_tabs') or []:
            lines.append(f'- Background tab: {tab.get("site") or "a web page"} — {tab.get("content", "")}')
    if home_screen:
        # Mobile: the visible elements are the home-screen app grid + dock, not
        # desktop windows. List every launchable icon so the task only targets
        # apps that are actually on screen.
        apps = [t['name'] for t in home_screen.get('app_grid', []) if t.get('kind') == 'app']
        dock = [d['name'] for d in home_screen.get('dock', [])]
        lines.append('### Home screen app icons')
        lines.append('- Apps: ' + (', '.join(apps) if apps else '(none)'))
        lines.append('- Dock: ' + (', '.join(dock) if dock else '(none)'))
    if visible:
        lines.append('### Visible UI elements')
        lines += [f'- {v}' for v in visible]
    if gs.get('target_window'):
        lines.append(f'\nForeground target window: {gs["target_window"]}')
    return '\n'.join(lines) + '\n'


def _build_directive_section(domain, directive):
    """Per-call generation directives: feature-tree hint, target difficulty,
    sentence style, and verbs to avoid. `directive` is a dict, may be empty."""
    if not directive:
        return ''
    lines = ['\n## Directed Requirements for This Generation\n']

    tree = domain.get('feature_tree')
    if tree:
        flat = [f'{cat} → {leaf}' for cat, leaves in tree.items() for leaf in leaves]
        lines.append('### Feature coverage (prefer feature points below that are less covered)')
        lines += [f'- {x}' for x in flat]

    if directive.get('difficulty'):
        lines.append(f'\n### Target difficulty\nGenerate a **{directive["difficulty"]}** difficulty task this time. {DIFFICULTY_GUIDE}')

    feas = directive.get('feasibility')
    if feas == 'infeasible_upfront':
        lines.append('\n### Feasibility (this generation)\nGenerate an **INFEASIBLE** trap task whose '
                     'impossibility is knowable **upfront** (the requested thing was never released, '
                     'or is a category error for this app). Set "feasible": false, "judge_timing": '
                     '"upfront", and give a one-sentence "infeasible_reason".')
    elif feas == 'infeasible_explore':
        lines.append('\n### Feasibility (this generation)\nGenerate an **INFEASIBLE** trap task whose '
                     'impossibility can only be confirmed by **exploring** the UI (the option would '
                     'live in a specific panel/menu but is not actually there). Set "feasible": false, '
                     '"judge_timing": "explore", give "infeasible_reason", and an "explore_hint" '
                     'naming the surface to open and what options really exist there.')
    elif feas == 'feasible':
        lines.append('\n### Feasibility (this generation)\nGenerate a normal **feasible** task '
                     '("feasible": true) that is genuinely completable on this platform.')

    if directive.get('style'):
        lines.append(f'\n### Instruction style\nPhrase the task using the **{directive["style"]}** style.')

    if directive.get('avoid_verbs'):
        lines.append(f'\n### Verb diversity\nAvoid reusing these recently frequent verbs: {", ".join(directive["avoid_verbs"])}. Use a different action verb.')

    if directive.get('focus'):
        lines.append(f'\n### Focus\n{directive["focus"]}')

    return '\n'.join(lines) + '\n'


def build_user_prompt(os_key, existing_tasks, max_history=15, *, seed, directive=None):
    """Build the user prompt for task generation.

    The supplied seed defines the visible scene and valid targets for the new task.
    `directive` carries per-call targets (difficulty / style / avoid_verbs).
    """
    if not isinstance(seed, dict) or seed.get('os_key') != os_key:
        raise ValueError('Task generation requires a seed from the requested platform')
    if not isinstance(seed.get('global_state'), dict) or not seed['global_state'].get('prompt'):
        raise ValueError('Task generation requires the sampled seed description')
    os_config = OS_REGISTRY[os_key]
    domain = OS_TASK_DOMAINS[os_key]

    # Truncate existing tasks if too many (to avoid prompt bloat)
    if len(existing_tasks) > max_history:
        # Keep last N to bias toward avoiding recent duplicates
        shown_tasks = existing_tasks[-max_history:]
        truncate_note = f' (showing the most recent {max_history} of {len(existing_tasks)} total)'
    else:
        shown_tasks = existing_tasks
        truncate_note = ''

    if shown_tasks:
        existing_tasks_str = '\n'.join(f'- {t}' for t in shown_tasks) + truncate_note
    else:
        existing_tasks_str = '(No existing tasks yet; feel free to generate the first one.)'

    apps_list = '\n'.join(f'- {a}' for a in domain['common_apps'])
    scenarios_list = '\n'.join(f'- {s}' for s in domain['common_scenarios'])

    return TASK_GEN_USER_TEMPLATE.format(
        os_name=os_config['name'],
        os_category=os_config['category'],
        description=domain['description'],
        apps_list=apps_list,
        scenarios_list=scenarios_list,
        complexity_min=domain['complexity_range'][0],
        complexity_max=domain['complexity_range'][1],
        seed_section=_build_seed_section(seed),
        directive_section=_build_directive_section(domain, directive),
        existing_count=len(existing_tasks),
        existing_tasks_str=existing_tasks_str,
    )


def validate_task_obj(task_obj):
    """Machine-level structural check. Returns (ok: bool, reason: str)."""
    if not isinstance(task_obj, dict):
        return False, 'not a dict'
    task = task_obj.get('task', '')
    if not isinstance(task, str) or len(task.strip()) < 4:
        return False, 'task missing or too short'
    if not isinstance(task_obj.get('app'), str) or not task_obj['app'].strip():
        return False, 'missing app'
    if not isinstance(task_obj.get('category'), str) or not task_obj['category'].strip():
        return False, 'missing category'
    if task_obj.get('complexity') not in ('simple', 'medium', 'complex'):
        return False, 'invalid complexity'
    # Feasibility triad. Absent 'feasible' defaults to True (backward compatible:
    # older callers/tasks that never set it are treated as feasible).
    feasible = task_obj.get('feasible', True)
    if type(feasible) is not bool:
        return False, 'feasible must be a boolean'
    if feasible is False:
        timing = task_obj.get('judge_timing')
        if timing not in ('upfront', 'explore'):
            return False, 'infeasible task missing valid judge_timing'
        if not isinstance(task_obj.get('infeasible_reason'), str) or not task_obj['infeasible_reason'].strip():
            return False, 'infeasible task missing infeasible_reason'
        if timing == 'explore' and (not isinstance(task_obj.get('explore_hint'), str) or not task_obj['explore_hint'].strip()):
            return False, 'explore-timing task missing explore_hint'
    return True, ''


def generate_one_task(os_key, existing_tasks, max_retries=3, dedup_threshold=0.85,
                      registry=None, *, seed, directive=None):
    """Generate a single new task that passes structural + dedup checks.

    The task is constrained to the supplied seed's visible elements.
    `directive` carries per-call targets (difficulty / style / avoid_verbs).

    Returns:
        dict with 'task', 'app', 'category', 'complexity', or None if all retries failed
    """
    user_prompt = build_user_prompt(os_key, existing_tasks, seed=seed, directive=directive)

    if registry is None:
        registry = get_registry_for_os(os_key)

    for attempt in range(max_retries):
        raw = call_llm(TASK_GEN_SYSTEM_PROMPT, user_prompt)
        try:
            task_obj = json.loads(strip_json_fence(raw))
        except json.JSONDecodeError:
            print(f'  ⚠️  attempt {attempt+1}: JSON parse failed, retrying')
            continue

        # Machine-level structural validation (format/fields/types)
        ok, reason = validate_task_obj(task_obj)
        if not ok:
            print(f'  ⚠️  attempt {attempt+1}: validation failed ({reason}), retrying')
            continue

        task_text = task_obj['task'].strip()

        # Check dedup
        is_dup, similar, sim = registry.check_duplicate(task_text, dedup_threshold)
        if is_dup:
            print(f'  ⚠️  attempt {attempt+1}: duplicate (sim={sim:.3f}, vs "{similar}"), retrying')
            # Strengthen the diversity hint by adding the just-rejected task to existing
            existing_tasks = existing_tasks + [task_text]
            user_prompt = build_user_prompt(os_key, existing_tasks, seed=seed, directive=directive)
            continue

        return task_obj

    return None


def generate_tasks_for_seed(seed, n, dedup_threshold=0.85, focus=None, on_event=None,
                            long_horizon=False):
    """Serially generate up to n deduped auto-tasks for one seed.

    Shared by cli.py (expand --auto-tasks) and batch_generate.py. Each call owns
    an in-memory TaskRegistry. Candidates are generated serially within that
    call to check duplicates against accepted tasks and track recent verbs.
    Separate seeds can generate tasks concurrently.

    Args:
        seed: a loaded seed dict (must carry 'os_key').
        n: number of tasks to attempt.
        focus: optional directive 'focus' string (e.g. bias toward in-app ops).
        on_event: optional callback(kind, info) for progress/skip logging, where
            kind is 'start' | 'skip' and info is a dict. Lets callers print in
            their own style without this function owning I/O.

    Returns:
        list of accepted task dicts (length <= n; failures are skipped). Each
        dict carries at least 'task', plus feasibility fields when the task is
        an infeasible trap ('feasible'/'judge_timing'/'infeasible_reason'/
        'explore_hint'). Callers that only need the text read d['task'].
    """
    if type(n) is not int or n < 0 or not 0 <= dedup_threshold <= 1:
        raise ValueError('Invalid task count or dedup threshold')
    os_key = seed['os_key']
    # Compare against tasks accepted in this call. Separate calls start fresh.
    registry = TaskRegistry(None)
    # long_horizon: force every task to the 'complex' difficulty so the planner
    # produces a long multi-stage workflow (15+ actions), instead of the default
    # 30/40/30 simple/medium/complex mix.
    difficulties = ['complex'] * n if long_horizon else _difficulty_quota(n)
    # Feasibility quota: mostly feasible, a minority of upfront/explore traps.
    feasibilities = _feasibility_quota(n)
    recent_verbs = []
    accepted = []
    for i in range(n):
        directive = {
            'difficulty': difficulties[i],
            'style': SENTENCE_STYLES[i % len(SENTENCE_STYLES)],
            'avoid_verbs': list(dict.fromkeys(recent_verbs[-6:])),
            'feasibility': feasibilities[i],
        }
        if focus:
            directive['focus'] = focus
        if on_event:
            on_event('start', {'index': i, 'total': n, 'difficulty': difficulties[i],
                               'feasibility': feasibilities[i]})
        try:
            task_obj = generate_one_task(os_key, registry.tasks, max_retries=3,
                                         dedup_threshold=dedup_threshold,
                                         registry=registry, seed=seed, directive=directive)
        except Exception as e:
            if on_event:
                on_event('skip', {'index': i, 'total': n, 'reason': f'{type(e).__name__}: {str(e)[:90]}'})
            continue
        if task_obj is None:
            if on_event:
                on_event('skip', {'index': i, 'total': n, 'reason': 'max retries'})
            continue
        registry.add_task(task_obj['task'])
        recent_verbs.append(task_obj['task'].strip().split()[0].lower())
        accepted.append(task_obj)
    return accepted


def _feasibility_quota(count, weights=FEASIBILITY_WEIGHTS):
    """Turn the feasibility distribution into a concrete per-task label list.
    Labels: 'feasible' | 'infeasible_upfront' | 'infeasible_explore'. Feasible
    absorbs any rounding drift so the total equals count."""
    order = ['infeasible_upfront', 'infeasible_explore', 'feasible']
    quota = {k: int(round(count * weights[k])) for k in
             ('feasible', 'infeasible_upfront', 'infeasible_explore')}
    drift = count - sum(quota.values())
    quota['feasible'] += drift
    seq = []
    for k in order:
        seq += [k] * max(quota[k], 0)
    if len(seq) < count:
        seq += ['feasible'] * (count - len(seq))
    return seq[:count]


def _difficulty_quota(count, weights=DIFFICULTY_WEIGHTS):
    """Turn a target distribution into a concrete per-difficulty count list,
    e.g. count=10 → ['simple']*3 + ['medium']*4 + ['complex']*3."""
    order = ['simple', 'medium', 'complex']
    quota = {d: int(round(count * weights[d])) for d in order}
    # fix rounding drift so the total equals count
    drift = count - sum(quota.values())
    quota['medium'] += drift
    seq = []
    for d in order:
        seq += [d] * max(quota[d], 0)
    return seq[:count] if len(seq) >= count else seq + ['medium'] * (count - len(seq))

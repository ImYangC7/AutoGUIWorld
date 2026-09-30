# -*- coding: utf-8 -*-
"""Prompt for TASK <-> SEED relevance check.

Asks a multimodal model whether a trajectory's INITIAL screenshot (obs_00, a copy
of the seed's initial.png) actually provides the preconditions the task assumes:
the right app foregrounded, and the specific content/elements the task refers to
being present. This catches generated tasks that do not match their saved
initial scene (e.g. a "deduplicate train IDs in the docx" task shown over a
Writer doc that is actually an Ubuntu marketing article).
"""

VERDICTS = ('match', 'partial', 'mismatch')

_SYSTEM = (
    'You are auditing a GUI agent dataset. Each item has a TASK instruction and '
    'the INITIAL screenshot the agent starts from. Judge whether the screenshot '
    'provides the preconditions the task assumes.'
)


def build_relevance_prompt(task, target_app):
    fg = target_app or '(unspecified)'
    return (
        f'{_SYSTEM}\n\n'
        f'TASK:\n"""{task}"""\n\n'
        f'Expected foreground app (from metadata): {fg}\n\n'
        'Look at the INITIAL screenshot and decide how well it matches the task:\n'
        '- "match": the right app/screen is shown AND the specific content or '
        'UI elements the task refers to are actually present (or plausibly one '
        'step away, e.g. a menu that clearly exists). The task can sensibly begin '
        'from this screen.\n'
        '- "partial": the right app is open, but the specific content the task '
        'refers to is missing/different, OR only some preconditions hold. The task '
        'is about this app but the concrete data/objects it names are not visible.\n'
        '- "mismatch": the screenshot is about a different app/topic entirely, or '
        'the task\'s subject matter is absent — the task makes no sense starting '
        'here.\n\n'
        'Focus especially on CONTENT: if the task names a specific document, file, '
        'dataset, message, page, or record, check whether THAT thing is on screen. '
        'A generic "right app is open" is only "partial" if the named content is '
        'absent.\n\n'
        'Return ONLY a JSON object:\n'
        '{\n'
        '  "verdict": "match" | "partial" | "mismatch",\n'
        '  "app_ok": true | false,            // is the expected app foregrounded?\n'
        '  "content_present": true | false,   // is the task-specific content visible?\n'
        '  "screenshot_shows": "<=12 words: what the screenshot actually depicts",\n'
        '  "reason": "<=30 words: why this verdict"\n'
        '}'
    )

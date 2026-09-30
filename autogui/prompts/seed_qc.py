# -*- coding: utf-8 -*-
"""Quality-control prompt for SEED initial screenshots.

Seed images are rendered by a text-to-image model and are meant
to look like *real* OS / app screenshots. Generation models routinely fail on
fine UI detail: blurry or garbled text, ghosting / double-exposure, wrong
aspect ratios, melted geometry, duplicated chrome, etc. Those images poison the
downstream agent-training data, so each seed is graded by a strong multimodal
model when the QC runner is invoked.

Design choices:
- **Defect-list style, not scoring.** The model lists every concrete defect it
  finds from a *closed* taxonomy; an empty list means the image is clean. This
  is easier to act on and to aggregate than a 1-5 score.
- **Annotate only.** The runner writes the result back to seed.json; nothing is
  deleted. A human (or a later threshold pass) decides what to drop.

The three defect classes the user cares about most -- blurry text, ghosting,
wrong proportions -- are listed first and called out explicitly in the rules so
the model inspects them deliberately.
"""

# Closed taxonomy. Keep keys stable: the runner aggregates by these strings.
DEFECT_TAXONOMY = [
    'blurry_text',      # text anywhere is soft / smeared / low-res / hard to read
    'garbled_text',     # fake glyphs, gibberish words, melted/mixed-script letters
    'ghosting',         # double-exposure, semi-transparent echoes, faint duplicate edges
    'wrong_aspect',     # stretched/squished UI, implausible element or screen proportions
    'warped_geometry',  # wavy lines that should be straight, melted / impossible UI shapes
    'duplicated_ui',    # two taskbars/docks/menu bars, repeated identical windows or icons
    'incoherent_layout',# floating fragments, nonsensical overlaps, broken / cut-off windows
    'visual_artifact',  # noise blobs, color smears, JPEG-like mush, nonsense textures
    'not_a_screenshot', # not a UI screenshot at all (3D device render, photo, abstract image)
]

# Severities the model may assign. The runner derives pass/fail from these.
SEVERITIES = ['minor', 'major', 'critical']


SEED_QC_TEMPLATE = """You are a strict visual quality inspector for AI-generated GUI screenshots.

The image below was produced by a text-to-image model and is supposed to look like a REAL, photorealistic screenshot of: {os_name}. It is the starting screen for a GUI agent, so any rendering flaw is harmful.

Your job is NOT to judge whether the *content* (which apps, which website, login identity) is "correct". Judge ONLY the **rendering quality / visual fidelity** -- does it look like a genuine, crisp screenshot, or does it betray generation artifacts?

## Inspect these closely (most important first)

1. **Text sharpness (blurry_text):** Zoom into every label, menu item, button, filename, address bar, and body text. Is the text crisp and fully legible, or is it soft, smeared, fuzzy, or low-resolution? Real screenshots have pixel-sharp text.
2. **Text validity (garbled_text):** Are the letters real, well-formed words, or fake/gibberish glyphs, melted letterforms, nonsense character soup, or wrongly-mixed scripts? Generators often "hallucinate" plausible-looking but meaningless text.
3. **Ghosting (ghosting):** Look for double-exposure, semi-transparent duplicate edges, faint echo copies of icons/windows/cursors, or a translucent "after-image" overlapping a solid element.
4. **Proportions (wrong_aspect):** Is the overall image and its elements proportioned like a real display? Watch for stretched/squished windows, icons with implausible aspect ratios, circles that became ovals, or a screen that does not match a real monitor/phone shape.
5. Other generation failures: **warped_geometry** (wavy lines that should be straight, melted shapes), **duplicated_ui** (two taskbars / docks / menu bars, repeated identical windows or icons), **incoherent_layout** (floating UI fragments, nonsensical overlaps, broken or cut-off windows), **visual_artifact** (noise blobs, color smears, mushy regions, nonsense textures), **not_a_screenshot** (a 3D device render, a photo of a screen, or an abstract image rather than a flat UI screenshot).

## How to report

Use ONLY these defect `type` values:
{taxonomy}

Assign each defect a `severity`:
- "critical": ruins the image; it cannot be used (e.g. pervasive garbled text, not a screenshot, gross distortion).
- "major": clearly visible flaw that a human would notice immediately (e.g. the main window's text is blurry, obvious ghosting on a key element).
- "minor": small / localized imperfection that does not really hurt usability (e.g. one tiny background label slightly soft).

Verdict rule (apply it yourself):
- "fail" if there is ANY defect with severity "critical" or "major".
- "pass" if the image is clean OR has only "minor" defects.

## Output format

Output a STRICT JSON object only -- no markdown, no ```json fences, no prose:

{{
  "defects": [
    {{"type": "<one of the taxonomy keys>", "severity": "minor|major|critical", "region": "where on screen (e.g. 'center window title bar')", "detail": "one short phrase describing the flaw"}}
  ],
  "verdict": "pass" | "fail",
  "summary": "one sentence overall judgement"
}}

If the image is clean, return "defects": [] and "verdict": "pass".
"""


def build_seed_qc_prompt(os_name):
    """Render the QC prompt for a seed of the given OS (human-readable name)."""
    return SEED_QC_TEMPLATE.format(
        os_name=os_name,
        taxonomy=', '.join(DEFECT_TAXONOMY),
    )

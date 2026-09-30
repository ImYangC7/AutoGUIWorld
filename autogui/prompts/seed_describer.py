# -*- coding: utf-8 -*-
"""System prompt for SEED-only generation.

Used in 'seed' mode: takes OS + aesthetic + env_state, asks the model adapter to
write a rich English description (global_state.prompt) that Image-2 will
use to render the initial screenshot. NO actions are generated here.
"""

import json


# Layout-guidance block injected into the rules, chosen by OS category. Desktop
# and browser get the multi-window layout block; mobile gets a home-screen grid
# block. Keeping these separate means a mobile prompt never carries desktop
# window-stacking instructions (and vice versa).
DESKTOP_LAYOUT_DIRECTIVE = """- **[WINDOW LAYOUT — IMPORTANT]** When multiple windows are open (see the Open windows list in the Initial Environment State):
  * Explicitly divide the screen into positional regions according to window_layout (center / top-left / top-right / bottom-left / bottom-right / far-background).
  * Write a separate sentence for **every** window, and each sentence must include three things:
      1) the window's **precise on-screen position**;
      2) the **app name + the specific view/content it is currently showing** (open file, page, panel, tab, etc.);
      3) its **occlusion / stacking relationship** with neighboring windows (overlapping / partially occluded / behind / docked beside).
  * The target_window (the one marked foreground) should be the **largest, most centered, and clearest**; the other background windows should be partially occluded.
  * Use spatial layout connectors to organize the sentences: in the center / in the top-right / behind it / partially hidden by / cascaded over."""

MOBILE_LAYOUT_DIRECTIVE = """- **[WRITE IT LIKE A PERSON DESCRIBING A REAL SCREENSHOT]** Do NOT write a rigid "Row 1 column 1 / Row 1 column 2" grid checklist. Instead describe the home screen the way a human would narrate a photo of their phone: flowing sentences, one per row, naming the apps left-to-right in that row, with natural spatial connectors (top row / next row / below that / bottom-left). The goal is a believable real screenshot, not a render spec.
  * **Status bar** at the very top: clock on the left; on the right, the listed indicator glyphs, the network label, and the battery with its exact percentage. Keep it to one short sentence.
  * **Wallpaper**: describe the given scene vividly and concretely (subject, composition, mood, color) — this is what makes it look real. Note that app labels stay legible over it.
  * **App grid**: walk through it row by row in natural language. For **well-known apps just name them** (Steam, 美团, Gmail, 王者荣耀, QQ…) and trust the model to draw the real icon — do NOT over-specify every icon's color and glyph. Only add a brief look-hint for an app the model might not know. Every tile is a single app icon (no folders). Mention a small **red unread badge** only on the tiles that carry one. If a row is partly empty, say so ("the rest of the row is empty") — real home screens have blank spots.
  * **Dock**: one sentence for the fixed bottom row and its few icons (with any badges).
  * **Page indicator** above the dock: a short phrase (current page as a highlighted bar, the others as small dots).
  * Keep every app label and badge number sharp and correctly spelled, the grid evenly aligned — but say this once, briefly, not per icon.
  * **State the platform explicitly**: begin the prompt with the given prompt-prefix so the OS and its design language (e.g. "iOS 26 with Apple Liquid Glass design", "Android 16 Material 3 Expressive") are named up front, and let that style govern the status bar, dock, and overall chrome.
  * **App icons must be the apps' REAL, full-color brand icons** (each keeps its own logo and colors), in the platform's native icon shape. The theme/wallpaper colors only affect the WALLPAPER and system chrome — do NOT recolor, tint, or frost the app icons to match the wallpaper or an accent color, and never make all icons look like the same uniform glass tile. On iOS 26, icons may carry a subtle glossy Liquid-Glass sheen/highlight but keep their full brand color and remain instantly recognizable."""

# The "describe every item" checklist, also category-specific.
DESKTOP_DESCRIBE_ITEMS = """  * login identity (username / email / avatar area)
  * the per-window position / content / stacking & occlusion described above
  * desktop file clutter level
  * system notifications / Dynamic Island / popups / control center
  * status bar (battery, WiFi, signal)"""

MOBILE_DESCRIBE_ITEMS = """  * the status bar (time, indicator glyphs, network label, battery percentage)
  * the wallpaper scene, described vividly
  * the apps in each row (named); leave blank spots where the row is empty
  * the few unread badges that exist
  * the dock and the page indicator"""

# Browser (pure web): the screenshot is an integral-screen Chrome window — browser
# chrome on top, ONE active web page filling the content area. No host OS desktop,
# Dock, taskbar, or other app windows. The active page must look like the real
# production website, keeping its native brand/CSS colors (the sampled accent must
# NOT recolor page links, buttons, logos, charts, icons, nav, or cards).
WEB_LAYOUT_DIRECTIVE = """- **[BROWSER-ONLY — IMPORTANT]** This is a pure web / browser-only screenshot. Do NOT draw any Windows/macOS/Ubuntu desktop, taskbar, Dock, desktop icons, or other application windows. Render only the Chrome window: browser chrome on top, one active web page below it.
  * **Chrome chrome**: the tab bar (active tab title + background tab titles/favicons, plus tab groups if present), the address bar (showing the active tab's real domain or a plausible URL), the bookmarks bar, extension icons, and a permission prompt / download bar ONLY if the Initial Web State says one exists.
  * **Active page**: fully describe the one active web page — its brand/site, page type, primary navigation, and the core UI (search box, filters, tables, forms, media player, cart, list rows, cards, tabs, buttons) so later GUI actions have concrete targets. Scroll position is at the top unless the state says otherwise.
  * **Native colors**: the real website's design system and Chrome chrome take priority over the decorative aesthetic. Keep each site's recognizable brand colors, link/button/chart/icon colors, typography, spacing, and density. Do NOT apply the sampled accent color to page content; it may only subtly tint browser-level details.
  * **Background tabs** appear only as titles/favicons in the tab strip — never render their page contents.
  * Do NOT draw cookie banners, cookie/privacy consent dialogs, or newsletter popups. Do not invent sites, tabs, logins, or banners not present in the Initial Web State; use simple realistic defaults for anything unspecified."""

WEB_DESCRIBE_ITEMS = """  * the signed-in / guest / incognito state (only as it shows in the Chrome UI)
  * the Chrome chrome: tab bar (active + background tab titles), address bar URL, bookmarks bar, extension icons
  * the active web page: brand/site, layout, and the interactive elements listed above
  * any permission prompt / pending download — only if present in the state (never a cookie/consent banner)"""


# Per-category (layout_directive, describe_items) injected into the template.
# Browser is its own surface, parallel to desktop/mobile (no os_key literals);
# anything not listed (desktop) falls back to the DESKTOP_* pair.
_CATEGORY_DIRECTIVES = {
    'mobile':  (MOBILE_LAYOUT_DIRECTIVE, MOBILE_DESCRIBE_ITEMS),
    'browser': (WEB_LAYOUT_DIRECTIVE, WEB_DESCRIBE_ITEMS),
}


SEED_DESCRIBER_TEMPLATE = """You are a GUI initial-state describer.

Given an operating system, a visual style, and an environment state, write a **detailed English initial-screenshot description** (global_state.prompt) that the configured image generation model will use to render the initial screenshot.

## Operating System Environment

{os_json}

## Visual Style

{style_directive}

## Initial Environment State

{env_state_text}

## Task

Do NOT generate any action. Output a single JSON object containing a global_state field:

```
{{
  "global_state": {{
    "environment": "OS name and version",
    "visible_elements": ["each visible UI element, annotating each window element with its on-screen position, e.g. 'Finder (top-right, screenshot grid)'"],
    "target_window": "foreground app name (if any; must match the window marked foreground in the Initial Environment State)",
    "prompt": "<rich English screenshot prompt>"
  }}
}}
```

## Rules for writing global_state.prompt

- Must begin with "{prompt_prefix}"
{layout_directive}
- Must **fully describe every item** in the Initial Environment State:
{describe_items}
- Incorporate the style description: {style_directive}
- No red bounding box.
- End with "Photorealistic, high fidelity UI screenshot style."

## Output Format

Output a strict JSON object only. No Markdown, no ```json fences, no explanatory text.
"""


def build_seed_describer_prompt(os_config, style_directive, env_state_text):
    """Describe the sampled GUI state before any task is selected."""
    layout_directive, describe_items = _CATEGORY_DIRECTIVES.get(
        os_config.get('category'), (DESKTOP_LAYOUT_DIRECTIVE, DESKTOP_DESCRIBE_ITEMS),
    )
    return SEED_DESCRIBER_TEMPLATE.format(
        os_json=json.dumps(os_config, ensure_ascii=False, indent=2),
        style_directive=style_directive,
        env_state_text=env_state_text,
        prompt_prefix=os_config['prompt_prefix'],
        layout_directive=layout_directive,
        describe_items=describe_items,
    )

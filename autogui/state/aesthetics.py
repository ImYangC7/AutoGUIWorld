# -*- coding: utf-8 -*-
"""Aesthetic style space with random sampling and constraint enforcement.

The aesthetic space is defined as independent parameter ranges.
At generation time, a random combination is sampled, filtered by OS constraints,
and validated against conflict rules.
"""

import random


# === Parameter Space Definition ===

AESTHETIC_PARAMS = {
    'theme': ['light', 'dark'],
    'accent_color': ['blue', 'purple', 'green', 'red', 'orange', 'pink', 'teal'],
    'wallpaper_type': ['solid_color', 'gradient', 'landscape_photo', 'abstract_art', 'geometric_pattern'],
    'wallpaper_tone': ['warm', 'cool', 'neutral', 'vibrant'],
    'icon_shape': ['circle', 'rounded_square', 'squircle', 'adaptive'],
    'icon_fill': ['flat_color', 'gradient', 'outlined', 'glassmorphism'],
    'font_size': ['small', 'default', 'large', 'extra_large'],
    'display_density': ['compact', 'default', 'comfortable'],
    'corner_radius': ['none', 'small_4px', 'medium_8px', 'large_16px', 'full_pill'],
    'shadow_depth': ['none', 'subtle', 'medium', 'strong'],
    'transparency': ['opaque', 'slight_blur', 'heavy_frosted_glass'],
}


# === OS-level parameter filters ===
# Each OS lists parameters it does NOT support or restricts.

OS_PARAM_OVERRIDES = {
    'windows11': {
        'icon_shape': ['rounded_square', 'adaptive'],  # Windows uses squares
    },
    # macOS ships a fixed Apple HIG look, so most style params are NOT user-
    # variable — only theme (light/dark), accent color, and wallpaper genuinely
    # change on a real Mac. The remaining appearance params are pinned to the
    # real macOS values here (single-value lists = sampled but constant), so the
    # style directive never emits un-macOS combos like full-pill corners or
    # glassmorphism icons.
    'macos': {
        # --- genuinely variable on a real Mac ---
        # macOS Sequoia real accent colors (System Settings > Appearance),
        # dropping the generic 'teal'. theme + wallpaper_type stay fully sampled.
        'accent_color': ['blue', 'purple', 'pink', 'red', 'orange', 'green'],
        # Wallpaper restricted to STOCK macOS wallpapers that all carry rich,
        # bright visual CONTENT (photo / dynamic / gradient). Excludes near-black
        # options (graphite "Macintosh", plain solids) that collapse to black
        # under dark mode. Gives visual diversity within a genuine macOS
        # distribution.
        'wallpaper_type': ['macos_sequoia_forest', 'macos_sequoia_sonoma',
                           'macos_sequoia_scenic', 'macos_sequoia_national',
                           'macos_sonoma_horizon', 'macos_ventura_swirl',
                           'macos_bigsur_peaks', 'macos_monterey_flow',
                           'macos_solar_gradient'],
        # --- pinned to the real fixed macOS look (single value = no variation) ---
        'icon_shape': ['squircle'],          # macOS app icons are squircles
        'icon_fill': ['gradient'],           # subtle gradient, not flat/outlined/glass
        'corner_radius': ['large_16px'],     # ~10px rounded windows/controls
        'font_size': ['default'],            # SF Pro at system size
        'display_density': ['default'],
        'shadow_depth': ['subtle'],          # soft window shadows
        'transparency': ['slight_blur'],     # native vibrancy/material blur
        # wallpaper_tone is inert for macOS (named-sentinel wallpapers ignore
        # tone in aesthetic_to_style_directive); pinned so it stops sampling.
        # Tone still varies for OSes using generic "<tone>-toned" wallpapers.
        'wallpaper_tone': ['neutral'],
    },
    'android': {
        'icon_shape': ['circle', 'rounded_square', 'squircle', 'adaptive'],  # Android supports all
    },
    'ios': {
        'icon_shape': ['rounded_square', 'squircle'],  # iOS uses fixed squircle, no adaptive
        'display_density': ['default'],  # iOS doesn't expose density control
    },
    'chrome_browser': {
        'wallpaper_type': ['solid_color'],  # browser has no wallpaper, just tab content
        'wallpaper_tone': ['neutral'],
        'icon_shape': ['rounded_square'],  # browser tabs are fixed
        'display_density': ['default', 'compact'],
    },
    'ubuntu2404': {
        'icon_shape': ['circle', 'rounded_square', 'squircle'],  # GNOME icons
    },
}


# === Sampling weights (optional, per-OS) ===
# Without an entry a param is sampled uniformly (rng.choice). Real phone
# wallpapers are mostly photos / gradients / solid colors; flashy abstract or
# geometric ones are rare. Uniform sampling made ~47% of phone seeds look
# unnaturally "arty", so both mobile OSes share this realistic bias. Desktop /
# browser keep uniform sampling (no entry).
_MOBILE_WALLPAPER_WEIGHTS = {'landscape_photo': 0.34, 'gradient': 0.28,
                            'solid_color': 0.22, 'abstract_art': 0.08,
                            'geometric_pattern': 0.08}

PARAM_WEIGHTS = {
    'android': {'wallpaper_type': _MOBILE_WALLPAPER_WEIGHTS},
    'ios': {'wallpaper_type': _MOBILE_WALLPAPER_WEIGHTS},
}


# === Fixed (non-randomized) aesthetics ===
# Some OSes ship a highly recognizable stock skin. Randomizing it produced
# unrealistic desktops (e.g. rainbow geometric wallpapers on Ubuntu, which in
# reality always boots into the light Yaru theme with an orange accent and the
# aubergine 'Noble Numbat' wallpaper). For these OSes we pin the aesthetic to
# the real default and skip sampling entirely (no theme/accent/wallpaper vary).
OS_FIXED_AESTHETIC = {
    'ubuntu2404': {
        'theme': 'light',
        'accent_color': 'orange',
        'wallpaper_type': 'default_ubuntu',   # named below in NAMED_WALLPAPERS
        'wallpaper_tone': 'warm',
        'icon_shape': 'squircle',
        'icon_fill': 'flat_color',
        'font_size': 'default',
        'display_density': 'default',
        'corner_radius': 'large_16px',
        'shadow_depth': 'subtle',
        'transparency': 'opaque',
    },
    # macOS samples theme (light/dark), a real macOS accent color, and a STOCK
    # Sequoia wallpaper (see the macos entry in OS_PARAM_OVERRIDES), giving
    # visual diversity while staying within a genuine macOS distribution.
    # Generated seeds use the platform appearance settings below.
}

# Wallpaper sentinels that map to a concrete, named stock wallpaper description
# (instead of the generic "<tone>-toned <type> wallpaper" phrasing).
NAMED_WALLPAPERS = {
    'default_ubuntu': ("the stock Ubuntu 24.04 'Noble Numbat' desktop wallpaper "
                       "(a warm aubergine-purple gradient backdrop with soft orange highlights)"),
    # Stock macOS wallpapers (real selectable options across recent macOS
    # releases — all ship with the OS). All are bright, content-rich images so
    # dark mode never collapses them to black.
    'macos_sequoia_forest': ("the stock macOS Sequoia default wallpaper: a "
                             "photographic stand of tall sequoia/redwood tree "
                             "trunks in a sunlit green forest with faint ground mist"),
    'macos_sequoia_sonoma': ("a stock macOS dynamic wallpaper: smooth flowing "
                             "ribbons of vivid saturated color (blue, teal, "
                             "magenta, orange) sweeping across the screen — bright "
                             "and colorful, the Sonoma/Sequoia aurora style"),
    'macos_sequoia_scenic': ("a stock macOS Sequoia scenic photo wallpaper: a "
                             "vivid daytime landscape (sunlit mountain range or "
                             "coastline under a bright sky), rich color and detail"),
    'macos_sequoia_national': ("the stock 'Sequoia' aerial wallpaper: a dramatic "
                               "top-down aerial photo of Sequoia National Park — "
                               "snow-dusted mountain ridges and a winding green "
                               "river valley, rich natural color"),
    'macos_sonoma_horizon': ("the stock macOS Sonoma wallpaper: layered rolling "
                             "hills receding into a warm hazy horizon at golden "
                             "hour, soft orange-and-blue gradient sky"),
    'macos_ventura_swirl': ("the stock macOS Ventura wallpaper: bold smooth "
                            "3D-rendered ribbons of blue, orange and red swirling "
                            "around a bright center, clean gradient background"),
    'macos_bigsur_peaks': ("the stock macOS Big Sur wallpaper: stylized layered "
                           "mountain peaks under a clear graduated dawn sky, calm "
                           "blue-to-amber tones"),
    'macos_monterey_flow': ("the stock macOS Monterey wallpaper: flowing "
                            "translucent glass-like curves in vivid blue, purple "
                            "and pink over a light background"),
    'macos_solar_gradient': ("a stock macOS 'Solar Gradients' wallpaper: a smooth "
                             "vivid two-tone gradient (warm sunrise colors blending "
                             "into deep blue), clean and bright"),
}


def _sample_param(param, os_key, rng):
    """Pick one value for param, honoring PARAM_WEIGHTS[os_key][param] if present
    (restricted to the OS-allowed options), else uniform over allowed options."""
    options = _get_param_options(param, os_key)
    weights = PARAM_WEIGHTS.get(os_key, {}).get(param)
    if weights:
        w = [weights.get(opt, 0.0) for opt in options]
        if sum(w) > 0:
            return rng.choices(options, weights=w, k=1)[0]
    return rng.choice(options)


# === Conflict rules ===
# List of (condition, exclusion) pairs.
# If condition matches, the exclusion is applied.

CONFLICT_RULES = [
    # high contrast concepts conflict with transparency effects
    {
        'if': {'theme': 'dark', 'shadow_depth': 'strong'},
        'then_exclude': {'transparency': ['heavy_frosted_glass']},
    },
    # glassmorphism icons need transparency support
    {
        'if': {'transparency': 'opaque'},
        'then_exclude': {'icon_fill': ['glassmorphism']},
    },
    # full pill corners don't mix well with no-radius elsewhere
    {
        'if': {'corner_radius': 'none'},
        'then_exclude': {'icon_shape': ['squircle']},
    },
]


def _get_param_options(param, os_key):
    """Get available options for a parameter, filtered by OS constraints."""
    base_options = AESTHETIC_PARAMS[param]
    overrides = OS_PARAM_OVERRIDES.get(os_key, {})
    if param in overrides:
        return overrides[param]
    return base_options


def _check_conflicts(sampled):
    """Check if a sampled combination violates any conflict rules.
    Returns a dict of param -> excluded_values to re-sample."""
    exclusions = {}
    for rule in CONFLICT_RULES:
        condition = rule['if']
        if all(sampled.get(k) == v for k, v in condition.items()):
            for param, excluded_vals in rule['then_exclude'].items():
                if param not in exclusions:
                    exclusions[param] = set()
                exclusions[param].update(excluded_vals)
    return exclusions


def sample_aesthetic(os_key, rng=None):
    """Randomly sample an aesthetic configuration for a given OS.

    Args:
        os_key: Operating system key (from OS_REGISTRY)
        rng: Optional random.Random instance for reproducibility

    Returns:
        dict with a value for each aesthetic parameter
    """
    if rng is None:
        rng = random.Random()

    # OSes with a pinned stock skin skip sampling entirely (see OS_FIXED_AESTHETIC).
    if os_key in OS_FIXED_AESTHETIC:
        return dict(OS_FIXED_AESTHETIC[os_key])

    # First pass: sample each param from OS-filtered options (weighted if configured)
    sampled = {}
    for param in AESTHETIC_PARAMS:
        sampled[param] = _sample_param(param, os_key, rng)

    # Second pass: fix conflicts (up to 3 attempts)
    for _ in range(3):
        exclusions = _check_conflicts(sampled)
        if not exclusions:
            break
        for param, excluded_vals in exclusions.items():
            if sampled.get(param) in excluded_vals:
                options = [v for v in _get_param_options(param, os_key) if v not in excluded_vals]
                if options:
                    sampled[param] = rng.choice(options)

    return sampled


def aesthetic_to_style_directive(os_config, aesthetic):
    """Convert OS config + sampled aesthetic into a natural language style directive.

    This string is injected into prompts to guide image generation.

    Mobile vs desktop differ on a key point: on a phone HOME SCREEN the app icons
    are REAL, full-color brand icons whose look is owned by each app — the random
    aesthetic must NOT recolor or glass-ify them (that produced washed-out,
    identical-looking icons). So for mobile the random params only drive the
    *wallpaper / theme*; the icon treatment is fixed to the platform's native look
    (carried in os_config['design_language']). Desktop keeps the full directive.
    """
    if os_config.get('category') == 'mobile':
        return _mobile_style_directive(os_config, aesthetic)

    parts = []

    # Theme
    theme = aesthetic['theme']
    parts.append(f"{'Dark' if theme == 'dark' else 'Light'} mode")

    # Accent
    parts.append(f"{aesthetic['accent_color']} accent color")

    # Wallpaper
    wp_type = aesthetic['wallpaper_type']
    if wp_type in NAMED_WALLPAPERS:
        parts.append(NAMED_WALLPAPERS[wp_type])
    else:
        wp = wp_type.replace('_', ' ')
        tone = aesthetic['wallpaper_tone']
        parts.append(f"{tone}-toned {wp} wallpaper")

    # Icons
    icon = f"{aesthetic['icon_shape'].replace('_', ' ')} {aesthetic['icon_fill'].replace('_', ' ')} icons"
    parts.append(icon)

    # Font & density
    font = aesthetic['font_size'].replace('_', ' ')
    density = aesthetic['display_density']
    parts.append(f"{font} font size, {density} density")

    # Micro UI
    radius = aesthetic['corner_radius'].replace('_', ' ')
    parts.append(f"{radius} corner radius")

    shadow = aesthetic['shadow_depth']
    if shadow != 'none':
        parts.append(f"{shadow} shadows")

    transparency = aesthetic['transparency']
    if transparency != 'opaque':
        parts.append(f"{transparency.replace('_', ' ')} effect")

    # Combine with OS design language
    design_lang = os_config['design_language']
    return f"{design_lang} style. " + ". ".join(parts) + "."


def _mobile_style_directive(os_config, aesthetic):
    """Style directive for a phone home screen.

    The random aesthetic only sets the THEME + WALLPAPER; app icons keep their
    real brand colors and the platform-native icon shape (no recoloring, no
    forced glassmorphism). Icon treatment comes from the OS design language.
    """
    theme = 'Dark mode' if aesthetic['theme'] == 'dark' else 'Light mode'
    wp = aesthetic['wallpaper_type'].replace('_', ' ')
    tone = aesthetic['wallpaper_tone']
    design_lang = os_config['design_language']
    return (
        f"{design_lang} style. {theme}. The wallpaper is a {tone}-toned {wp}. "
        "App icons are the apps' REAL, full-color brand icons (each app keeps its "
        "own logo and colors) in the platform's native icon shape — do NOT recolor, "
        "tint, or wash them out to match the wallpaper or any accent color, and do "
        "NOT make every icon look like the same frosted glass; keep them crisp, "
        "varied, and instantly recognizable."
    )

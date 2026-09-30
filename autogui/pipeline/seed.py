# -*- coding: utf-8 -*-
"""SEED pipeline: sample (OS x aesthetic x env_state) -> render initial.png -> persist seed."""

import json
import random

from autogui.state.registry import OS_REGISTRY
from autogui.state.aesthetics import sample_aesthetic, aesthetic_to_style_directive
from autogui.state.environment import (
    sample_environment_state, clean_state,
    state_to_descriptive_text, has_blocking_state, sample_windows,
    sample_browser_tabs, sample_dock,
)
from autogui.state.mobile import sample_home_screen
from autogui.prompts.seed_describer import build_seed_describer_prompt
from autogui.clients.llm import call_llm
from autogui.clients.image import generate_image
from autogui.utils.jsonio import strip_json_fence
from autogui.storage.manager import reserve_seed_id, save_seed
from autogui.utils.cost import get_logger


def create_seed(os_key: str, seed_rng: int | None = None, rich_state: bool = False,
                skip_state: bool = False, quality: str = 'high',
                web_category: str | None = None, web_site: str | None = None,
                web_url: str | None = None, web_content: str | None = None,
                seed_id: str | None = None) -> str:
    """Sample a GUI scene, render its initial screenshot, and save the seed.

    Browser category, site, URL, and page descriptions can constrain the sampled
    browser surface. A task is supplied or generated only after the seed exists.
    Returns the allocated seed identifier.
    """
    if os_key not in OS_REGISTRY or quality not in ('low', 'medium', 'high'):
        raise ValueError('Unknown platform or image quality')
    if any((web_category, web_site, web_url, web_content)) and OS_REGISTRY[os_key]['category'] == 'mobile':
        raise ValueError('Web constraints do not apply to mobile home screens')
    if (web_url or web_content) and OS_REGISTRY[os_key]['category'] != 'browser':
        raise ValueError('Explicit page URLs/content require chrome_browser')
    rng = random.Random(seed_rng) if seed_rng is not None else random.Random()
    os_config = OS_REGISTRY[os_key]
    aesthetic = sample_aesthetic(os_key, rng)
    style_directive = aesthetic_to_style_directive(os_config, aesthetic)

    if skip_state:
        env_state = clean_state(os_key)
    else:
        env_state = sample_environment_state(os_key, rich=rich_state, rng=rng)
    if os_config['category'] == 'mobile':
        # Layered home-screen inventory (mobile): status bar / wallpaper /
        # app grid / folders / dock / page indicator. Mobile counterpart of
        # the desktop window inventory below. Only when unlocked — a locked
        # phone shows a lock screen, not the home grid.
        if env_state.get('login_state') == 'unlocked':
            env_state['home_screen'] = sample_home_screen(os_key, env_state, aesthetic, rng=rng)
    elif os_config['category'] == 'browser':
        # Structured tab inventory (pure-web browser): one active tab (the
        # task target surface) + background tabs. Web counterpart of the
        # desktop window / mobile home-screen inventory.
        env_state = sample_browser_tabs(env_state, rng=rng,
                                        web_category=web_category, web_site=web_site,
                                        web_url=web_url, web_content=web_content)
    else:
        # Structured window inventory (desktop OS): reproducible position + content.
        windows = sample_windows(os_key, env_state, rng=rng,
                                 web_category=web_category, web_site=web_site)
        if windows:
            env_state['windows'] = windows
        # Dock is sampled after windows so its running indicators match the
        # open apps (ubuntu2404 + logged_in only; returns None otherwise).
        dock = sample_dock(os_key, env_state, rng=rng)
        if dock:
            env_state['dock'] = dock

    env_state_text = state_to_descriptive_text(os_key, env_state)
    blockers = has_blocking_state(env_state)

    print(f'\n{"="*60}')
    print(f' Creating seed for {os_config["name"]}')
    print(f' Image size: {os_config["image_size"]}')
    print(f' Style: {style_directive[:80]}...')
    print(f' Blockers: {len(blockers)}')
    for b in blockers:
        print(f'   🚧 {b}')
    print(f'{"="*60}')

    # 1. Expand env_state into a detailed global_state.prompt.
    print('\n🧠 LLM 扩充初始状态描述...')
    sys_prompt = build_seed_describer_prompt(os_config, style_directive, env_state_text)
    raw = call_llm(sys_prompt, f'OS: {os_key}, please generate the global_state JSON.')
    try:
        seed_plan = json.loads(strip_json_fence(raw))
    except (ValueError, TypeError):
        raise ValueError('Seed description is not valid JSON') from None
    if not isinstance(seed_plan, dict) or not isinstance(seed_plan.get('global_state'), dict):
        raise ValueError('Seed description must contain a global_state object')
    global_state = seed_plan['global_state']
    if not isinstance(global_state.get('prompt'), str) or not global_state['prompt'].strip():
        raise ValueError('Seed description must contain a nonempty visual prompt')
    # Anchor target_window to the foreground window we actually sampled (if any).
    # Desktop-only: mobile seeds carry no 'windows', so fg stays None and this is
    # a no-op (a phone home screen has no foreground "target window").
    fg = next((w for w in env_state.get('windows', []) if w.get('role') == 'foreground'), None)
    if fg and not global_state.get('target_window'):
        global_state['target_window'] = fg['app']
    # Browser: the target surface is the active tab; anchor to its site so the
    # task generator and trajectory planner share the same foreground reference.
    active_tab = env_state.get('active_tab')
    if active_tab and not global_state.get('target_window'):
        site = active_tab.get('site')
        global_state['target_window'] = f'Google Chrome — {site}' if site else 'Google Chrome active tab'
    print(f'✅ global_state.prompt 长度: {len(global_state["prompt"])} chars')

    # 2. Render the initial screenshot through the image adapter.
    print('\n🎨 渲染初始截图...')
    image_size = os_config['image_size']
    image_bytes = generate_image(
        global_state['prompt'],
        size=image_size, quality=quality,
    )

    # 3. Persist seed
    if seed_id is None:
        seed_id = reserve_seed_id(os_key)
    seed_data = {
        'os_key': os_key,
        'aesthetic': aesthetic,
        'env_state': env_state,
        'env_state_text': env_state_text,
        'blockers': blockers,
        'image_size': image_size,
        'style_directive': style_directive,
        'global_state': global_state,
    }
    sd = save_seed(seed_id, seed_data, image_bytes)
    get_logger().flush()

    print(f'\n✅ Seed 创建完成: {seed_id} → {sd}')
    return seed_id

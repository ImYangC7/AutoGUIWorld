# -*- coding: utf-8 -*-
"""TRAJECTORY pipeline: expand a fixed seed into an obs/act frame sequence.

obs chain (clean observations) + act frames (red-box overlays):
  obs_k = edit(obs_{k-1}, action-after result)        spine, always clean
  act_k = obs_{k-1} pixels + red box(es) drawn by PIL  (pointing actions),
          located via vision grounding on obs_{k-1}; pixel-identical to obs.
          Non-pointing actions reuse obs_{k-1} as their act frame (no box).
"""

import json
import os
import re

from autogui.clients.backend import BackendConfigurationError
from autogui.state.registry import OS_REGISTRY, ACTION_SPACES
from autogui.pipeline.step_utils import element_descs, effective_actions, trajectory_complete, validate_plan
from autogui.prompts.trajectory_planner import (
    build_trajectory_planner_prompt,
    VOYAGER_SYS, voyager_user_prompt, render_edit_prompt,
)
from autogui.clients.llm import call_llm, call_llm_vision
from autogui.utils.credentials import mask_credentials, unmask_credentials
from autogui.clients.image import edit_with_ref
from autogui.clients.box_backends import annotate_act_frame
from autogui.clients.grounding import DEFAULT_GROUNDER, GROUNDERS
from autogui.utils.jsonio import strip_json_fence
from autogui.utils.cost import get_logger as get_cost_logger
from autogui.tasks.dedup import TaskRegistry
from autogui.storage.manager import (
    load_seed, reserve_trajectory_id, init_trajectory, finalize_trajectory,
    task_registry_path,
)

# LocateAnything-3B is the default grounder for every OS category (desktop /
# mobile / browser); it returns real element boxes directly. The MAI-UI and
# GPT-5.5 backends remain selectable via the `grounder` argument / CLI /
# AUTOGUI_GROUNDER.


def gen_voyager_frame(prev_obs_path, action_step, prompt_prefix, max_attempts=3,
                      high_level_plan=None, step_index=None, total_steps=None,
                      steps_done=None):
    """Closed-loop Voyager output for one step: {voyager_prompt, thought,
    action_abstract}.

    Voyager plays two roles in one call, from the REAL previous frame plus this
    step's full action JSON: (1) the acting agent — a before-action first-person
    `thought` and a one-sentence imperative `action_abstract` (EvoCUA-style
    Thought + Action); (2) the renderer — the after-action `voyager_prompt` that
    is the SOLE source of the render description. The planner no longer writes a
    scene_prompt, only a one-line `description` passed through as advisory context.

    Retries up to max_attempts for a NON-EMPTY voyager_prompt. If every attempt
    fails (network error, unparseable JSON, or empty voyager_prompt) it RAISES —
    we NEVER fall back to a low-quality prompt, because per-frame image quality is
    the priority. The caller truncates on this raise, keeping the valid prefix.
    """
    last_err = None
    for attempt in range(max_attempts):
        try:
            raw = call_llm_vision(VOYAGER_SYS,
                                  voyager_user_prompt(action_step, prompt_prefix,
                                                      high_level_plan=high_level_plan,
                                                      step_index=step_index,
                                                      total_steps=total_steps,
                                                      steps_done=steps_done),
                                  [('current_frame', prev_obs_path)])
            m = re.search(r'\{.*\}', raw, re.S)
            if m:
                j = json.loads(m.group())
                fields = ('voyager_prompt', 'thought', 'action_abstract')
                if isinstance(j, dict) and all(isinstance(j.get(k), str) and j[k].strip() for k in fields):
                    return {k: j[k].strip() for k in fields}
            last_err = 'empty or invalid Voyager response'
        except BackendConfigurationError:
            raise
        except Exception as e:
            last_err = type(e).__name__
        print(f'  ⚠️  voyager 帧生成失败 (attempt {attempt + 1}/{max_attempts}): {last_err}')
    raise RuntimeError(f'voyager frame generation failed after {max_attempts} attempts: {last_err}')


def expand_seed(seed_id: str, task_description: str, quality: str = 'high',
                dedup_threshold: float = 0.85, skip_dedup: bool = False,
                act_render: str = 'pil', grounder: str | None = None,
                meta_extra: dict | None = None, infeasible: bool = False,
                judge_timing: str | None = None, infeasible_reason: str | None = None,
                explore_hint: str | None = None) -> str | None:
    """Generate one trajectory from a seed. Returns trajectory_id or None if rejected.

    act_render selects how pointing-action act frames are drawn: 'pil' (default,
    pixel-identical red-box overlay) or 'image2' (image-edit repaint). grounder
    selects the coordinate backend ('locate_anything' | 'mai_ui' | 'gpt55'); None
    uses the global DEFAULT_GROUNDER (locate_anything). Box coordinates always come
    from the chosen grounder regardless of act_render.

    meta_extra: optional run metadata stored with the generated trajectory.
    """
    if not isinstance(task_description, str) or not task_description.strip():
        raise ValueError('Task must be nonempty text')
    if not 0 <= dedup_threshold <= 1:
        raise ValueError('Dedup threshold must be between 0 and 1')
    if act_render not in ('pil', 'image2') or (grounder or DEFAULT_GROUNDER) not in GROUNDERS:
        raise ValueError('Unknown annotation renderer or grounding backend')
    seed = load_seed(seed_id)
    os_key = seed['os_key']
    os_config = OS_REGISTRY[os_key]
    image_size = seed['image_size']
    style_directive = seed['style_directive']
    env_state_text = seed['env_state_text']
    blockers = seed.get('blockers', [])
    seed_global_state = seed['global_state']
    if grounder is None:
        grounder = DEFAULT_GROUNDER

    # Task dedup
    if not skip_dedup:
        registry = TaskRegistry(task_registry_path(os_key))
        is_dup, similar, sim = registry.check_duplicate(task_description, dedup_threshold)
        if is_dup:
            print(f'\n⚠️  任务过于相似，跳过。')
            print(f'   New: {task_description}')
            print(f'   Existing: {similar}  (sim={sim:.3f})')
            return None

    # Action space
    action_space_key = os_config['action_space']
    action_space = ACTION_SPACES[action_space_key]['actions']

    # Build trajectory planner prompt
    sys_prompt = build_trajectory_planner_prompt(
        os_config, style_directive, env_state_text,
        seed_global_state['prompt'], blockers, action_space,
        infeasible=infeasible, judge_timing=judge_timing,
        infeasible_reason=infeasible_reason, explore_hint=explore_hint,
    )

    print(f'\n{"="*60}')
    print(f' Expanding {seed_id} → trajectory')
    print(f' Task: {task_description}')
    print(f' OS: {os_config["name"]}, image: {image_size}, grounder: {grounder}')
    print(f'{"="*60}')

    print('\n🧠 LLM 规划 action 序列...')
    # Replace task account fields with stable placeholders during planning.
    masked_task, cred_map = mask_credentials(task_description)
    # The planner occasionally emits malformed JSON (its own formatting slip).
    # Retry once with a fresh call — a re-generation usually returns valid JSON.
    plan = None
    last_err = None
    for attempt in range(2):
        raw = call_llm(sys_prompt, masked_task)
        try:
            plan = unmask_credentials(json.loads(strip_json_fence(raw)), cred_map)
            break
        except Exception:
            last_err = ValueError("Planner returned invalid JSON")
            print(f'Planner returned invalid JSON (attempt {attempt + 1})')
    if plan is None:
        raise last_err
    plan = validate_plan(plan, os_key)
    actions = plan['actions']
    if not actions:
        print(f'❌ 未生成 action')
        return None
    high_level_plan = plan.get('high_level_plan')
    print(f'✅ 生成 {len(actions)} 个 actions')

    # Init trajectory dir, copy initial.png as obs_00.png
    traj_id = reserve_trajectory_id(os_key)
    _meta = dict(meta_extra or {})
    _meta.pop('plan_raw', None)
    _meta['agent_plan'] = plan
    td = init_trajectory(traj_id, seed_id, task_description, meta_extra=_meta)

    # Generate the obs chain (clean observations) + act frames (box overlays).
    print('\n🎯 串行生成 obs / act 帧...')
    step_results = []
    prev_obs = os.path.join(td, 'obs_00.png')   # obs_0 = seed initial
    for action_step in actions:
        k = action_step['step']
        act = action_step.get('action') or {}
        act_name = act.get('action') if isinstance(act, dict) else act

        rec = {
            'step': k,
            'phase': action_step.get('phase', 'main'),
            'action': act,
            'description': action_step.get('description'),
            'target_element': action_step.get('target_element'),
        }

        # 1) act frame: draw red box(es) on the BEFORE observation (prev_obs).
        descs = element_descs(action_step)
        rec['n_boxes'] = len(descs)

        if descs:
            act_path = os.path.join(td, f'act_{k:02d}.png')
            try:
                boxes = annotate_act_frame(prev_obs, act_path, descs, grounder=grounder,
                                           render=act_render, image_size=image_size, quality=quality)
                rec['act_frame'] = os.path.basename(act_path)
                rec['boxes'] = boxes
                if len(boxes) != len(descs):
                    raise ValueError('Grounding did not locate every required target')
                print(f'  ✅ act_{k:02d} 生成 ({len(boxes)}/{len(descs)} box 定位)')
            except Exception as e:
                rec.update(status='error', obs_frame=None, msg=f'grounding: {type(e).__name__}')
                step_results.append(rec)
                print(f'  Grounding failed at step {k}; trajectory truncated')
                break
        else:
            # non-pointing action: its act frame is just the before-observation
            rec['act_frame'] = os.path.basename(prev_obs)

        # 2) next clean observation obs_k (action-after).
        # answer reuses the previous frame and ends the trajectory without a
        # Voyager call or another rendered frame. Every other action uses
        # the REAL prev_obs + this action's literal text to write the voyager
        # prompt (so typed text / terminal output renders as real characters), the
        # before-action thought and one-line action_abstract, then edit the frame.
        if act_name == 'answer':
            rec['obs_frame'] = os.path.basename(prev_obs)
            rec['status'] = 'success'
            step_results.append(rec)
            print(f'  ✅ answer step{k} — reused final observation; trajectory ended')
            break

        # The obs chain is strictly serial: obs_k is edited FROM prev_obs. If any
        # step's frame fails to render, prev_obs cannot advance — continuing would
        # draw every later frame from a stale reference, silently producing frames
        # whose pixels no longer match their action. So on any failure we TRUNCATE:
        # keep the successful prefix, drop the rest, never emit misaligned frames.
        def _truncate(msg):
            rec['obs_frame'] = None
            rec['status'] = 'error'
            rec['msg'] = msg
            step_results.append(rec)
            print(f'  ❌ obs_{k:02d} 失败: {msg} — 截断轨迹(保留前 {len(step_results) - 1} 步)')

        try:
            steps_done = [r['action_abstract'] for r in step_results
                          if r.get('action_abstract')]
            vf = gen_voyager_frame(
                prev_obs, action_step, os_config['prompt_prefix'],
                high_level_plan=high_level_plan,
                step_index=k, total_steps=len(actions), steps_done=steps_done)
        except Exception as e:
            # Voyager exhausted its retries — do NOT render from a low-quality
            # prompt; truncate to preserve per-frame quality.
            _truncate(f'voyager: {e}')
            break
        voyager_prompt = vf['voyager_prompt']
        rec['voyager_prompt'] = voyager_prompt
        rec['thought'] = vf['thought']            # EvoCUA-style before-action reasoning
        rec['action_abstract'] = vf['action_abstract']  # one-line imperative summary
        if action_step.get('must_not_render'):
            rec['must_not_render'] = action_step['must_not_render']
        obs_path = os.path.join(td, f'obs_{k:02d}.png')
        try:
            edit_with_ref(render_edit_prompt(voyager_prompt), prev_obs, obs_path,
                          image_size, quality)
        except Exception as e:
            _truncate(str(e))
            break
        rec['obs_frame'] = os.path.basename(obs_path)
        rec['status'] = 'success'
        prev_obs = obs_path
        print(f'  ✅ obs_{k:02d} 生成 | {vf["action_abstract"][:50]}')

        step_results.append(rec)

    # Finalize
    finalize_trajectory(traj_id, plan, step_results)

    # Register task to dedup
    complete = trajectory_complete({'agent_plan': plan, 'steps': step_results})
    if not skip_dedup and complete:
        TaskRegistry(task_registry_path(os_key)).add_task(task_description)

    ok = sum(1 for r in step_results if r['status'] == 'success')
    print(f'\n{"="*60}')
    print(f' Trajectory {traj_id}: {"complete" if complete else "partial"}')
    print(f'    Steps: {ok}/{len(effective_actions(plan))} → {td}')
    print(f'{"="*60}')

    cost_logger = get_cost_logger()
    cost_logger.flush()
    cost_logger.print_summary()

    return traj_id

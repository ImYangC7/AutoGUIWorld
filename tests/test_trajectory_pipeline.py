# -*- coding: utf-8 -*-
"""Offline Planner/Voyager regressions with real temporary trajectory files.

The planner, vision, grounding and image-edit boundaries are mocked. Prompt
builders, Voyager parsing/retries, the trajectory loop and storage run normally.
No credentials, model downloads or live services are needed.
"""

import copy
import io
import json
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

from autogui.pipeline import trajectory
from autogui.storage import manager as storage


def _voyager_response(step=1):
    return json.dumps({
        'voyager_prompt': f'Rendered result of action {step}.',
        'thought': f'The current screen supports action {step}.',
        'action_abstract': f'Perform action {step}.',
    })


def _payload(vision_call):
    """Read the JSON payload without depending on the surrounding prompt prose."""
    text = vision_call.args[1]
    return json.JSONDecoder().raw_decode(text[text.index('{'):])[0]


class TrajectoryPipelineTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(redirect_stdout(io.StringIO()))

        self.http = self.stack.enter_context(mock.patch(
            'requests.sessions.Session.request',
            side_effect=AssertionError('Network access is forbidden in this test'),
        ))
        self.connect = self.stack.enter_context(mock.patch(
            'socket.socket.connect',
            side_effect=AssertionError('Socket access is forbidden in this test'),
        ))
        self.stack.enter_context(mock.patch.multiple(
            storage,
            SEEDS_DIR=str(self.root / 'seeds'),
            TRAJ_DIR=str(self.root / 'trajectories'),
            TASK_REG_DIR=str(self.root / 'task_registries'),
            SEED_INDEX_PATH=str(self.root / 'seeds' / '_index.json'),
            TRAJ_INDEX_PATH=str(self.root / 'trajectories' / '_index.json'),
        ))
        self.registry = self.stack.enter_context(mock.patch.object(
            trajectory, 'TaskRegistry',
            side_effect=AssertionError('These fixtures bypass task dedup/model loading'),
        ))
        self.cost = mock.Mock()
        self.stack.enter_context(mock.patch.object(
            trajectory, 'get_cost_logger', return_value=self.cost,
        ))

        self.events = []
        self.plan = {
            'high_level_plan': 'Enter a query, then submit the form.',
            'actions': [
                {'step': 1, 'description': 'Focus the search field.',
                 'target_element': 'Search field',
                 'action': {'action': 'click', 'element': 'Search field'}},
                {'step': 2, 'description': 'Enter the query.',
                 'action': {'action': 'type_text', 'text': 'sample query'}},
                {'step': 3, 'description': 'Submit the form.',
                 'target_element': 'Submit button',
                 'action': {'action': 'click', 'element': 'Submit button'}},
                {'step': 4, 'description': 'Report completion.',
                 'action': {'action': 'answer', 'status': 'DONE', 'text': 'Done.'}},
            ],
        }
        self.planner = self.stack.enter_context(mock.patch.object(
            trajectory, 'call_llm', side_effect=self._plan,
        ))
        self.vision = self.stack.enter_context(mock.patch.object(
            trajectory, 'call_llm_vision', side_effect=self._vision,
        ))
        self.ground = self.stack.enter_context(mock.patch.object(
            trajectory, 'annotate_act_frame', side_effect=self._annotate,
        ))
        self.edit = self.stack.enter_context(mock.patch.object(
            trajectory, 'edit_with_ref', side_effect=self._edit,
        ))

        self.seed_id = 'seed_001'
        self.task = 'Enter the sample query and submit the form.'
        self.seed = {
            'os_key': 'chrome_browser',
            'image_size': '32x24',
            'aesthetic': {},
            'style_directive': 'Use the fixture visual style.',
            'env_state': {},
            'env_state_text': 'A form with a Search field and Submit button.',
            'blockers': [],
            'global_state': {'prompt': 'The fixture initial screenshot description.'},
        }
        png = io.BytesIO()
        Image.new('RGB', (32, 24), (240, 240, 240)).save(png, format='PNG')
        self.seed_dir = Path(storage.save_seed(self.seed_id, self.seed, png.getvalue()))

    def tearDown(self):
        # A swallowed network exception must fail the test, too.
        self.http.assert_not_called()
        self.connect.assert_not_called()
        self.registry.assert_not_called()

    def _plan(self, system_prompt, user_prompt):
        self.events.append('planner')
        return json.dumps(self.plan)

    def _vision(self, system_prompt, user_prompt, images):
        self.events.append('voyager')
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0][0], 'current_frame')
        with Image.open(images[0][1]) as im:
            self.assertEqual(im.size, (32, 24))
            self.assertNotEqual(im.getpixel((2, 2)), (255, 0, 0))
        payload = json.JSONDecoder().raw_decode(user_prompt[user_prompt.index('{'):])[0]
        return _voyager_response(payload['progress']['current_step'])

    def _annotate(self, before, output, descriptions, **kwargs):
        self.events.append('ground')
        metadata = json.loads((Path(before).parent / 'meta.json').read_text())
        self.assertEqual(metadata['agent_plan'], self.plan)
        self.assertNotIn('plan_raw', metadata)
        with Image.open(before) as im:
            annotated = im.convert('RGB')
        ImageDraw.Draw(annotated).rectangle([2, 2, 8, 8], outline=(255, 0, 0))
        annotated.save(output)
        return [
            {'element': desc, 'source': 'fixture', 'point_px': [5, 5],
             'bbox_px': [2, 2, 8, 8], 'bbox_norm': [2 / 32, 2 / 24, 8 / 32, 8 / 24]}
            for desc in descriptions
        ]

    def _edit(self, prompt, before, output, size, quality):
        self.events.append('edit')
        with Image.open(before) as im:
            after = im.convert('RGB')
        self.assertNotEqual(after.getpixel((2, 2)), (255, 0, 0))
        step = int(Path(output).stem.split('_')[1])
        after.putpixel((0, 0), (step, 0, 0))
        after.save(output)
        return output

    def _expand(self, **kwargs):
        tid = trajectory.expand_seed(
            self.seed_id, self.task, skip_dedup=True,
            quality='low', grounder='locate_anything', **kwargs,
        )
        self.assertIsNotNone(tid)
        directory = Path(storage.trajectory_dir(tid))
        return directory, json.loads((directory / 'meta.json').read_text(encoding='utf-8'))

    def _assert_truncated(self, directory, meta):
        self.assertEqual([s['step'] for s in meta['steps']], [1, 2])
        first, failed = meta['steps']
        self.assertEqual(first['status'], 'success')
        self.assertEqual(first['obs_frame'], 'obs_01.png')
        self.assertEqual(failed['status'], 'error')
        self.assertIsNone(failed['obs_frame'])
        self.assertTrue((directory / 'obs_01.png').is_file())
        for name in ('obs_02.png', 'act_03.png', 'obs_03.png', 'obs_04.png'):
            self.assertFalse((directory / name).exists(), name)
        self.assertEqual(meta['agent_plan'], self.plan)
        self.assertNotIn('plan_raw', meta)
        self.planner.assert_called_once()
        self.cost.flush.assert_called_once_with()

    def test_planner_voyager_chain_uses_clean_previous_images(self):
        directory, meta = self._expand(meta_extra={'source': 'offline-fixture'})

        self.planner.assert_called_once()
        system_prompt, user_prompt = self.planner.call_args.args
        self.assertEqual(user_prompt, self.task)
        self.assertIn(self.seed['env_state_text'], system_prompt)
        self.assertIn(self.seed['global_state']['prompt'], system_prompt)
        self.assertEqual(self.events, [
            'planner', 'ground', 'voyager', 'edit', 'voyager', 'edit',
            'ground', 'voyager', 'edit',
        ])
        self.assertNotIn('plan_raw', meta)
        self.assertEqual(meta['agent_plan'], self.plan)
        self.assertEqual(meta['source'], 'offline-fixture')
        self.assertEqual([s['action'] for s in meta['steps']],
                         [s['action'] for s in self.plan['actions']])

        for k, (vision_call, edit_call) in enumerate(zip(
                self.vision.call_args_list, self.edit.call_args_list), 1):
            before = str(directory / f'obs_{k - 1:02d}.png')
            self.assertEqual(vision_call.args[2], [('current_frame', before)])
            self.assertEqual(edit_call.args[1:], (
                before, str(directory / f'obs_{k:02d}.png'), '32x24', 'low',
            ))
            self.assertIn(f'Rendered result of action {k}.', edit_call.args[0])
            self.assertNotIn(self.plan['actions'][k - 1]['description'], edit_call.args[0])
            payload = _payload(vision_call)
            self.assertEqual(payload['action'], self.plan['actions'][k - 1]['action'])
            self.assertEqual(payload['high_level_plan'], self.plan['high_level_plan'])
            self.assertEqual(payload['progress'], {
                'current_step': k, 'total_steps': 4,
                'steps_done_so_far': [f'Perform action {i}.' for i in range(1, k)],
            })
            self.assertEqual(meta['steps'][k - 1]['thought'],
                             f'The current screen supports action {k}.')
            self.assertEqual(meta['steps'][k - 1]['action_abstract'], f'Perform action {k}.')

        self.assertEqual(self.vision.call_count, 3)
        self.assertEqual(self.edit.call_count, 3)
        self.assertEqual([Path(c.args[0]).name for c in self.ground.call_args_list],
                         ['obs_00.png', 'obs_02.png'])
        self.assertEqual([c.args[2] for c in self.ground.call_args_list],
                         [['Search field'], ['Submit button']])
        self.assertEqual([s['act_frame'] for s in meta['steps']],
                         ['act_01.png', 'obs_01.png', 'act_03.png', 'obs_03.png'])
        self.assertEqual(meta['steps'][-1]['obs_frame'], 'obs_03.png')
        self.assertFalse((directory / 'obs_04.png').exists())
        self.assertEqual((directory / 'obs_00.png').read_bytes(),
                         (self.seed_dir / 'initial.png').read_bytes())
        with Image.open(directory / 'act_01.png') as im:
            self.assertEqual(im.getpixel((2, 2)), (255, 0, 0))
        self.cost.flush.assert_called_once_with()

    def test_answer_only_reuses_initial_image_without_voyager_or_render(self):
        for status in ('DONE', 'FAIL'):
            with self.subTest(status=status):
                self.plan['actions'] = [{
                    'step': 1, 'action': {'action': 'answer', 'status': status, 'text': 'Result.'},
                }]
                directory, meta = self._expand()
                self.assertEqual(len(meta['steps']), 1)
                step = meta['steps'][0]
                self.assertEqual(step['action']['status'], status)
                self.assertEqual(step['obs_frame'], 'obs_00.png')
                self.assertEqual(step['act_frame'], 'obs_00.png')
                self.assertNotIn('appended', step)
                self.assertEqual(sorted(p.name for p in directory.glob('*.png')), ['obs_00.png'])
        self.vision.assert_not_called()
        self.ground.assert_not_called()
        self.edit.assert_not_called()

    def test_voyager_failure_keeps_prefix_and_stops_later_actions(self):
        self.vision.side_effect = [
            _voyager_response(1), RuntimeError('fixture vision failure'),
            'invalid JSON', json.dumps({'voyager_prompt': '   '}),
        ]
        directory, meta = self._expand()
        self._assert_truncated(directory, meta)
        self.assertIn('voyager', meta['steps'][1]['msg'])
        self.assertEqual(self.vision.call_count, 4)
        self.edit.assert_called_once()
        self.ground.assert_called_once()
        retries = self.vision.call_args_list[1:]
        self.assertTrue(all(c == retries[0] for c in retries))
        self.assertEqual(retries[0].args[2], [('current_frame', str(directory / 'obs_01.png'))])
        self.assertEqual(_payload(retries[0])['progress']['steps_done_so_far'],
                         ['Perform action 1.'])

    def test_image_edit_failure_keeps_prefix_and_stops_later_actions(self):
        def fail_second_edit(prompt, before, output, size, quality):
            if Path(output).name == 'obs_02.png':
                raise RuntimeError('fixture edit failure')
            return self._edit(prompt, before, output, size, quality)

        self.edit.side_effect = fail_second_edit
        directory, meta = self._expand()
        self._assert_truncated(directory, meta)
        self.assertIn('fixture edit failure', meta['steps'][1]['msg'])
        self.assertEqual(self.vision.call_count, 2)
        self.assertEqual(self.edit.call_count, 2)
        self.ground.assert_called_once()

    def test_full_action_parameters_and_context_reach_voyager(self):
        actions = [
            {'action': 'type_text', 'text': 'A "quoted" query\n第二行'},
            {'action': 'key_press', 'key': 'Tab'},
            {'action': 'hotkey', 'keys': ['CTRL', 'SHIFT', 'S']},
            {'action': 'hotkey', 'value': 'CTRL+S'},
            {'action': 'scroll', 'value': 'up', 'amount': 240},
            {'action': 'drag', 'from_element': 'Card A', 'to_element': 'Column B',
             'duration': 0.5, 'extra': {'held_keys': ['SHIFT']}},
        ]
        for action in actions:
            with self.subTest(action=action):
                step = {
                    'step': 3, 'action': action, 'description': 'Fixture planner intent.',
                    'target_element': 'Fixture target', 'from_element': 'Source hint',
                    'to_element': 'Destination hint',
                    'must_not_render': 'Do not show an unavailable option.',
                }
                original = copy.deepcopy(step)
                result = trajectory.gen_voyager_frame(
                    str(self.seed_dir / 'initial.png'), step, 'Fixture prefix',
                    high_level_plan='Fixture strategy', step_index=3, total_steps=8,
                    steps_done=['First completed action.', 'Second completed action.'],
                )
                payload = _payload(self.vision.call_args)
                self.assertEqual(payload['action'], action)
                for key in ('target_element', 'from_element', 'to_element', 'must_not_render'):
                    self.assertEqual(payload[key], step[key])
                self.assertEqual(payload['planner_description'], step['description'])
                self.assertEqual(payload['high_level_plan'], 'Fixture strategy')
                self.assertEqual(payload['progress'], {
                    'current_step': 3, 'total_steps': 8,
                    'steps_done_so_far': ['First completed action.', 'Second completed action.'],
                })
                self.assertIn('Fixture prefix', self.vision.call_args.args[1])
                self.assertEqual(result, json.loads(_voyager_response(3)))
                self.assertEqual(step, original)
        self.assertEqual(self.vision.call_count, len(actions))
        self.planner.assert_not_called()
        self.edit.assert_not_called()

    def test_infeasible_exploration_and_negative_constraint_are_preserved(self):
        self.plan['actions'] = [copy.deepcopy(self.plan['actions'][0]), {
            'step': 2, 'action': {'action': 'answer', 'status': 'FAIL', 'text': 'Unavailable.'},
        }]
        constraint = 'Do not show Blue; the available themes are Light and Dark.'
        self.plan['actions'][0]['must_not_render'] = constraint
        directory, meta = self._expand(
            infeasible=True, judge_timing='explore',
            infeasible_reason='The requested theme is unavailable.',
            explore_hint='Inspect the appearance settings.',
        )
        prompt = self.planner.call_args.args[0]
        self.assertIn('The requested theme is unavailable.', prompt)
        self.assertIn('Inspect the appearance settings.', prompt)
        self.assertEqual(_payload(self.vision.call_args)['must_not_render'], constraint)
        self.assertEqual(meta['steps'][0]['must_not_render'], constraint)
        self.assertEqual(meta['steps'][1]['action']['status'], 'FAIL')
        self.assertEqual(meta['steps'][1]['obs_frame'], 'obs_01.png')
        self.assertFalse((directory / 'obs_02.png').exists())
        self.vision.assert_called_once()
        self.edit.assert_called_once()

    def test_voyager_retries_then_returns_trimmed_fields(self):
        self.vision.side_effect = [RuntimeError('fixture transient failure'), 'not JSON',
                                  json.dumps({'voyager_prompt': ' next frame ',
                                              'thought': ' before action ',
                                              'action_abstract': ' click target '})]
        result = trajectory.gen_voyager_frame(
            str(self.seed_dir / 'initial.png'), self.plan['actions'][0], 'Fixture prefix',
        )
        self.assertEqual(result, {'voyager_prompt': 'next frame', 'thought': 'before action',
                                  'action_abstract': 'click target'})
        self.assertEqual(self.vision.call_count, 3)
        self.assertTrue(all(c == self.vision.call_args_list[0]
                            for c in self.vision.call_args_list))
        self.edit.assert_not_called()

    def test_voyager_exhausts_invalid_responses_without_planner_fallback(self):
        for raw in ('not JSON', '{}', '{"voyager_prompt": "   "}', '{"voyager_prompt": null}'):
            with self.subTest(response=raw):
                self.vision.reset_mock()
                self.vision.side_effect = None
                self.vision.return_value = raw
                with self.assertRaisesRegex(RuntimeError, 'after 3 attempts'):
                    trajectory.gen_voyager_frame(
                        str(self.seed_dir / 'initial.png'), self.plan['actions'][0], 'Fixture prefix',
                    )
                self.assertEqual(self.vision.call_count, 3)
        self.planner.assert_not_called()
        self.edit.assert_not_called()

    def test_terminal_action_stops_even_with_trailing_plan_actions(self):
        terminal = copy.deepcopy(self.plan['actions'][-1])
        terminal['step'] = 1
        trailing = copy.deepcopy(self.plan['actions'][0])
        trailing['step'] = 2
        self.plan['actions'] = [terminal, trailing]
        directory, meta = self._expand()
        self.assertEqual(len(meta['steps']), 1)
        self.assertEqual(meta['steps'][0]['obs_frame'], 'obs_00.png')
        self.vision.assert_not_called()
        self.edit.assert_not_called()

    def test_invalid_plan_is_rejected_before_allocating_output(self):
        for actions in ([{'step': 9, 'action': {'action': 'click'}}],
                        [{'step': 1, 'action': {'action': 'unknown_action'}}],
                        ['invalid']):
            self.plan['actions'] = actions
            with self.subTest(actions=actions), mock.patch.object(trajectory, 'reserve_trajectory_id') as reserve:
                with self.assertRaises(ValueError):
                    self._expand()
                reserve.assert_not_called()

    def test_grounding_failure_stops_before_voyager_and_marks_partial(self):
        self.ground.side_effect = None
        self.ground.return_value = []
        directory, meta = self._expand()
        self.assertEqual(meta['status'], 'partial')
        self.assertEqual(meta['steps'][0]['status'], 'error')
        self.vision.assert_not_called()
        self.edit.assert_not_called()

    def test_account_text_is_restored_after_json_parsing(self):
        self.task = 'Use password `a"b\\c` in the visible form'
        self.planner.side_effect = None
        self.planner.return_value = json.dumps({'actions': [
            {'step': 1, 'action': {'action': 'type_text', 'text': '<CRED_1>'}},
            {'step': 2, 'action': {'action': 'answer', 'status': 'DONE', 'text': 'Done'}},
        ]})
        directory, meta = self._expand()
        self.assertEqual(meta['steps'][0]['action']['text'], 'a"b\\c')
        self.assertEqual(meta['status'], 'complete')


    def test_empty_plan_does_not_allocate_a_trajectory(self):
        self.plan['actions'] = []
        self.assertIsNone(trajectory.expand_seed(self.seed_id, self.task, skip_dedup=True))
        self.assertFalse((self.root / 'trajectories').exists())
        self.planner.assert_called_once()
        self.vision.assert_not_called()
        self.ground.assert_not_called()
        self.edit.assert_not_called()
        self.cost.flush.assert_not_called()


if __name__ == '__main__':
    unittest.main()

"""Run the complete seed-driven CLI flow with local model and grounding fixtures."""
import base64
import copy
import io
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image, ImageDraw

import cli
from autogui.analysis import qc_seeds, qc_task_seed
from autogui.clients import backend, image, llm
from autogui.pipeline import trajectory
from autogui.pipeline import seed as seed_pipeline
from autogui.state.registry import OS_REGISTRY
from autogui.storage import manager as storage
from autogui.tasks import dedup, generator
from autogui.utils.cost import CostLogger
from scripts.maintain.check_integrity import check_integrity


class SeedFlowTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.network = self.stack.enter_context(mock.patch(
            'socket.socket.connect', side_effect=AssertionError('External network call')))
        self.stack.enter_context(mock.patch.multiple(
            storage, SEEDS_DIR=str(self.directory/'seeds'),
            TRAJ_DIR=str(self.directory/'trajectories'),
            TASK_REG_DIR=str(self.directory/'task_registries'),
            SEED_INDEX_PATH=str(self.directory/'seeds/_index.json'),
            TRAJ_INDEX_PATH=str(self.directory/'trajectories/_index.json'),
        ))
        self.stack.enter_context(mock.patch.object(qc_task_seed, 'TRAJ_DIR', storage.TRAJ_DIR))
        small_registry = copy.deepcopy(OS_REGISTRY)
        for entry in small_registry.values():
            entry['image_size'] = '64x64'
        self.stack.enter_context(mock.patch.dict(OS_REGISTRY, small_registry))
        embedder = mock.Mock()
        embedder.encode.side_effect = lambda text: np.array([1.0, 0.0, 0.0])
        self.stack.enter_context(mock.patch.object(dedup, '_load_model', return_value=embedder))
        self.adapter = types.ModuleType('seed_flow_fixture')
        self.adapter.chat = self._chat
        self.adapter.image = self._image
        self.stack.enter_context(mock.patch.dict(sys.modules, {self.adapter.__name__: self.adapter}))
        self.stack.enter_context(mock.patch.dict(os.environ, {'AUTOGUI_BACKEND': self.adapter.__name__}))
        backend._load.cache_clear()
        self.addCleanup(backend._load.cache_clear)
        self.cost = CostLogger(self.directory/'usage.json')
        self.stack.enter_context(mock.patch.object(seed_pipeline, 'get_logger', return_value=self.cost))
        for module in (llm, image, trajectory):
            self.stack.enter_context(mock.patch.object(module, 'get_cost_logger', return_value=self.cost))
        for module in (llm, image):
            self.stack.enter_context(mock.patch.object(module._RATE_GATE, 'wait'))
        self.stack.enter_context(mock.patch.object(trajectory, 'annotate_act_frame', side_effect=self._ground))
        self.events = []

    def tearDown(self):
        self.network.assert_not_called()

    def _chat(self, *, messages, purpose, max_tokens):
        system = messages[0]['content']
        if purpose == 'qc':
            self.events.append('qc')
            return {'text': json.dumps({'defects': [], 'summary': 'clear', 'verdict': 'match',
                                       'app_ok': True, 'content_present': True})}
        if purpose == 'llm_vision':
            self.events.append('voyager')
            data = next(part['image_url']['url'] for part in messages[1]['content']
                        if part['type'] == 'image_url')
            with Image.open(io.BytesIO(base64.b64decode(data.split(',', 1)[1]))) as frame:
                self.assertNotEqual(frame.getpixel((2, 2)), (255, 0, 0))
            return {'text': json.dumps({'thought': 'Use the visible fixture control.',
                                       'action_abstract': 'Complete the next edit.',
                                       'voyager_prompt': 'Show the next state of the fixture form.'})}
        if system.startswith('You are a GUI initial-state describer.'):
            self.events.append('describe_seed')
            return {'text': json.dumps({'global_state': {
                'prompt': 'A sampled fixture application with a control and text field.',
                'visible_elements': ['Fixture control', 'Fixture field'],
                'target_window': 'Fixture App',
            }})}
        if system == generator.TASK_GEN_SYSTEM_PROMPT:
            self.events.append('generate_task')
            self.assertTrue(storage.list_seeds())
            self.assertIn('Fixture control', messages[1]['content'])
            self.assertIn('Fixture field', messages[1]['content'])
            return {'text': json.dumps({'task': 'Select the fixture control and enter a note.',
                                       'app': 'Fixture App', 'category': 'editing',
                                       'complexity': 'simple', 'feasible': True})}
        self.assertTrue(system.startswith('You are a GUI agent action planner.'))
        self.events.append('plan')
        self.assertIn('sampled fixture application', system)
        action = 'tap' if OS_REGISTRY[self.platform]['category'] == 'mobile' else 'click'
        return {'text': json.dumps({'high_level_plan': 'Focus the field and write a note.', 'actions': [
            {'step': 1, 'description': 'Select the control.', 'target_element': 'Fixture control',
             'action': {'action': action, 'element': 'Fixture control'}},
            {'step': 2, 'description': 'Write a note.', 'action': {'action': 'type_text', 'text': 'note'}},
            {'step': 3, 'description': 'Finish.', 'action': {'action': 'answer', 'status': 'DONE', 'text': 'Done.'}},
        ]})}

    def _image(self, *, prompt, operation, image_bytes, size, quality):
        self.events.append('render_seed' if operation == 'generate' else 'edit')
        if image_bytes is None:
            frame = Image.new('RGB', (64, 64), 'white')
        else:
            with Image.open(io.BytesIO(image_bytes)) as reference:
                frame = reference.convert('RGB')
            self.assertNotEqual(frame.getpixel((2, 2)), (255, 0, 0))
            frame.putpixel((0, 0), (0, 0, 0))
        output = io.BytesIO()
        frame.save(output, format='PNG')
        return {'image': output.getvalue()}

    def _ground(self, before, output, descriptions, **kwargs):
        self.events.append('ground')
        with Image.open(before) as frame:
            overlay = frame.convert('RGB')
        ImageDraw.Draw(overlay).rectangle([2, 2, 15, 15], outline=(255, 0, 0))
        overlay.save(output)
        return [{'element': name, 'source': 'fixture', 'bbox_px': [2, 2, 15, 15],
                 'bbox_norm': [2/64, 2/64, 15/64, 15/64], 'point_px': [8, 8]}
                for name in descriptions]

    def test_full_cli_flow_across_all_platforms(self):
        for self.platform in OS_REGISTRY:
            with self.subTest(platform=self.platform):
                self.events.clear()
                with mock.patch.object(sys, 'argv', ['cli.py', 'seed', '--os', self.platform, '--seed', '42']):
                    cli.main()
                sid, _ = storage.list_seeds(self.platform)[-1]
                initial = storage.load_seed(sid)
                self.assertEqual(self.events, ['describe_seed', 'render_seed'])
                self.assertEqual(initial['os_key'], self.platform)
                self.assertEqual(check_integrity(self.directory, [self.platform])['issues'], [])
                with mock.patch.object(sys, 'argv', ['cli.py', 'expand', '--seed-id', sid, '--auto-tasks', '1']):
                    cli.main()
                self.assertEqual(self.events, ['describe_seed', 'render_seed', 'generate_task', 'plan',
                                               'ground', 'voyager', 'edit', 'voyager', 'edit'])
                tid, _ = storage.list_trajectories(seed_id=sid)[-1]
                directory = Path(storage.trajectory_dir(tid))
                meta = json.loads((directory/'meta.json').read_text())
                self.assertEqual([step['status'] for step in meta['steps']], ['success'] * 3)
                self.assertEqual(meta['steps'][-1]['obs_frame'], 'obs_02.png')
                self.assertEqual(meta['steps'][0]['n_boxes'], 1)
                self.assertEqual(qc_seeds.grade_seed(directory/'obs_00.png', self.platform)['verdict'], 'pass')
                targets = qc_task_seed._collect_targets(self.platform, tid)
                self.assertEqual(len(targets), 1)
                self.assertEqual(targets[0][-1], 'Fixture App')
                self.assertEqual(qc_task_seed.judge(directory/'obs_00.png', meta['task_description'],
                                                   targets[0][-1])['verdict'], 'match')
                self.assertEqual(check_integrity(self.directory, [self.platform])['issues'], [])

    def test_task_generation_rejects_missing_or_wrong_platform_seed(self):
        for value in (None, {}, {'os_key': 'macos', 'global_state': {'prompt': 'scene'}}):
            with self.subTest(seed=value), self.assertRaises(ValueError):
                generator.generate_one_task('windows11', [], registry=dedup.TaskRegistry(None), seed=value)
        self.assertEqual(self.events, [])

    def test_clean_browser_constraints_and_mobile_inventory_are_realized(self):
        for platform in ('chrome_browser', 'android', 'ios'):
            self.platform = platform
            sid = seed_pipeline.create_seed(platform, seed_rng=42, skip_state=True,
                                             web_site='GitHub' if platform == 'chrome_browser' else None)
            seed = storage.load_seed(sid)
            if platform == 'chrome_browser':
                self.assertEqual(seed['env_state']['active_tab']['site'], 'GitHub')
            else:
                self.assertTrue(seed['env_state']['home_screen']['app_grid'])

    def test_seed_only_generation_flushes_usage(self):
        self.platform = 'windows11'
        seed_pipeline.create_seed(self.platform, seed_rng=42)
        usage = json.loads(self.cost.path.read_text())
        self.assertEqual(usage['summary']['total_calls'], 2)

    def test_duplicate_task_is_retried_with_same_seed_context(self):
        sample = {'os_key': 'windows11', 'global_state': {
            'prompt': 'A visible form.', 'visible_elements': ['Fixture control'],
        }}
        registry = mock.Mock()
        registry.check_duplicate.side_effect = [(True, 'existing task', 0.98), (False, None, 0)]
        responses = [json.dumps({'task': text, 'app': 'Fixture App', 'category': 'editing',
                                 'complexity': 'simple'}) for text in ['First proposed task', 'Revised proposed task']]
        with mock.patch.object(generator, 'call_llm', side_effect=responses) as call:
            result = generator.generate_one_task('windows11', [], registry=registry, seed=sample)
        self.assertEqual(result['task'], 'Revised proposed task')
        self.assertEqual(call.call_count, 2)
        self.assertTrue(all('Fixture control' in args.args[1] for args in call.call_args_list))


if __name__ == '__main__':
    unittest.main()

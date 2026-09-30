"""Failures must not masquerade as valid generated data or successful jobs."""
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

import batch_generate
from autogui.clients import grounding
from autogui.pipeline.step_utils import validate_plan
from autogui.tasks import dedup
from autogui.tasks.generator import validate_task_obj
from scripts.maintain import vlm_qc_trajectory as qc

ROOT = Path(__file__).resolve().parents[1]


def verdict():
    return {'grounding': {'box_hits_target': 'pass', 'box_tightness': 'pass', 'target_exists': 'pass'},
            'action': {'action_valid_here': 'pass', 'obs_transition_ok': 'pass'},
            'thinking': {'thinking_matches_screen': 'na', 'thinking_wavering': 'na'}}


class FailureContractTest(unittest.TestCase):
    def test_pointing_qc_requires_three_frames_and_reuses_valid_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for name in ('obs_00.png', 'act_01.png', 'obs_01.png'):
                Image.new('RGB', (20, 20), 'white').save(path/name)
            meta = {'task_description': 'Click Save', 'steps': [{
                'step': 1, 'status': 'success', 'action': {'action': 'click', 'element': 'Save'},
                'act_frame': 'act_01.png', 'obs_frame': 'obs_01.png',
                'boxes': [{'element': 'Save', 'bbox_px': [2, 2, 10, 10]}],
            }]}
            (path/'meta.json').write_text(json.dumps(meta))
            with mock.patch.object(qc, '_call_vlm', return_value=qc._normalize(verdict())) as call:
                self.assertEqual(qc._process_traj(directory, False)[:3], (1, 0, 0))
                self.assertEqual(len(call.call_args.args[2]), 3)
                self.assertEqual(qc._process_traj(directory, False)[:3], (0, 1, 0))
                call.assert_called_once()
                (path/'obs_01.png').unlink()
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(qc._process_traj(directory, False)[:3], (0, 0, 1))
                call.assert_called_once()

    def test_pointing_qc_cannot_use_na_to_pass_missing_evidence(self):
        result = qc._normalize(verdict())
        result['grounding']['box_hits_target'] = 'na'
        with self.assertRaises(ValueError):
            qc._check_applicability(result, 'click')
        result = qc._normalize(verdict())
        result['action']['obs_transition_ok'] = 'na'
        with self.assertRaises(ValueError):
            qc._check_applicability(result, 'type_text')

    def test_trajectory_qc_cli_and_report_cover_all_selected_platforms(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for os_key in ('windows11', 'macos'):
                td = root/os_key/'traj_001'
                td.mkdir(parents=True)
                Image.new('RGB', (20, 20), 'white').save(td/'obs_00.png')
                (td/'meta.json').write_text(json.dumps({'steps': [{'step': 1, 'status': 'success',
                    'action': {'action': 'answer'}, 'act_frame': 'obs_00.png', 'obs_frame': 'obs_00.png'}]}))
            with mock.patch.object(qc, 'TRAJ_ROOT', directory), mock.patch.object(qc, 'require_backend'), \
                 mock.patch.object(qc, '_call_vlm', return_value=qc._normalize(verdict())), redirect_stdout(io.StringIO()):
                for os_key in ('windows11', 'macos'):
                    with mock.patch.object(sys, 'argv', ['qc', '--os', os_key, '--rate', '0', '--workers', '1']):
                        self.assertEqual(qc.main(), 0)
                with mock.patch.object(sys, 'argv', ['qc', '--report', '--report-os', 'windows11', 'macos']):
                    qc.main()
            result = json.loads((root/'_vlm_qc_report.json').read_text())
            self.assertEqual(set(result['summary']), {'windows11', 'macos'})
            self.assertEqual(result['summary']['macos']['qc_done'], 1)

    def test_mai_ui_boundary_coordinates_are_inside_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'obs.png'
            Image.new('RGB', (20, 10), 'white').save(path)
            response = mock.Mock(status_code=200)
            response.json.return_value = {'choices': [{'message': {'content': '<answer>{"coordinate":[1000,1000]}</answer>'}}]}
            with mock.patch.object(grounding._HTTP, 'post', return_value=response), \
                 mock.patch.object(grounding, 'get_cost_logger'):
                self.assertEqual(grounding.ground_point(path, 'Target', 20, 10), [19, 9])

    def test_malformed_action_parameters_are_rejected(self):
        actions = [{'action': 'click'}, {'action': 'drag', 'from_element': 'Card'},
                   {'action': 'type_text', 'text': 42}, {'action': 'hotkey', 'keys': 'ctrl+s'},
                   {'action': 'answer', 'status': 'maybe', 'text': 'Done'},
                   {'action': 'scroll', 'value': 'sideways'}]
        for action in actions:
            with self.subTest(action=action), self.assertRaises(ValueError):
                validate_plan({'actions': [{'step': 1, 'action': action}]}, 'windows11')
        normalized = validate_plan({'actions': [{'step': 1, 'action': {'action': 'click'},
                                                 'target_element': 'Save'}]}, 'windows11')
        self.assertEqual(normalized['actions'][0]['action']['element'], 'Save')

    def test_feasibility_must_be_boolean(self):
        base = {'task': 'Open the visible form', 'app': 'Editor', 'category': 'editing', 'complexity': 'simple'}
        for value in ['false', 'true', 0, 1, None]:
            self.assertFalse(validate_task_obj(dict(base, feasible=value))[0])

    def test_grounding_rejects_nonfinite_empty_and_invalid_boxes(self):
        for box in [[float('nan'), 0, 10, 10], [0, 0, float('inf'), 3], [0, 0, 0, 10], ['1', 0, 10, 10], [True, 0, 10, 10]]:
            with self.subTest(box=box), self.assertRaises(ValueError):
                grounding._clamp_box(box, 100, 100)
        self.assertEqual(grounding._clamp_box([-3, -4, 120, 110], 100, 100), [0, 0, 99, 99])

    def test_local_grounder_skips_bad_payload_and_continues(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'obs.png'
            Image.new('RGB', (40, 30), 'white').save(path)
            bad, good = mock.Mock(status_code=200), mock.Mock(status_code=200)
            bad.json.return_value = {'boxes': [[float('nan'), 0, 5, 5]]}
            good.json.return_value = {'boxes': [[2, 3, 12, 13]]}
            with mock.patch.object(grounding._HTTP, 'post', side_effect=[bad, good]), redirect_stdout(io.StringIO()):
                boxes = grounding.ground_boxes(path, ['Bad target', 'Good target'], 'locate_anything')
            self.assertEqual(len(boxes), 1)
            self.assertEqual(boxes[0]['element'], 'Good target')

    def test_qc_missing_frames_cannot_be_scored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            Image.new('RGB', (20, 20), 'white').save(path / 'obs_00.png')
            meta = {'task_description': 'Click Save', 'steps': [{'step': 1, 'status': 'success',
                    'action': {'action': 'click', 'element': 'Save'}, 'obs_frame': None,
                    'act_frame': None, 'qc': dict(verdict(), overall='ok')}]}
            (path / 'meta.json').write_text(json.dumps(meta))
            with mock.patch.object(qc, '_call_vlm') as call, redirect_stdout(io.StringIO()):
                self.assertEqual(qc._process_traj(directory, False)[:3], (0, 0, 1))
            call.assert_not_called()
            self.assertIn('error', json.loads((path / 'meta.json').read_text())['steps'][0]['qc'])

    def test_qc_retries_error_cache_and_scopes_dimensions(self):
        raw = verdict()
        raw['grounding']['box_hits_target'] = 'fail'
        raw['thinking']['box_hits_target'] = 'pass'
        self.assertEqual(qc._normalize(raw)['overall'], 'major')
        raw = verdict()
        raw['action']['obs_transition_ok'] = 'fail'
        self.assertEqual(qc._normalize(raw)['overall'], 'major')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            Image.new('RGB', (20, 20), 'white').save(path / 'obs_00.png')
            meta = {'steps': [{'step': 1, 'status': 'success', 'action': {'action': 'answer'},
                              'act_frame': 'obs_00.png', 'obs_frame': 'obs_00.png', 'qc': {'error': 'earlier failure'}}]}
            (path / 'meta.json').write_text(json.dumps(meta))
            with mock.patch.object(qc, '_call_vlm', return_value=qc._normalize(verdict())) as call:
                self.assertEqual(qc._process_traj(directory, False)[:3], (1, 0, 0))
            call.assert_called_once()

    def test_batch_does_not_count_partial_trajectory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            action = {'action': 'type_text', 'text': 'note'}
            (path / 'meta.json').write_text(json.dumps({'agent_plan': {'actions': [{'step': 1, 'action': action}]},
                                                       'steps': [{'step': 1, 'action': action, 'status': 'error'}]}))
            with mock.patch.object(batch_generate, 'expand_seed', return_value='traj_001'), \
                 mock.patch.object(batch_generate, 'trajectory_dir', return_value=directory), redirect_stdout(io.StringIO()):
                self.assertIsNone(batch_generate.render_job('seed_001', 'Write note', 'low', 0.85))

    def test_cli_rejects_invalid_jobs_before_model_calls(self):
        cases = [['cli.py', 'expand', '--seed-id', 'seed_001', '--task', 'x', '--dedup-threshold', 'nan'],
                 ['cli.py', 'seed', '--os', 'windows11', '--batch', '0'],
                 ['batch_generate.py'], ['batch_generate.py', '--seeds-per-os', '2']]
        for args in cases:
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, *args], cwd=ROOT, env=dict(os.environ, AUTOGUI_BACKEND=''),
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn('Traceback', result.stderr)


class DedupConcurrencyTest(unittest.TestCase):
    def test_registry_updates_from_multiple_instances_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'registry.json'
            model = mock.Mock()
            model.encode.return_value = np.array([1.0, 0.0])
            registries = [dedup.TaskRegistry(path) for _ in range(20)]
            with mock.patch.object(dedup, '_load_model', return_value=model), ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda pair: pair[1].add_task(f'Task {pair[0]}'), enumerate(registries)))
            self.assertEqual(len(json.loads(path.read_text())['tasks']), 20)

    def test_embedding_model_is_loaded_once_across_threads(self):
        module = types.ModuleType('sentence_transformers')
        module.SentenceTransformer = mock.Mock(return_value=object())
        with mock.patch.dict(sys.modules, {'sentence_transformers': module}), mock.patch.object(dedup, '_MODEL', None), \
             ThreadPoolExecutor(max_workers=8) as pool:
            models = list(pool.map(lambda _: dedup._load_model(), range(24)))
        module.SentenceTransformer.assert_called_once()
        self.assertTrue(all(model is models[0] for model in models))

"""Batch entry point with real storage and local generation fixtures."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

from PIL import Image

import batch_generate
from autogui.clients.backend import BackendError
from autogui.storage import manager as storage
from scripts.maintain.check_integrity import check_integrity


class BatchPipelineTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.stack.enter_context(mock.patch('autogui.clients.backend.require_backend'))
        self.stack.enter_context(mock.patch.multiple(
            storage, SEEDS_DIR=str(self.root/'seeds'), TRAJ_DIR=str(self.root/'trajectories'),
            TASK_REG_DIR=str(self.root/'tasks'), SEED_INDEX_PATH=str(self.root/'seeds/_index.json'),
            TRAJ_INDEX_PATH=str(self.root/'trajectories/_index.json')))
        self.png = io.BytesIO()
        Image.new('RGB', (32, 24), 'white').save(self.png, format='PNG')
        self.stack.enter_context(mock.patch.object(batch_generate, 'create_seed', side_effect=self.create_seed))
        self.stack.enter_context(mock.patch.object(batch_generate, 'generate_tasks_for_seed', side_effect=lambda seed, n, **k: [
            {'task': f'Complete fixture {i}', 'feasible': True} for i in range(n)]))
        self.expand = self.stack.enter_context(mock.patch.object(batch_generate, 'expand_seed', side_effect=self.expand_seed))

    def create_seed(self, os_key, **kwargs):
        sid = storage.reserve_seed_id(os_key)
        storage.save_seed(sid, {'os_key': os_key, 'image_size': '32x24'}, self.png.getvalue())
        return sid

    def expand_seed(self, sid, task, **kwargs):
        seed = storage.load_seed(sid)
        tid = storage.reserve_trajectory_id(seed['os_key'])
        action = {'action': 'answer', 'status': 'DONE', 'text': 'Complete'}
        plan = {'actions': [{'step': 1, 'action': action}]}
        storage.init_trajectory(tid, sid, task, {'agent_plan': plan})
        storage.finalize_trajectory(tid, plan, [{'step': 1, 'action': action, 'status': 'success',
                                              'obs_frame': 'obs_00.png', 'act_frame': 'obs_00.png'}])
        return tid

    def run_batch(self, args):
        with mock.patch.object(sys, 'argv', ['batch_generate.py', *args]):
            return batch_generate.main()

    def test_parallel_seed_task_render_phases_preserve_indexes(self):
        result = self.run_batch(['--os', 'windows11', 'macos', '--seeds-per-os', '3', '--traj', '2', '--workers', '4'])
        self.assertEqual(result, 0)
        self.assertEqual(len(storage.list_seeds()), 6)
        self.assertEqual(len(storage.list_trajectories()), 12)
        self.assertEqual(check_integrity(self.root, ['windows11', 'macos'])['issues'], [])

    def test_seed_only_and_existing_seed_expansion(self):
        self.assertEqual(self.run_batch(['--os', 'ubuntu2404', '--seeds-per-os', '2', '--traj', '0']), 0)
        self.expand.assert_not_called()
        sid = storage.list_seeds()[0][0]
        self.assertEqual(self.run_batch(['--expand-seeds', sid, sid, '--traj', '1']), 0)
        self.assertEqual(self.expand.call_count, 1)

    def test_failed_seed_and_partial_render_return_nonzero(self):
        with mock.patch.object(batch_generate, 'create_seed', side_effect=BackendError('failed')):
            self.assertEqual(self.run_batch(['--os', 'windows11', '--seeds-per-os', '1', '--traj', '0']), 1)
        sid = self.create_seed('windows11')
        self.expand.side_effect = None
        self.expand.return_value = None
        self.assertEqual(self.run_batch(['--expand-seeds', sid, '--traj', '1']), 1)

    def test_saved_seed_cannot_be_overwritten_or_escape_data_root(self):
        sid = self.create_seed('windows11')
        self.expand_seed(sid, 'Fixture')
        seed = storage.load_seed(sid)
        before = (Path(seed['_dir'])/'trajectories.json').read_bytes()
        with self.assertRaises(FileExistsError):
            storage.save_seed(sid, {'os_key': 'windows11', 'image_size': '32x24'}, self.png.getvalue())
        self.assertEqual((Path(seed['_dir'])/'trajectories.json').read_bytes(), before)
        with self.assertRaises(ValueError):
            storage.seed_dir('../../elsewhere')

    def test_integrity_reports_invalid_images_boxes_and_indexes(self):
        sid = self.create_seed('windows11')
        tid = self.expand_seed(sid, 'Fixture')
        directory = Path(storage.trajectory_dir(tid))
        (directory/'obs_00.png').write_bytes(b'invalid png')
        report = check_integrity(self.root, ['windows11'])
        self.assertIn('invalid_image', {item['category'] for item in report['issues']})
        (self.root/'trajectories/_index.json').write_text(json.dumps({tid: {'os_key': [], 'seed_id': sid}}))
        report = check_integrity(self.root, ['windows11'])
        self.assertIn('unknown_platform', {item['category'] for item in report['issues']})

    def test_id_allocator_does_not_reuse_indexed_missing_ids(self):
        (self.root/'seeds').mkdir()
        (self.root/'seeds/_index.json').write_text(json.dumps({'seed_025': {'os_key': 'windows11'}}))
        self.assertEqual(storage.reserve_seed_id('windows11'), 'seed_026')

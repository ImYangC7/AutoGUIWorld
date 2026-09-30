"""Regression tests for privacy boundaries, fixtures, and safe persistence."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock
from PIL import Image

from autogui.storage import manager as storage
from autogui.utils.cost import CostLogger
from autogui.utils.jsonio import atomic_write_json
from autogui.state.environment import PERSONA_NAMES
from scripts.maintain.check_integrity import check_integrity, main as check_integrity_cli

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_check', ROOT / 'scripts/check_release.py')
release_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_check)


class ReleaseSafetyTest(unittest.TestCase):
    def test_scanner_detects_unprefixed_secret_defaults_without_echo(self):
        field = 'APP_' + 'KEY'
        fixture_value = 'fixture-secret-value'
        source = f'{field} = os.environ.get("X", "{fixture_value}")'
        result = release_check.scan_text('fixture.py', source)
        self.assertIn('hardcoded-credential-default', [x['category'] for x in result])
        self.assertNotIn(fixture_value, str(result))

    def test_scanner_distinguishes_synthetic_email_and_keyboard_keys(self):
        self.assertEqual(release_check.scan_text('fixture.py',
                         'email = "user@example.invalid"\naction = {"key": "Enter"}'), [])
        personal = 'person@' + 'mail.test'
        result = release_check.scan_text('fixture.txt', personal)
        self.assertEqual(result[0]['category'], 'non-synthetic-email')
        self.assertNotIn(personal, str(result))

    def test_persona_preserves_reviewed_source_content(self):
        for table in PERSONA_NAMES.values():
            for name, email in table.values():
                self.assertTrue(name.strip())
                self.assertIn('@', email)
        approvals = json.loads((ROOT / '.release-fixtures.json').read_text())['files']
        for filename, approval in approvals.items():
            raw = (ROOT / filename).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), approval['sha256'])
            findings = release_check.scan_text(filename, raw.decode())
            blocking, reviewed = release_check.classify_reviewed_fixture(filename, raw, findings, approvals)
            self.assertEqual(blocking, [])
            self.assertTrue(reviewed)

    def test_fixture_approval_expires_when_content_changes(self):
        raw = ('contact=' + 'person@' + 'mail.test').encode()
        findings = release_check.scan_text('fixture.txt', raw.decode())
        approvals = {'fixture.txt': {
            'sha256': hashlib.sha256(raw).hexdigest(),
            'categories': ['non-synthetic-email'], 'reason': 'Reviewed test content',
        }}
        blocking, reviewed = release_check.classify_reviewed_fixture('fixture.txt', raw, findings, approvals)
        self.assertEqual(blocking, [])
        self.assertTrue(reviewed)
        blocking, reviewed = release_check.classify_reviewed_fixture('fixture.txt', raw + b' changed', findings, approvals)
        self.assertEqual(blocking, findings)
        self.assertEqual(reviewed, [])

    def test_fixture_approval_never_exempts_credentials(self):
        raw = b'fixture'
        findings = [{'file': 'fixture.py', 'line': 1, 'category': 'hardcoded-credential-default'}]
        approvals = {'fixture.py': {
            'sha256': hashlib.sha256(raw).hexdigest(),
            'categories': ['hardcoded-credential-default'], 'reason': 'Invalid exemption',
        }}
        blocking, reviewed = release_check.classify_reviewed_fixture('fixture.py', raw, findings, approvals)
        self.assertEqual(blocking, findings)
        self.assertEqual(reviewed, [])

    def test_failed_json_serialization_preserves_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meta.json'
            atomic_write_json(path, {'previous': True})
            with self.assertRaises(TypeError):
                atomic_write_json(path, {'invalid': object()})
            self.assertEqual(json.loads(path.read_text()), {'previous': True})
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_seed_reservations_are_unique_under_concurrency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.multiple(storage, SEEDS_DIR=str(root/'seeds'),
                                     TRAJ_DIR=str(root/'trajectories'), TASK_REG_DIR=str(root/'tasks')):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    ids = list(pool.map(storage.reserve_seed_id, ['windows11'] * 40))
                self.assertEqual(len(set(ids)), 40)
                self.assertTrue(all((root/'seeds'/'windows11'/sid).is_dir() for sid in ids))

    def test_usage_log_keeps_only_valid_numeric_fields_under_concurrency(self):
        with tempfile.TemporaryDirectory() as directory:
            log = CostLogger(Path(directory)/'usage.json')
            def record(i):
                log.record('chat', 'external', {'usage': {'prompt_tokens': 1, 'diagnostic': 'private-detail'},
                                               'cost_info': {'cost': 2, 'detail': 'private-detail'}})
                log.flush()
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(record, range(20)))
            result = json.loads(log.path.read_text())
            self.assertEqual(result['summary']['total_calls'], 20)
            self.assertEqual(result['summary']['total_prompt_tokens'], 20)
            self.assertNotIn('private-detail', log.path.read_text())

    def test_cli_fails_fast_without_adapter_and_without_writing_data(self):
        env = dict(os.environ, AUTOGUI_BACKEND='')
        result = subprocess.run([sys.executable, 'cli.py', 'seed', '--os', 'windows11'],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('AUTOGUI_BACKEND', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_batch_seed_zero_is_respected_and_each_seed_differs(self):
        import argparse
        import cli
        args = argparse.Namespace(batch=3, os='windows11', seed=0, rich_state=False,
                                  skip_state=False, quality='high', web_category=None,
                                  web_site=None, web_url=None, web_content=None)
        with mock.patch.object(cli, 'create_seed') as create, contextlib.redirect_stdout(io.StringIO()):
            cli.cmd_seed(args)
        self.assertEqual([call.kwargs['seed_rng'] for call in create.call_args_list], [0, 1, 2])


class IntegrityCheckTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.seed_dir = self.root / 'seeds/windows11/seed_001'
        self.traj_dir = self.root / 'trajectories/windows11/traj_001'
        self.seed_dir.mkdir(parents=True)
        self.traj_dir.mkdir(parents=True)
        self.write(self.root / 'seeds/_index.json', {'seed_001': {'os_key': 'windows11'}})
        self.write(self.root / 'trajectories/_index.json', {
            'traj_001': {'os_key': 'windows11', 'seed_id': 'seed_001'}})
        self.write(self.seed_dir / 'seed.json', {'seed_id': 'seed_001', 'os_key': 'windows11'})
        self.write(self.seed_dir / 'trajectories.json', {'trajectory_ids': ['traj_001']})
        Image.new('RGB', (8, 8), 'white').save(self.seed_dir / 'initial.png')
        Image.new('RGB', (8, 8), 'white').save(self.traj_dir / 'obs_00.png')
        answer = {'action': 'answer', 'status': 'DONE', 'text': 'Already complete.'}
        self.write(self.traj_dir / 'meta.json', {
            'trajectory_id': 'traj_001', 'seed_id': 'seed_001', 'os_key': 'windows11',
            'plan_raw': {'actions': [{'step': 1, 'action': answer},
                                     {'step': 2, 'action': {'action': 'click'}}]},
            'steps': [{'step': 1, 'action': answer, 'status': 'success',
                       'act_frame': 'obs_00.png', 'obs_frame': 'obs_00.png'}],
        })

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value))

    def test_terminal_answer_reuses_frame_and_check_is_read_only(self):
        path = self.traj_dir / 'meta.json'
        meta = json.loads(path.read_text())
        plan = meta.pop('plan_raw')
        for fields in (('agent_plan',), ('plan_raw',), ('agent_plan', 'plan_raw')):
            with self.subTest(plan_fields=fields):
                self.write(path, dict(meta, **{field: plan for field in fields}))
                before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(check_integrity_cli(['--data-dir', str(self.root)]), 0)
                after = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
                self.assertEqual(before, after)

    def test_missing_frames_links_and_corrupt_metadata_are_reported(self):
        (self.traj_dir / 'obs_00.png').unlink()
        self.write(self.seed_dir / 'trajectories.json', {'trajectory_ids': []})
        categories = {item['category'] for item in check_integrity(self.root, ['windows11'])['issues']}
        self.assertTrue({'missing_frame', 'seed_backref_missing'} <= categories)
        (self.traj_dir / 'meta.json').write_text('{unfinished')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(check_integrity_cli(['--data-dir', str(self.root), '--json']), 1)
        self.assertIn('invalid_json', output.getvalue())

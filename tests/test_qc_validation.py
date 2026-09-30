"""Malformed model judgments must never be treated as successful QC."""
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

from PIL import Image

from autogui.analysis import qc_seeds, qc_task_seed
from autogui.utils.jsonio import load_jsonl_report, write_jsonl_report

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('trajectory_qc', ROOT/'scripts/maintain/vlm_qc_trajectory.py')
trajectory_qc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trajectory_qc)


class QCValidationTest(unittest.TestCase):
    def test_forced_qc_preserves_unselected_report_records(self):
        for kind, module in (('seed', qc_seeds), ('traj', qc_task_seed)):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
                root = Path(directory)
                target, untouched = f'{kind}_002', f'{kind}_010'
                field = f'{kind}_id'
                report_path = root / 'report.jsonl'
                old = {target: {field: target, 'verdict': 'old'},
                       untouched: {field: untouched, 'verdict': 'unchanged', 'detail': 'Keep this record.'}}
                write_jsonl_report(report_path, old)
                stack.enter_context(redirect_stdout(io.StringIO()))
                stack.enter_context(mock.patch.object(module, 'require_backend'))
                stack.enter_context(mock.patch.object(sys, 'argv', [
                    'qc', '--seed-id' if kind == 'seed' else '--traj-id', target, '--force']))
                if kind == 'seed':
                    seed = {'seed_id': target, 'os_key': 'windows11', 'scene': {'title': 'Fixture'}}
                    (root / 'seed.json').write_text(json.dumps(seed))
                    Image.new('RGB', (8, 8), 'white').save(root / 'initial.png')
                    stack.enter_context(mock.patch.object(module, 'QC_REPORT_PATH', str(report_path)))
                    stack.enter_context(mock.patch.object(module, 'seed_dir', return_value=str(root)))
                    grade = stack.enter_context(mock.patch.object(module, 'grade_seed', return_value={
                        'verdict': 'pass', 'defects': [], 'summary': 'clear'}))
                else:
                    Image.new('RGB', (8, 8), 'white').save(root / 'obs_00.png')
                    stack.enter_context(mock.patch.object(module, 'REPORT_PATH', str(report_path)))
                    stack.enter_context(mock.patch.object(module, '_collect_targets', return_value=[
                        (target, 'windows11', str(root / 'meta.json'), str(root / 'obs_00.png'),
                         'Inspect the visible form.', 'Fixture App')]))
                    grade = stack.enter_context(mock.patch.object(module, 'judge', return_value={
                        'verdict': 'match', 'app_ok': True, 'content_present': True,
                        'screenshot_shows': 'Fixture form', 'reason': 'Visible'}))
                module.main()
                grade.assert_called_once()
                saved = load_jsonl_report(report_path, field)
                self.assertEqual(saved[untouched], old[untouched])
                self.assertEqual(saved[target]['verdict'], 'pass' if kind == 'seed' else 'match')
                self.assertEqual([json.loads(line)[field] for line in report_path.read_text().splitlines()],
                                 [target, untouched])
                if kind == 'seed':
                    updated = json.loads((root / 'seed.json').read_text())
                    self.assertEqual(updated['scene'], seed['scene'])
                    self.assertEqual(updated['qc']['verdict'], 'pass')

    def test_failed_report_serialization_preserves_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'report.jsonl'
            records = {'seed_010': {'seed_id': 'seed_010'}, 'seed_002': {'seed_id': 'seed_002'}}
            write_jsonl_report(path, records)
            before = path.read_bytes()
            with self.assertRaises(TypeError):
                write_jsonl_report(path, dict(records, seed_011={'seed_id': 'seed_011', 'invalid': object()}))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(load_jsonl_report(path, 'seed_id'), records)
            self.assertEqual(list(root.iterdir()), [path])

    def test_missing_seed_defects_cannot_pass(self):
        for value in ({}, {'defects': None}, {'defects': 'clean'},
                      {'defects': [{'type': 'unknown', 'severity': 'major'}]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                qc_seeds._normalize(value)
        self.assertEqual(qc_seeds._normalize({'defects': []})['verdict'], 'pass')

    def test_seed_verdict_is_derived_from_defects(self):
        value = {'verdict': 'pass', 'defects': [{'type': 'blurry_text', 'severity': 'major'}]}
        self.assertEqual(qc_seeds._normalize(value)['verdict'], 'fail')

    def test_string_booleans_and_contradictory_match_are_rejected(self):
        with self.assertRaises(ValueError):
            qc_task_seed._normalize({'verdict': 'match', 'app_ok': 'false', 'content_present': 'false'})
        result = qc_task_seed._normalize({'verdict': 'match', 'app_ok': True, 'content_present': False})
        self.assertEqual(result['verdict'], 'partial')

    def test_incomplete_trajectory_judgment_cannot_pass(self):
        for value in ({}, {'action': {'action_valid_here': 'pass'}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                trajectory_qc._normalize(value)

    def test_trajectory_qc_routes_through_shared_adapter(self):
        verdict = {
            'grounding': {'box_hits_target': 'fail', 'box_tightness': 'pass', 'target_exists': 'pass'},
            'action': {'action_valid_here': 'pass', 'obs_transition_ok': 'pass'},
            'thinking': {'thinking_matches_screen': 'na', 'thinking_wavering': 'na'},
            'overall': 'ok',
        }
        with mock.patch.object(trajectory_qc, 'generate_text', return_value=json.dumps(verdict)) as call:
            result = trajectory_qc._call_vlm('system', 'fixture', [])
        self.assertEqual(result['overall'], 'major')
        self.assertEqual(call.call_args.kwargs['purpose'], 'qc')

    def test_trajectory_qc_reads_current_thought_and_saves_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new('RGB', (8, 8), 'white').save(root / 'obs_00.png')
            meta = {'task_description': 'Inspect the visible screen.', 'steps': [{
                'step': 1, 'action': {'action': 'answer', 'status': 'DONE'},
                'status': 'success', 'obs_frame': 'obs_00.png', 'act_frame': 'obs_00.png',
                'thought': 'The requested state is already visible.',
            }]}
            path = root / 'meta.json'
            path.write_text(json.dumps(meta))
            with mock.patch.object(trajectory_qc, '_call_vlm', return_value={'overall': 'ok', 'grounding': {}, 'action': {'obs_transition_ok': 'na'}}) as call:
                done, skipped, errored, _ = trajectory_qc._process_traj(directory, False)
            self.assertEqual((done, skipped, errored), (1, 0, 0))
            self.assertIn(meta['steps'][0]['thought'], call.call_args.args[1])
            saved = json.loads(path.read_text())
            self.assertEqual(saved['steps'][0]['qc']['overall'], 'ok')
            self.assertEqual(saved['steps'][0]['thought'], meta['steps'][0]['thought'])
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['meta.json', 'obs_00.png'])

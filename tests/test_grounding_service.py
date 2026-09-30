"""Exercise service HTTP validation and replica cleanup without GPU weights."""
import base64
import io
import queue
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from contextlib import ExitStack

from fastapi.testclient import TestClient
from PIL import Image

from services.locateanything import server


class GroundingServiceTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.enter = stack.enter_context
        frame = io.BytesIO()
        Image.new('RGB', (200, 100), 'white').save(frame, format='PNG')
        self.payload = {'image_b64': base64.b64encode(frame.getvalue()).decode(), 'phrase': 'Save button'}
        self.stack = self.enter(mock.patch.multiple(
            server, _REPLICAS=[], _SHARED={}, POOL=queue.Queue()))
        def load():
            server._REPLICAS.append(object())
            server.POOL.put(0)
        self.enter(mock.patch.object(server, '_load', side_effect=load))
        self.predict = self.enter(mock.patch.object(server, '_predict', return_value=(
            '<box><100><200><400><600></box> <box><500><500></box>')))
        self.client = self.enter(TestClient(server.app))

    def test_valid_request_returns_pixel_coordinates(self):
        self.assertEqual(self.client.get('/health').json()['free_slots'], 1)
        response = self.client.post('/ground', json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['boxes'], [[20, 20, 80, 60]])
        self.assertEqual(response.json()['points'], [[100, 50]])
        self.assertEqual(server.POOL.qsize(), 1)

    def test_bad_request_never_runs_inference(self):
        for field, value, status in [('image_b64', 'invalid', 400), ('phrase', ' ', 422),
                                     ('output_type', 'invalid', 422), ('generation_mode', 'invalid', 422),
                                     ('max_new_tokens', -1, 422)]:
            with self.subTest(field=field):
                response = self.client.post('/ground', json=dict(self.payload, **{field: value}))
                self.assertEqual(response.status_code, status)
        self.predict.assert_not_called()

    def test_failed_inference_returns_replica_and_hides_details(self):
        self.predict.side_effect = RuntimeError('hidden-provider-detail')
        response = self.client.post('/ground', json=self.payload)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('hidden-provider-detail', response.text)
        self.assertEqual(server.POOL.qsize(), 1)

    def test_busy_and_unloaded_service_fail_without_hanging(self):
        server.POOL.get_nowait()
        with mock.patch.object(server, 'QUEUE_TIMEOUT', 0):
            self.assertEqual(self.client.post('/ground', json=self.payload).status_code, 503)
        server._REPLICAS.clear()
        self.assertEqual(self.client.post('/ground', json=self.payload).status_code, 503)
        self.predict.assert_not_called()

    def test_invalid_model_coordinates_are_not_returned(self):
        self.predict.return_value = '<box><400><300><100><200></box><box><1001><0></box>'
        response = self.client.post('/ground', json=self.payload)
        self.assertEqual(response.json()['boxes'], [])
        self.assertEqual(response.json()['points'], [])

    def test_launcher_rejects_invalid_settings_and_missing_environment(self):
        source = Path(__file__).resolve().parents[1] / 'services/locateanything/start.sh'
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'start.sh'
            shutil.copy(source, script)
            for args in (['invalid'], ['start']):
                response = subprocess.run(['bash', str(script), *args], capture_output=True, text=True, timeout=5)
                self.assertEqual(response.returncode, 2)
            response = subprocess.run(['bash', str(script), 'stop'], capture_output=True, text=True, timeout=5)
            self.assertEqual(response.returncode, 0)

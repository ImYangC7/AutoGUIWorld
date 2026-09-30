"""Offline model adapter integration tests."""

import base64
import contextlib
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from autogui import config
from autogui.clients import backend, image, llm
from autogui.utils.cost import CostLogger


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.frame = self.directory / 'frame.png'
        Image.new('RGB', (16, 12), 'white').save(self.frame)
        self.module = types.ModuleType('sample_backend')
        self.module.chat = mock.Mock(return_value={'text': 'sample response'})
        self.module.image = mock.Mock(return_value={'image': self.frame.read_bytes()})
        self.stack.enter_context(mock.patch.dict(sys.modules, {'sample_backend': self.module}))
        self.stack.enter_context(mock.patch.dict(os.environ, {'AUTOGUI_BACKEND': 'sample_backend'}))
        backend._load.cache_clear()
        self.addCleanup(backend._load.cache_clear)
        self.log = CostLogger(self.directory / 'usage.json')
        for module in (llm, image):
            self.stack.enter_context(mock.patch.object(module._RATE_GATE, 'wait'))
            self.stack.enter_context(mock.patch.object(module.time, 'sleep'))
            self.stack.enter_context(mock.patch.object(module, 'get_cost_logger', return_value=self.log))
        self.network = self.stack.enter_context(mock.patch(
            'socket.socket.connect', side_effect=AssertionError('Unexpected network call')))

    def tearDown(self):
        self.network.assert_not_called()

    def test_missing_adapter_fails_before_model_call(self):
        with mock.patch.dict(os.environ, {'AUTOGUI_BACKEND': ''}):
            with self.assertRaisesRegex(backend.BackendConfigurationError, 'AUTOGUI_BACKEND'):
                llm.call_llm('system', 'task')
        self.module.chat.assert_not_called()

    def test_import_failure_hides_module_diagnostics(self):
        with mock.patch.dict(os.environ, {'AUTOGUI_BACKEND': 'unavailable_backend'}), \
             mock.patch.object(backend.importlib, 'import_module', side_effect=RuntimeError('hidden detail')):
            with self.assertRaises(backend.BackendConfigurationError) as caught:
                llm.call_llm('s', 'u')
        self.assertNotIn('hidden detail', str(caught.exception))

    def test_chat_receives_task_without_modification(self):
        self.assertEqual(llm.call_llm('system', 'task'), 'sample response')
        self.module.chat.assert_called_once_with(messages=[
            {'role': 'system', 'content': 'system'},
            {'role': 'user', 'content': 'task'},
        ], purpose='llm_chat', max_tokens=None)

    def test_vision_includes_image_bytes_and_routing(self):
        llm.call_llm_vision('system', 'inspect', [('frame', self.frame)], purpose='qc', max_tokens=512)
        call = self.module.chat.call_args.kwargs
        self.assertEqual(call['purpose'], 'qc')
        self.assertEqual(call['max_tokens'], 512)
        content = call['messages'][1]['content']
        encoded = content[2]['image_url']['url'].split(',', 1)[1]
        self.assertEqual(base64.b64decode(encoded), self.frame.read_bytes())

    def test_generation_and_edit_preserve_images(self):
        self.assertEqual(image.generate_image('initial', size='16x12'), self.frame.read_bytes())
        self.assertEqual(self.module.image.call_args.kwargs['operation'], 'generate')
        self.assertIsNone(self.module.image.call_args.kwargs['image_bytes'])
        output = self.directory / 'next.png'
        image.edit_with_ref('next frame', self.frame, output, '16x12', 'low')
        call = self.module.image.call_args.kwargs
        self.assertEqual(call['operation'], 'edit')
        self.assertEqual(call['image_bytes'], self.frame.read_bytes())
        self.assertEqual(call['size'], '16x12')
        self.assertEqual(output.read_bytes(), self.frame.read_bytes())


    def test_transient_failures_retry_and_hide_details(self):
        self.module.chat.side_effect = [backend.TransientBackendError('hidden detail'), {'text': 'ok'}]
        self.assertEqual(llm.call_llm('s', 'u', max_retries=2), 'ok')
        self.assertEqual(self.module.chat.call_count, 2)
        self.module.image.side_effect = backend.TransientBackendError('hidden detail')
        with mock.patch.object(image, '_MAX_RETRIES', 1):
            with self.assertRaises(backend.TransientBackendError) as caught:
                image.generate_image('p')
        self.assertEqual(self.module.image.call_count, 2)
        self.assertNotIn('hidden detail', str(caught.exception))

    def test_permanent_failure_does_not_retry_or_echo_details(self):
        self.module.chat.side_effect = RuntimeError('hidden detail')
        with self.assertRaises(backend.BackendError) as caught:
            llm.call_llm('s', 'u')
        self.module.chat.assert_called_once()
        self.assertEqual(str(caught.exception), 'chat operation failed')

    def test_invalid_responses_rejected(self):
        for value in (None, {}, {'text': ''}, {'text': 42}):
            with self.subTest(value=value):
                self.module.chat.return_value = value
                with self.assertRaises(backend.BackendError):
                    llm.call_llm('s', 'u')
        for value in (None, {}, {'image': ''}, {'image': b''}):
            with self.subTest(value=value):
                self.module.image.return_value = value
                with self.assertRaises(backend.BackendError):
                    image.generate_image('p')

    def test_corrupt_image_bytes_are_rejected(self):
        self.module.image.return_value = {'image': b'not-an-image'}
        with self.assertRaisesRegex(backend.BackendError, 'invalid image'):
            image.generate_image('fixture')

    def test_wrong_image_dimensions_are_rejected(self):
        with self.assertRaises(backend.BackendError):
            image.generate_image('fixture', size='32x24')


    def test_only_numeric_usage_is_recorded(self):
        self.module.chat.return_value = {
            'text': 'ok', 'deployment': 'hidden detail',
            'usage': {'prompt_tokens': 3, 'total_tokens': 5, 'completion_tokens': 'hidden detail',
                      'extra': 'hidden detail'},
        }
        llm.call_llm('s', 'u')
        self.log.flush()
        saved = self.log.path.read_text()
        self.assertNotIn('hidden detail', saved)
        self.assertEqual(json.loads(saved)['entries'][0]['usage'],
                         {'prompt_tokens': 3, 'total_tokens': 5})


class ConfigurationTest(unittest.TestCase):
    def tearDown(self):
        importlib.reload(config)

    def test_default_grounding_uses_single_loopback_endpoint(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            importlib.reload(config)
            self.assertEqual(config.LOCATE_ANYTHING_URLS, ['http://localhost:8004'])

    def test_grounding_list_is_explicit_and_strips_whitespace(self):
        with mock.patch.dict(os.environ, {'AUTOGUI_LA_URLS': ' http://localhost:8004, ,http://localhost:8005 '}):
            importlib.reload(config)
            self.assertEqual(config.LOCATE_ANYTHING_URLS,
                             ['http://localhost:8004', 'http://localhost:8005'])


if __name__ == '__main__':
    unittest.main()

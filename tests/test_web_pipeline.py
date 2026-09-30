# -*- coding: utf-8 -*-
"""Offline browser sampling, prompt dispatch, and grounding image checks."""

import io
import json
import os
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

os.environ.setdefault('AUTOGUI_OMNI', '0')   # skip optional OmniParser detector

import numpy as np
from PIL import Image, ImageDraw

from autogui.state.registry import OS_REGISTRY, ACTION_SPACES
from autogui.state.environment import (
    OS_ENV_SCHEMAS, clean_state, sample_browser_tabs,
    sample_web_page, web_site_url, state_to_descriptive_text,
)
from autogui.prompts.seed_describer import build_seed_describer_prompt
from autogui.prompts.trajectory_planner import build_trajectory_planner_prompt
from autogui.tasks.generator import _build_seed_section


class WebStateTest(unittest.TestCase):
    def test_no_cookie_banner_state(self):
        opts = OS_ENV_SCHEMAS['chrome_browser']['site_notification']['options']
        self.assertNotIn('cookie_banner', opts)
        self.assertIn('permission_prompt', opts)

    def test_web_site_constraint_populates_active_tab(self):
        state = clean_state('chrome_browser')
        state['open_tabs_count'] = 3
        enriched = sample_browser_tabs(state, rng=random.Random(7),
                                       web_category='Commerce', web_site='Shopify')
        self.assertEqual(enriched['active_tab']['site'], 'Shopify')
        self.assertEqual(enriched['active_tab']['url'], 'https://www.shopify.com/')
        self.assertEqual(len(enriched['background_tabs']), 2)

    def test_web_url_injection_pins_active_tab(self):
        state = clean_state('chrome_browser')
        state['open_tabs_count'] = 2
        enriched = sample_browser_tabs(state, rng=random.Random(3),
                                       web_url='https://www.github.com',
                                       web_content='a GitHub repo homepage')
        at = enriched['active_tab']
        self.assertEqual(at['url'], 'https://www.github.com')
        self.assertEqual(at['site'], 'www.github.com')
        self.assertIn('GitHub repo', at['content'])
        text = state_to_descriptive_text('chrome_browser', enriched)
        self.assertIn('github.com', text)
        self.assertIn('Active tab [TARGET]', text)

    def test_sample_web_page_case_insensitive(self):
        p = sample_web_page(random.Random(1), category='productivity', site='github')
        self.assertEqual(p['site'], 'GitHub')
        self.assertEqual(web_site_url('GitHub'), 'https://github.com/')


class WebPromptDispatchTest(unittest.TestCase):
    def test_planner_uses_element_web_rules_for_browser_only(self):
        web = build_trajectory_planner_prompt(
            OS_REGISTRY['chrome_browser'], 'Light mode.', 's', 'd', [],
            ACTION_SPACES['web']['actions'])
        self.assertIn('Element Grounding Rules', web)
        self.assertIn('target_element', web)
        self.assertNotIn('COORDINATE-BASED', web)
        self.assertNotIn('3 to 15 atomic actions', web)
        self.assertIn('Do NOT create cookie banners', web)
        self.assertNotIn('phone HOME SCREEN', web)

    def test_seed_prompt_drops_cookie_banner_for_browser(self):
        web = build_seed_describer_prompt(
            OS_REGISTRY['chrome_browser'], 'Light.', 'Active tab [TARGET]: GitHub.')
        self.assertIn('BROWSER-ONLY', web)
        self.assertIn('Do NOT draw cookie banners', web)


class WebTaskSeedSectionTest(unittest.TestCase):
    def test_seed_section_lists_active_tab(self):
        seed = {'global_state': {'visible_elements': []},
                'env_state': {'active_tab': {'site': 'YouTube', 'category': 'Media',
                                             'content': 'a youtube home page'},
                              'background_tabs': [{'site': 'Reddit', 'content': 'a reddit feed'}]}}
        sec = _build_seed_section(seed)
        self.assertIn('Active tab (target): YouTube', sec)
        self.assertIn('Background tab: Reddit', sec)


class DualGrounderTest(unittest.TestCase):
    """Grounding backends share a record format and preserve clean image pixels."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = directory.name
        self.obs = os.path.join(self.dir, 'obs.png')
        self.act = os.path.join(self.dir, 'act.png')
        Image.new('RGB', (1792, 1024), (240, 240, 240)).save(self.obs)

    @staticmethod
    def _nonred_changed(obs_path, act_path):
        o = np.array(Image.open(obs_path).convert('RGB')).astype(int)
        a = np.array(Image.open(act_path).convert('RGB')).astype(int)
        red = (a[:, :, 0] > 150) & (a[:, :, 1] < 80) & (a[:, :, 2] < 80)
        return int(((np.abs(o - a).sum(axis=2) > 0) & ~red).sum())


    def test_mai_ui_grounder_pixel_identical_pil(self):
        import autogui.clients.grounding as g
        import autogui.clients.box_backends as bb
        with mock.patch.object(g, 'ground_point', return_value=[900, 500]):
            boxes = bb.annotate_act_frame(self.obs, self.act, ['Sign in button'],
                                          grounder='mai_ui', render='pil')
        self.assertEqual(len(boxes), 1)
        self.assertIn('bbox_px', boxes[0])
        self.assertEqual(self._nonred_changed(self.obs, self.act), 0)

    def test_gpt55_grounder_returns_same_shape(self):
        import json
        import autogui.clients.grounding as g
        import autogui.clients.box_backends as bb
        with mock.patch.object(g, 'ground_point', return_value=[900, 500]):
            mai = bb.annotate_act_frame(self.obs, self.act, ['btn'], grounder='mai_ui', render='pil')
        fake = json.dumps({'bbox': [880, 480, 1020, 540], 'confidence': 'high'})
        with mock.patch('autogui.clients.llm.call_llm_vision', return_value=fake):
            gpt = bb.annotate_act_frame(self.obs, self.act, ['btn'], grounder='gpt55', render='pil')
        self.assertEqual(set(gpt[0]), set(mai[0]))           # identical record shape
        self.assertIn(gpt[0]['source'], ('gpt55', 'gpt55_cv2'))

    def test_render_axis_is_orthogonal_to_grounder(self):
        import json
        import autogui.clients.box_backends as bb

        def fake_edit(prompt, ref, out, size=None, quality=None):
            Image.new('RGB', (1792, 1024), (200, 200, 200)).save(out)
            return out

        fake = json.dumps({'bbox': [880, 480, 1020, 540]})
        with mock.patch('autogui.clients.llm.call_llm_vision', return_value=fake):
            pil = bb.annotate_act_frame(self.obs, self.act, ['btn'], grounder='gpt55', render='pil')
        with mock.patch('autogui.clients.llm.call_llm_vision', return_value=fake), \
             mock.patch.object(bb, 'edit_with_ref', side_effect=fake_edit):
            img2 = bb.annotate_act_frame(self.obs, self.act, ['btn'], grounder='gpt55',
                                         render='image2', image_size='1792x1024')
        self.assertEqual(pil[0]['bbox_px'], img2[0]['bbox_px'])  # render never changes coords


class BboxCvTest(unittest.TestCase):
    def test_redbox_cli_finds_platform_organized_trajectories(self):
        from autogui.analysis import redbox
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            root = data / 'trajectories'
            td = root / 'windows11' / 'traj_001'
            td.mkdir(parents=True)
            frame = Image.new('RGB', (200, 160), 'white')
            ImageDraw.Draw(frame).rectangle([45, 45, 130, 95], outline=(255, 0, 0), width=3)
            frame.save(td / 'act_01.png')
            (td / 'meta.json').write_text(json.dumps({'steps': [
                {'step': 1, 'n_boxes': 1, 'act_frame': 'act_01.png'},
            ]}))
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            for args in ([], [str(root)], [str(td.parent)], [str(td)]):
                with self.subTest(args=args), mock.patch.object(redbox, 'DATA_DIR', str(data)), \
                     redirect_stdout(io.StringIO()) as output:
                    redbox.main(args)
                self.assertIn('traj_001  match 1/1', output.getvalue())
                self.assertNotIn('windows11  match', output.getvalue())
            with redirect_stdout(io.StringIO()) as output:
                redbox.main([str(td / 'act_01.png')])
            self.assertTrue(json.loads(output.getvalue())['found'])
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_before_after_diff_ignores_native_red(self):
        from autogui.clients.bbox_cv import detect_new_red_bbox
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        d = directory.name
        before = os.path.join(d, 'b.png')
        ann = os.path.join(d, 'a.png')
        img = Image.new('RGB', (1792, 1024), (245, 245, 245))
        ImageDraw.Draw(img).rectangle([100, 100, 260, 150], fill=(220, 30, 30))  # native red UI
        img.save(before)
        img2 = img.copy()
        d2 = ImageDraw.Draw(img2)
        for i in range(2):
            d2.rectangle([900 - i, 500 - i, 1000 + i, 540 + i], outline=(255, 0, 0))  # new box
        img2.save(ann)
        bb = detect_new_red_bbox(before, ann, hint_bbox=[905, 505, 995, 535], require_hint=True)
        self.assertIsNotNone(bb)
        self.assertGreater(bb[0], 800)   # picked the NEW box, not the native red block
        self.assertGreater(bb[1], 400)


if __name__ == '__main__':
    unittest.main()

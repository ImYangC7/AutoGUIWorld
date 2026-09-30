# -*- coding: utf-8 -*-
"""Detect candidate element boxes with OmniParser (YOLOv8).

Runs the detector once per screenshot. The grounding client selects a box
containing the predicted point and handles fallback refinement.

Model weights: OmniParser-v2.0/icon_detect/model.pt (40 MB YOLOv8). Set the
path via the AUTOGUI_OMNI_WEIGHTS environment variable.

Public API:
    detector = OmniDetector()                         # loads once
    boxes = detector.detect(image_path)
"""

import os
import threading

_DEFAULT_WEIGHTS = os.environ.get(
    'AUTOGUI_OMNI_WEIGHTS',
    'OmniParser-v2.0/icon_detect/model.pt',
)

Box = list[int]


class OmniDetector:
    def __init__(self, weights: str = _DEFAULT_WEIGHTS, device: int = 0,
                 conf: float = 0.05, imgsz: int = 1280):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.device = device
        self.conf = conf
        self.imgsz = imgsz
        # YOLO.predict on a shared model is not thread-safe; serialize it.
        # Inference is ~70ms so the lock is essentially free under concurrency.
        self._lock = threading.Lock()

    def detect(self, image_path: str) -> list[Box]:
        """Return all element boxes as a list of [x0, y0, x1, y1] in pixels."""
        with self._lock:
            res = self.model.predict(image_path, device=self.device, conf=self.conf,
                                     imgsz=self.imgsz, verbose=False)[0]
            return [[int(v) for v in b] for b in res.boxes.xyxy.cpu().numpy()]

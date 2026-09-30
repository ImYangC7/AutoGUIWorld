# -*- coding: utf-8 -*-
"""LocateAnything-3B grounding HTTP service (OpenAI-ish minimal JSON API).

Runs in its OWN venv (transformers==4.57.1 + trust_remote_code) so it never
collides with AutoGUI's transformers. AutoGUI's `locate_anything` grounder calls
this over HTTP, exactly like the existing MAI-UI vLLM service on port 8003.

Concurrency: loads LA_REPLICAS independent model copies on the (single) visible
GPU and serves requests from a replica pool. FastAPI runs sync endpoints in a
threadpool, so N in-flight requests grab N distinct replicas and run in parallel;
the decode phase leaves GPU gaps that overlapping replicas fill. Pin to one GPU
with CUDA_VISIBLE_DEVICES (the launcher sets it).

Endpoints:
  GET  /health   -> {"status": "ok", "model": ..., "replicas": N}
  POST /ground   {image_b64, phrase, output_type=box|point, generation_mode}
        -> {"boxes": [[x1,y1,x2,y2], ...], "points": [[x,y], ...], "raw": str,
            "width": W, "height": H}   (coords in PIXELS of the posted image)

The model card's inference interface uses AutoModel/AutoTokenizer/AutoProcessor,
+ trust_remote_code, py_apply_chat_template, process_vision_info, custom generate
signature, 0-1000 normalized integer coords mapped back to pixels here.
"""
import base64
import binascii
import io
import os
import queue
import re
import time
from contextlib import asynccontextmanager
from typing import Literal

from PIL import Image
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MODEL_PATH = os.environ.get(
    "LA_MODEL_PATH",
    "LocateAnything-3B",
)
DEFAULT_MODE = os.environ.get("LA_GEN_MODE", "hybrid")  # fast | slow | hybrid
MAX_NEW_TOKENS = int(os.environ.get("LA_MAX_NEW_TOKENS", "2048"))
REPLICAS = int(os.environ.get("LA_REPLICAS", "1"))
QUEUE_TIMEOUT = 10

_BOX_RE = re.compile(r"<box><(\d+)><(\d+)><(\d+)><(\d+)></box>")
_PT_RE = re.compile(r"<box><(\d+)><(\d+)></box>")

@asynccontextmanager
async def lifespan(app):
    try:
        _load()
        yield
    finally:
        _REPLICAS.clear()
        _SHARED.clear()
        while not POOL.empty():
            POOL.get_nowait()


app = FastAPI(title="LocateAnything-3B grounding", lifespan=lifespan)

# Shared tokenizer/processor (stateless, thread-safe for our read-only use) +
# a list of model replicas; POOL hands out the index of a free replica.
_SHARED = {}
_REPLICAS = []           # list of nn.Module copies, one per pool slot
POOL: "queue.Queue[int]" = queue.Queue()


def _build_model():
    import torch
    from transformers import AutoModel, AutoConfig
    # config ships _attn_implementation="magi" (Hopper-only kernel, not installed);
    # its fallback selects flash_attention_2 which the decoder forward does NOT
    # implement -> force sdpa on both towers.
    cfg = AutoConfig.from_pretrained(MODEL_PATH, trust_remote_code=True)
    cfg._attn_implementation = "sdpa"
    cfg.text_config._attn_implementation = "sdpa"
    cfg.vision_config._attn_implementation = "sdpa"
    return AutoModel.from_pretrained(
        MODEL_PATH, config=cfg, torch_dtype=torch.bfloat16,
        trust_remote_code=True, attn_implementation="sdpa",
    ).to("cuda").eval()


def _load():
    import torch
    from transformers import AutoTokenizer, AutoProcessor
    if REPLICAS < 1:
        raise ValueError('LA_REPLICAS must be positive')
    if not torch.cuda.is_available():
        raise RuntimeError('LocateAnything service requires CUDA')
    print(f">> loading {MODEL_PATH}  (replicas={REPLICAS}) ...", flush=True)
    t0 = time.time()
    _SHARED["tok"] = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    _SHARED["proc"] = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
    for i in range(REPLICAS):
        ti = time.time()
        _REPLICAS.append(_build_model())
        POOL.put(i)
        free, total = torch.cuda.mem_get_info()
        print(f">>   replica {i} ready in {time.time()-ti:.1f}s "
              f"(GPU free {free/2**30:.1f}/{total/2**30:.1f} GiB)", flush=True)
    print(f">> all {REPLICAS} replicas loaded in {time.time() - t0:.1f}s", flush=True)


class GroundReq(BaseModel):
    image_b64: str = Field(min_length=1)
    phrase: str = Field(min_length=1, pattern=r'\S')
    output_type: Literal['box', 'point'] = 'box'
    generation_mode: Literal['fast', 'slow', 'hybrid'] = Field(default=DEFAULT_MODE, validate_default=True)
    max_new_tokens: int = Field(default=MAX_NEW_TOKENS, gt=0, le=8192, validate_default=True)


@app.get("/health")
def health():
    return {"status": "ok" if _REPLICAS else "loading",
            "model": MODEL_PATH, "replicas": len(_REPLICAS),
            "free_slots": POOL.qsize()}


def _predict(model, image, question, generation_mode, max_new_tokens):
    import torch
    tok, proc = _SHARED["tok"], _SHARED["proc"]
    messages = [{"role": "user", "content": [
        {"type": "image", "image": image}, {"type": "text", "text": question}]}]
    text = proc.py_apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    images, videos = proc.process_vision_info(messages)
    inputs = proc(text=[text], images=images, videos=videos, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        resp = model.generate(
            pixel_values=inputs["pixel_values"].to(torch.bfloat16),
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            image_grid_hws=inputs.get("image_grid_hws", None),
            tokenizer=tok,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            generation_mode=generation_mode,
            temperature=0.0,
            do_sample=False,
            verbose=False,
        )
    return resp[0] if isinstance(resp, tuple) else resp


@app.post("/ground")
def ground(req: GroundReq):
    try:
        with Image.open(io.BytesIO(base64.b64decode(req.image_b64, validate=True))) as source:
            img = source.convert('RGB')
    except (ValueError, OSError, binascii.Error):
        raise HTTPException(status_code=400, detail='Invalid image data') from None
    W, H = img.size
    if req.output_type == "point":
        q = f"Point to: {req.phrase}."
    else:
        q = f"Locate the region that matches the following description: {req.phrase}."
    t0 = time.time()
    if not _REPLICAS:
        raise HTTPException(status_code=503, detail='Model is not ready')
    try:
        idx = POOL.get(timeout=QUEUE_TIMEOUT)
    except queue.Empty:
        raise HTTPException(status_code=503, detail='All replicas are busy') from None
    try:
        answer = _predict(_REPLICAS[idx], img, q, req.generation_mode, req.max_new_tokens)
        if not isinstance(answer, str):
            raise ValueError('Model returned a non-text result')
    except Exception:
        raise HTTPException(status_code=502, detail='Grounding inference failed') from None
    finally:
        POOL.put(idx)
    # Greedy: 4-coord boxes first, then leftover 2-coord points (point regex would
    # otherwise mis-match the first half of a box).
    boxes = []
    for m in _BOX_RE.finditer(answer):
        x1, y1, x2, y2 = (int(g) for g in m.groups())
        if 0 <= x1 < x2 <= 1000 and 0 <= y1 < y2 <= 1000:
            boxes.append([x1 / 1000 * W, y1 / 1000 * H, x2 / 1000 * W, y2 / 1000 * H])
    points = []
    for m in _PT_RE.finditer(_BOX_RE.sub("", answer)):
        x, y = int(m.group(1)), int(m.group(2))
        if 0 <= x <= 1000 and 0 <= y <= 1000:
            points.append([min(W - 1, x / 1000 * W), min(H - 1, y / 1000 * H)])
    return {
        "boxes": boxes, "points": points, "raw": answer,
        "width": W, "height": H, "latency_s": round(time.time() - t0, 2),
    }

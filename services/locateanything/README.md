# LocateAnything grounding service

This optional service provides the `locate_anything` grounder. Run it in its own Python
virtual environment with CUDA-capable PyTorch and the model's required Transformers runtime.
Set `LA_MODEL_PATH` to the installed model directory.

```bash
cd services/locateanything
python -m venv .venv
source .venv/bin/activate
pip install torch torchvision "transformers==4.57.1" peft pillow numpy opencv-python-headless \
  "fastapi>=0.115,<1" "pydantic>=2,<3" uvicorn decord lmdb
export LA_MODEL_PATH=/path/to/LocateAnything-3B
bash start.sh
```

The launcher defaults to GPU 0, port 8004, one replica, and loopback binding. `LA_GPU`,
`LA_PORT`, `LA_REPLICAS`, and `LA_HOST` override those choices. Review `server.py` for the
model loading and attention configuration required by your installed checkpoint.
Logs and the managed process ID are stored in `.runtime/`. Use `bash start.sh stop`
to stop that instance. Starting the process does not imply the model is ready;
wait for `/health` to report `status: "ok"` before generating trajectories.

`GET /health` returns readiness and replica counts. `POST /ground` accepts an encoded
image, a target phrase, and `output_type` (`box` or `point`). Coordinates in the response
are screen pixels.

From the project root, configure `AUTOGUI_LA_URL` for one service or `AUTOGUI_LA_URLS`
for several instances, then use `--grounder locate_anything`. If only a point is returned,
the client attempts optional OmniParser refinement and then computer-vision refinement.
Use `AUTOGUI_OMNI_WEIGHTS` to point at local detector weights, or `AUTOGUI_OMNI=0` to
skip that detector. GPU inference is separate from the offline test suite.

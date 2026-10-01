<h1 align="center">AutoGUIWorld</h1>

<h3 align="center">Image Generators as Visual World Models for GUI Agent</h3>

<p align="center">
  <a href="https://huggingface.co/YangC777/AGW-35B/blob/main/AutoGUIWorld_Report.pdf"><img src="https://img.shields.io/badge/Technical_Report-PDF-B31B1B?logo=readthedocs&amp;logoColor=white" alt="Technical Report (PDF)" /></a>
  <a href="#demo"><img src="https://img.shields.io/badge/Demo-Watch_Video-2563EB?logo=youtube&amp;logoColor=white" alt="Watch the demo video" /></a>
  <a href="#getting-started"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&amp;logoColor=white" alt="Python 3.10+" /></a>
  <a href="https://huggingface.co/YangC777/AGW-35B"><img src="https://img.shields.io/badge/Model-AGW--35B-FFD21E?logo=huggingface&amp;logoColor=111111" alt="AGW-35B" /></a>
  <a href="#pipeline"><img src="https://img.shields.io/badge/Pipeline-Seed--Planner--Voyager-2563EB" alt="Seed, Planner, Voyager pipeline" /></a>
  <a href="#gui-world-sampling"><img src="https://img.shields.io/badge/Platforms-Desktop%20%7C%20Mobile-0F766E" alt="Desktop and mobile" /></a>
</p>

<p align="center">
  <strong><a href="#demo">Demo</a> · <a href="#overview">Overview</a> · <a href="#pipeline">Pipeline</a> · <a href="#getting-started">Getting Started</a> · <a href="#data-format">Data Format</a> · <a href="https://huggingface.co/YangC777/AGW-35B">Model</a> · <a href="https://huggingface.co/YangC777/AGW-35B/blob/main/AutoGUIWorld_Report.pdf">Technical Report</a></strong>
</p>

<p align="center">
  <img src="assets/autoguiworld-hero.png" width="100%" alt="AutoGUIWorld application and platform coverage" />
</p>

## TL;DR

**AutoGUIWorld generates grounded GUI interaction trajectories without running every target software environment.**

It samples a structured GUI world, renders an initial screenshot, creates a task for that scene, and rolls out an atomic action sequence through iterative image editing. Pointing actions receive spatial annotations, and quality-control tools audit grounding and visual transitions.

The released code supports desktop scenes across Windows, macOS, Ubuntu, and Chrome, together with Android and iOS mobile scenes. The AutoGUIWorld training set used in our technical report contains **79,266** grounded and filtered examples across Chrome, Ubuntu, Windows, and macOS. Fine-tuning Qwen3.5-35B-A3B on these trajectories produces [AGW-35B](https://huggingface.co/YangC777/AGW-35B), a cross-platform computer-use agent.

> [!NOTE]
> **Scope.** AutoGUIWorld produces training trajectories in visual state space. It does not execute them in a real desktop environment or independently verify task completion.

## Demo

Watch the full AutoGUIWorld demo (2 min 6 sec).

https://github.com/user-attachments/assets/abadb96f-b00e-4cc9-a4e0-58950f71005f

[Watch or download the 1080p video](https://github.com/ImYangC7/AutoGUIWorld/raw/refs/heads/main/assets/demo/AutoGUIWorld_Demo.mp4).

## Overview

GUI-agent datasets are bounded by the software available during collection. Adding an application usually requires installation, configuration, task initialization, runtime infrastructure, and reliable resets. AutoGUIWorld expands coverage by generating interaction experience directly in visual state space.

AutoGUIWorld separates semantic planning from visual rendering. The Meta Planner turns a scene-conditioned task into atomic actions. For each action, Voyager reads the latest clean screenshot and describes the intended visual change; the image backend renders the next state. Grounding adds spatial labels, while quality-control tools inspect scene validity, action alignment, and transition fidelity.

## Pipeline

<p align="center">
  <img src="assets/autoguiworld-overview.png" width="100%" alt="AutoGUIWorld method overview" />
</p>

The generation loop has four stages:

1. **Sample and render a seed.** Choose the platform, appearance, and initial GUI state, then render `initial.png`.
2. **Create a task and plan actions.** Generate a task grounded in the visible scene and decompose it into atomic GUI actions.
3. **Roll out visual transitions.** Voyager reads the latest clean screenshot and describes the intended next state for the image-editing backend.
4. **Annotate and audit.** Ground pointing targets, write `act_k.png` and `obs_k.png`, and run optional quality-control checks.

### Core Components

| Component | Role | Main implementation |
|---|---|---|
| GUI world sampler | Samples platform constraints, appearance, windows/tabs, visible content, and blockers | `autogui/state/` |
| Seed realization | Expands structured state into a visual description and renders the initial screenshot | `autogui/pipeline/seed.py` |
| Task generator | Produces scene-compatible tasks and filters near duplicates | `autogui/tasks/` |
| Meta Planner | Decomposes a task into grounded atomic actions | `autogui/prompts/trajectory_planner.py` |
| Voyager | Uses the latest screenshot and action context to describe the next visual state | `autogui/pipeline/trajectory.py` |
| Grounding | Locates visible targets and creates action-label boxes | `autogui/clients/grounding.py` |
| Storage | Maintains seeds, trajectories, indexes, and provenance | `autogui/storage/` |
| Quality control | Audits seed quality, task relevance, grounding, and transitions | `autogui/analysis/`, `scripts/maintain/` |

## GUI World Sampling

AutoGUIWorld represents an initial GUI scene through three complementary factors:

| Factor | Examples |
|---|---|
| **OS substrate** | OS type, screen geometry, action space, UI conventions, application ecosystem |
| **Visual appearance** | Theme, color palette, wallpaper, typography, density, shape and material |
| **Initial GUI state** | Window or tab count, layout, foreground relation, page/app content, visible controls, task objects |

The current registry covers two platform families. Desktop includes native operating-system interfaces and Chrome web interfaces; mobile includes Android and iOS.

| Platform | Key | Surface | Default canvas |
|---|---|---|---:|
| Desktop | `windows11` | Windows 11 desktop | 1792 × 1024 |
| Desktop | `macos` | macOS desktop | 1792 × 1024 |
| Desktop | `ubuntu2404` | Ubuntu 24.04 GNOME desktop | 1792 × 1024 |
| Desktop | `chrome_browser` | Full-screen Chrome and web page | 1792 × 1024 |
| Mobile | `android` | Android phone home screen | 1024 × 2272 |
| Mobile | `ios` | iPhone home screen | 1024 × 2272 |

Desktop scenes use structured window inventories, browser scenes use structured tab inventories, and mobile scenes use layered home-screen inventories. A fixed random seed makes structured state sampling reproducible; generated text and pixels can still vary across backend calls.

## Getting Started

### Requirements

- Python 3.10 or newer
- A separately installed model adapter providing text, vision, and image generation/editing
- A grounding backend for pointing actions

### Install

```bash
git clone https://github.com/ImYangC7/AutoGUIWorld.git
cd AutoGUIWorld

python -m venv .venv
source .venv/bin/activate
pip install -r requirements-generation.txt
```

### Configure the Model Adapter

Install your model adapter separately, then select its Python module:

```bash
export AUTOGUI_BACKEND=my_model_backend
```

The adapter implements `chat()` and `image()`. It owns the provider connection settings;
AutoGUIWorld passes tasks and images through a shared interface. Text, vision, annotation,
and quality-control calls use that same interface. See the [adapter contract](docs/backend.md)
for input types, output types, retries, and a minimal implementation example.

Choose the grounding backend before generating trajectories. `gpt55` uses the configured
vision adapter; the name is a compatibility selector. `locate_anything` is the default and
requires the [local grounding service](services/locateanything/README.md).

```bash
# Ground through the vision adapter without a separate local grounding model.
export AUTOGUI_GROUNDER=gpt55
```

For offline development, `pip install -r requirements-dev.txt` installs the core libraries,
linter, and HTTP test dependencies without downloading model weights. Automatic task generation and persistent
task deduplication use `sentence-transformers` from `requirements-generation.txt`.

### Generate a Seed

```bash
# Deterministic structured state sampling
python cli.py seed --os windows11 --seed 42

# Browser seed constrained to a site
python cli.py seed --os chrome_browser --web-site GitHub

# Create several mobile seeds
python cli.py seed --os android --batch 3
```

Each seed stores the sampled world state and its rendered `initial.png`.

### Expand a Seed into Trajectories

```bash
# Use an explicit task
python cli.py expand \
  --seed-id seed_001 \
  --task "Open Settings and switch the system to dark mode"

# Generate five scene-conditioned tasks automatically
python cli.py expand --seed-id seed_001 --auto-tasks 5

# Select a grounding backend explicitly
python cli.py expand \
  --seed-id seed_001 \
  --task "Open the current project in a new window" \
  --grounder locate_anything
```

### Inspect Generated Data

```bash
python cli.py list seeds
python cli.py list seeds --os ubuntu2404
python cli.py list trajectories --seed-id seed_001
```

## Batch Generation

`batch_generate.py` runs generation in three stages:

1. create independent seeds in parallel;
2. generate scene-conditioned tasks;
3. render trajectories concurrently while keeping each trajectory's observation chain serial.

```bash
# Generate initial scenes without trajectories
python batch_generate.py --os windows11 --seeds-per-os 25 --traj 0 --workers 8

# Two platforms, 25 seeds each, three trajectories per seed
python batch_generate.py \
  --os windows11 macos \
  --seeds-per-os 25 \
  --traj 3 \
  --workers 16

# Expand existing seeds only
python batch_generate.py \
  --expand-seeds seed_012 seed_013 \
  --traj 3 \
  --workers 8

# Generate long multi-stage workflows
python batch_generate.py \
  --os ubuntu2404 \
  --seeds-per-os 10 \
  --traj 2 \
  --long-horizon \
  --workers 8
```

The script renders different trajectories in parallel. Steps within one trajectory remain serial because `obs_k` depends on `obs_{k-1}`.
Generation commands return a nonzero exit code if any requested seed, task, or trajectory
is missing or incomplete. The batch summary counts completed trajectories.

## Grounding and Action Annotations

Pointing actions are annotated on the clean pre-action screenshot. The default `pil` renderer changes only the box pixels, and annotated frames are never reused as later observations.

Available grounding backends:

| Backend | Description | Local service |
|---|---|---|
| `locate_anything` | LocateAnything-3B point/box grounding with optional OmniParser refinement | Yes |
| `mai_ui` | MAI-UI point prediction followed by box refinement | Yes |
| `gpt55` | Coordinates predicted by the configured vision-language backend | No additional model |

Select the default backend globally:

```bash
export AUTOGUI_GROUNDER=locate_anything
```

For local LocateAnything setup, see [`services/locateanything/README.md`](services/locateanything/README.md).

## Data Format

Generated artifacts live under `data/`, which is intentionally excluded from Git.

```text
data/
├── seeds/
│   ├── _index.json
│   └── <os_key>/seed_001/
│       ├── seed.json
│       ├── initial.png
│       └── trajectories.json
├── trajectories/
│   ├── _index.json
│   └── <os_key>/traj_001/
│       ├── meta.json
│       ├── obs_00.png
│       ├── act_01.png
│       ├── obs_01.png
│       └── ...
├── task_registries/
└── _cost_log.json
```

- `obs_00.png` is copied from the seed's `initial.png`.
- `obs_k.png` is the clean visual state after action `k`.
- `act_k.png` is the pre-action observation with target boxes for pointing actions.
- `meta.json` stores the task, high-level plan, atomic actions, frame mapping, grounding boxes, Voyager outputs, status, and provenance.
- `agent_plan` contains the planned action sequence, saved before rendering begins.
- Trajectory `status` is `complete` when every planned step through the first terminal answer is generated, or `partial` after a failure. Each step records `success` or `error` separately.
- If grounding misses a required target or a transition fails, the pipeline stops and preserves the valid prefix and error record.

## Quality Control

Quality checks cover seed screenshots, task relevance, grounded targets, and visual
transitions. These checks use the model adapter. The data integrity checker runs
offline and reports missing files, incomplete steps, and broken seed/index links.

```bash
python -m autogui.analysis.qc_seeds --help
python -m autogui.analysis.qc_task_seed --help
python scripts/maintain/vlm_qc_trajectory.py --help
python scripts/maintain/check_integrity.py --os windows11 macos ubuntu2404 chrome_browser
python redbox_cli.py data/trajectories
```

`redbox_cli.py` inspects saved red-box geometry offline. It accepts an image,
one trajectory, a platform directory, or the full trajectory directory.
QC rejects missing or unreadable evidence, and retries earlier failed assessments.
The integrity checker verifies image format and size as well as metadata links.

If generation stops, inspect the error in `meta.json`, restore backend availability,
and generate a new trajectory from the saved seed with the same task:

```bash
python cli.py expand --seed-id seed_001 --task "Your original task" --skip-dedup
```

The retry receives a new trajectory ID. Its incomplete predecessor remains available
for inspection.

Operational lessons and known generation failure modes are documented in [`docs/failure_case.md`](docs/failure_case.md).

## Repository Structure

```text
autogui/
├── state/       structured GUI world and platform registries
├── prompts/     seed, planner, Voyager, grounding, and QC prompts
├── tasks/       task generation, platform features, and deduplication
├── pipeline/    seed realization and closed-loop trajectory generation
├── clients/     LLM, image, grounding, detection, and refinement backends
├── storage/     seed and trajectory persistence
├── analysis/    visual and grounding audits
└── utils/       credentials, rate limits, JSON, and cost accounting

scripts/
├── check_release.py          source hygiene scan
└── maintain/
    ├── check_integrity.py    saved data and index checks
    └── vlm_qc_trajectory.py  per-step visual quality checks and reports

services/
└── locateanything/   optional self-hosted grounding service
```

## Tests

The offline tests cover the full seed-to-trajectory flow on all six platforms,
sampling constraints, model adapters, grounding images, failure handling, quality
checks, and storage integrity. Model calls use local fixtures.

```bash
python -m unittest discover -s tests -v
python scripts/check_release.py
ruff check .
```

## Downstream Model

[AGW-35B](https://huggingface.co/YangC777/AGW-35B) is obtained by fine-tuning Qwen3.5-35B-A3B on AutoGUIWorld trajectories. In the technical report, the final checkpoint improves all four interactive benchmarks:

| Benchmark | Metric | Base | AGW-35B | Gain |
|---|---|---:|---:|---:|
| OSWorld | Mean task score | 33.0 | **40.8** | **+7.8** |
| Windows Agent Arena | Mean task score | 19.4 | **27.9** | **+8.5** |
| macOSWorld | Task success | 28.1 | **45.0** | **+16.9** |
| ScienceBoard | Task success | 14.0 | **32.2** | **+18.2** |

Scores are percentages; gains are percentage points. The model card describes the evaluation protocol, ScreenSpot-Pro grounding results, interaction contract, and deployment example.

## Citation

```bibtex
@techreport{hunyuan2026autoguiworld,
  title       = {AutoGUIWorld: Image Generators as Visual World Models for GUI Agent},
  author      = {{Hunyuan AI Data Team}},
  institution = {Tencent Hunyuan},
  year        = {2026}
}
```

## Acknowledgements

AutoGUIWorld builds on multimodal language models, image generation models, GUI grounding systems, and the broader computer-use research ecosystem. We thank the teams behind Qwen, LocateAnything, OmniParser, OSWorld, Windows Agent Arena, macOSWorld, ScienceBoard, and ScreenSpot-Pro.

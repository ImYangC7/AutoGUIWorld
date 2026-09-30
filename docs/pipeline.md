# Pipeline and data contracts

## Structure

`state/` samples platform appearance and GUI inventories. `tasks/` generates instructions
for a saved seed. `prompts/` builds scene, Planner, and Voyager inputs. `pipeline/` runs
image generation and editing; `clients/` provides model and grounding interfaces;
`storage/` keeps seeds, trajectories, and their indexes.

## Model calls

`AUTOGUI_BACKEND` selects a separately installed adapter providing `chat()` and `image()`.
Missing configuration is reported before generation. Explicit transient errors use bounded
retries; permanent errors stop the operation. Image outputs are validated, and usage logs
accept only recognized numeric fields. See [the adapter contract](backend.md).

## Seed-first generation

1. `create_seed` samples the platform's visual style and initial state. Desktop windows,
   browser tabs, and mobile home screens have their own inventories.
2. The scene describer turns that sampled state into an image-generation prompt.
3. The rendered `initial.png` and structured state are saved as a seed.
4. `generate_tasks_for_seed` proposes new tasks using the saved scene and its visible
   elements. A user may also supply an instruction when expanding an existing seed.
5. The Meta Planner creates and validates an action sequence from the task and seed.
6. For each action, grounding annotates the pre-action image, Voyager describes the next
   visible state, and image editing produces the next clean observation.

Terminal `answer` actions reuse the latest observation and end the trajectory. A grounding or render
failure retains a completed prefix and an error record. Generated infeasible tasks retain
their upfront/exploration annotations so the planner can represent a refusal appropriately.

## Storage

Seeds are written to `data/seeds/<os_key>/`; trajectories to `data/trajectories/<os_key>/`.
The metadata records the seed link, task, plan, images, labels, and generation status.
New trajectories store their plan once, in `agent_plan`, before the first action is
rendered. The integrity checker also accepts `plan_raw` from earlier datasets.
Scene personas remain preset visual content. Each step records `success` or `error`;
trajectory `status` is `complete` or `partial`. These describe generation, not real
application execution. Partial runs are excluded from batch success counts and the
successful-task registry.

JSON metadata and rendered images use write-then-replace operations. IDs and index updates are guarded
within one process. Run one writer process per data directory. Cross-file updates are not
a database transaction; use the integrity checker after an interrupted run.

## Quality and interrupted runs

`qc_seeds` assesses initial screenshots, `qc_task_seed` checks tasks against their saved
scene, and `vlm_qc_trajectory.py` inspects action labels and visual transitions. The QC
runners use the same model adapter. Malformed assessments are treated as errors.
Seed and task QC share the JSONL report reader and atomic writer in `utils/jsonio.py`.
Each report remains a full snapshot, including records outside the current selection.

`python scripts/maintain/check_integrity.py` checks all six platforms for missing frames,
incomplete steps, and broken index or seed references without changing data. Use `--os`
to select platforms, `--data-dir` for another dataset directory, or `--json` for a
machine-readable report. Exit code 1 indicates detected issues. A seed without
trajectories is valid, and terminal `answer` steps reuse their last observation.

After a generation failure, inspect the step error in `meta.json` and restore the backend.
Run `python cli.py expand --seed-id <id> --task "<original task>" --skip-dedup` to generate
a new trajectory from that seed. The original partial trajectory remains on disk.

Batch generation uses `batch_generate.py`: `--traj 0` creates seeds only,
`--expand-seeds` expands saved seeds, and `--long-horizon` requests longer workflows.

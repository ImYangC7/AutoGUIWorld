# Generation failure modes

| Symptom | Cause to check | Recovery |
|---|---|---|
| Few accepted tasks | Similarity threshold and task registry coverage | Inspect rejected instructions and select a suitable deduplication threshold. |
| A trajectory stops after a valid prefix | Voyager or image editing failed | Check the step error, restore backend availability, and generate a new trajectory from the saved seed. |
| A target box is missing or displaced | Invisible/ambiguous target or grounding failure | Inspect the clean pre-action image, then regenerate with a clearer task or another grounding backend. |
| Later images disagree with actions | A failed or inaccurate image transition | Regenerate from the saved seed. The main loop stops on render failure. |
| Index and directories disagree | A process stopped between metadata updates | Run `scripts/maintain/check_integrity.py` to locate broken links and incomplete records. |

To retry an existing task, use `python cli.py expand --seed-id <id> --task "<original task>"
--skip-dedup`. This creates a new trajectory and preserves the partial run for inspection.

Image editing runs serially within a trajectory. Parallelism is across independent
trajectories. Optional local detection models have separate requirements; keep their model
files and local backend configuration outside source control.

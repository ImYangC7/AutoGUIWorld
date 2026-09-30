# Ubuntu scene sampling

Ubuntu uses the GNOME application pool in `autogui/state/desktop_linux.py` and the shared
window sampler in `autogui/state/environment.py`.

The sampled state determines window count, layout, login state, desktop clutter, and system
indicators. `sample_windows` chooses applications from the pool, avoids redundant office
suite combinations, and assigns content and positions. The first window is the foreground
surface; subsequent windows form its background.

After sampling windows, `sample_dock` chooses launcher favorites and adds running indicators
for applications present in the scene. This keeps the dock and windows consistent. Browser
windows use the shared website catalog.

The complete scene is described and rendered before task generation. The task generator
then uses the saved scene and Ubuntu feature descriptions to propose interactions.

```bash
python cli.py seed --os ubuntu2404 --seed 42
python cli.py expand --seed-id seed_001 --auto-tasks 3
```

Replace `seed_001` with the ID returned by the first command. Backend and optional grounding
services must be configured as described in the project README.

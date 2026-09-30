# Release checks

Run these checks in a clean checkout before publishing:

```bash
python -m pip install -r requirements-dev.txt
python scripts/check_release.py
ruff check .
python -m unittest discover -s tests -v
```

The release scan checks tracked and non-ignored source files for provider connection fields,
credential-like literals, personal absolute paths, private network hosts, non-synthetic email
addresses, and generated files. It prints locations and categories without matched values.
Keyboard action keys, dictionary keys, localhost grounding endpoints, and intentional public
project identities are valid source content.

Preset scene identities are intentional image-generation content. Their reviewed email
matches are recorded in `.release-fixtures.json` using a file digest. Changing the source
requires review again. This classification never suppresses connection or credential findings.

Run `python scripts/check_release.py --history` to scan reachable Git commits as well.
Removing a value from the working tree does not remove copies in Git history. Previously
published credentials require service-side revocation; history changes are a separate release
decision.

The codebase includes generated GUI illustrations and application-view templates. Automated
scanning checks file contents and image metadata; visible illustration text needs manual
review. Real provider inference and GPU grounding require separately configured backends.

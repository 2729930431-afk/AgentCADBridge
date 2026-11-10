# CADBridge development rules

Read [the bundled development Skill](skills/cad-develop/SKILL.md) before changing runtime behavior or adding capabilities. It is the canonical architecture rule and is distributed inside the CAD plugin.

Every feature must preserve the upstream shared multi-CAD adaptation structure. Use one shared core and compatible COM backend with profile configuration for AutoCAD, ZWCAD, GstarCAD and BricsCAD. Vendor-specific functionality must be isolated behind backend contracts/capability gates with explicit compatibility limits. ZWCAD-only live testing must never be described as all-CAD validation.

Keep Agent adapters thin. Prefer background preview to computer control. Automated tests must not create CAD documents; explicit live acceptance uses one owned drawing with finally cleanup. Never publish local runtime state or user drawings.

Run `python -m pytest -q`, `python -m ruff check cadbridge scripts tests` and `python scripts/inventory.py --check` with the project environment before release. Refresh `uv.lock` and `requirements-lock.txt` after dependency changes.

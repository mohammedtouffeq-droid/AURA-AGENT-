# AURA — Coding & Game Development Workspace

AURA is an early-stage coding and game-development assistant. Its core local workflows are:

- **Coding:** CoderX generates a workspace file, checks Python syntax, and runs a validation command.
- **Game development:** the Godot project builder creates a starter project; the trainer can run Godot headlessly to validate it.
- **Optional media:** image and video generation remain available, but are not automatically included in coding or game runs.

The master pipeline asks for **Allow once** before it runs a workflow. The approval prompt describes the requested workspace writes and local validation; generated code is executed locally and is not isolated. A denied or expired request does not dispatch an engine. Pipeline jobs do not collect system telemetry unless the `system` domain is explicitly selected. Generated output files are restricted to their respective AURA workspaces.

## Run locally

Start the web workspace from the repository root:

```powershell
python aura_web.py
```

By default, the server listens on `http://127.0.0.1:5050`. AURA can scaffold a Godot project without the engine; headless validation requires a compatible Godot binary available to `godot_engine_manager.py`.

Run the focused offline pipeline tests with:

```powershell
python -m unittest test_aura_pipeline -v
```

## Integration status

The repository declares 63 upstream engine entries in `.gitmodules` and keeps descriptive metadata in `aura_agent.py`. In the current checkout, the engine audit reports those submodules as uninitialized. Listing or cloning an upstream project does **not** make its code callable by AURA; those entries are not all wired into the product pipeline. `engine_auditor.py` checks submodule metadata and local checkout state only—it does not test runtime integration or compatibility.

The current master pipeline connects the CoderX and Godot paths. Media is an explicit optional capability. Other registered engines, desktop automation, and broad SaaS integrations should be treated as separate or experimental until they have an implemented adapter, an end-to-end test, and an approval flow appropriate to their effects.

## Next priorities

1. Route all file, shell, browser, and device-changing entry points through the same user-visible consent gate; the new gate currently covers master-pipeline runs.
2. Replace the static engine catalog with truthful runtime capability checks, then integrate only a small, tested coding/game toolchain.
3. Add end-to-end workflow tests that exercise code generation, Godot validation, and artifact delivery without relying on fixed local machine state.

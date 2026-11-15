# AURA — Coding & Game Development Workspace

AURA is an early-stage coding and game-development assistant. Its core local workflows are:

- **Coding:** CoderX generates a workspace file, checks Python syntax, and runs a validation command.
- **Game development:** the Godot project builder creates a starter project; the trainer can run Godot headlessly to validate it.
- **Optional media:** image and video generation remain available, but are not automatically included in coding or game runs.

The master pipeline asks for **Allow once** before it runs a workflow. The approval prompt describes the requested workspace writes and local validation; generated code is executed locally and is not isolated. A denied or expired request does not dispatch an engine. Pipeline jobs do not collect system telemetry unless the `system` domain is explicitly selected. Generated output files are restricted to their respective AURA workspaces.

## Model settings

The signed-in workspace lets each user choose a supported Google Gemini model or a locally installed Ollama model. Gemini uses the server's `GEMINI_API_KEY`; Ollama connects only to `http://127.0.0.1:11434`. Provider/model preferences are stored per user, and credentials are not accepted or returned by the settings API. Codex and GitHub Copilot are not model providers in this build.

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

## BharatCode Top-10 Super-Suite (All 10 Judged Winners Integrated)

`aura_bharatcode_top10.py` natively integrates the core capabilities of all 10 judged winners from the BharatCode Build League into a unified, 100% deterministic and verified execution suite (`/api/bharatcode10/overview`, `/api/bharatcode10/execute`, `/api/bharatcode10/superpipeline`):

1. **#1 TRINETRA (`trinetra`)** — Sovereign Cyber Defense, IOC/SIEM extraction, MITRE ATT&CK + CERT-In Playbooks, Indian Statutory Legal Intelligence (`BNS 2023`, `IT Act 2000`, `DPDP Act 2023`), and Explainable AI (XAI) Deepfake Forensics.
2. **#2 BharatCode IDE Agent (`bharatcode_ide`)** — Autonomous IDE Code Agent, Python/JS AST bug & anti-pattern detector, unified diff refactorer, and unit test synthesizer.
3. **#3 GitKitty (`gitkitty`)** — Automated codebase architecture tour and interactive Git recovery simulator (`rebase_conflict`, `detached_head`, `accidental_hard_reset`).
4. **#4 Ashby Multi-ATS Job Radar (`ashby_job_radar`)** — Multi-ATS (`Ashby`, `Greenhouse`, `Lever`, `Workday`) engineering role radar with deterministic `0-100` skill-match scoring.
5. **#5 LearnOS (`learnos`)** — Student Learning OS with 4-stage mastery roadmaps, SM-2 spaced-repetition flashcards, and coding arena challenges.
6. **#6 Form2Fact (`form2fact`)** — Evidence-first institutional document cross-verification and discrepancy audit engine.
7. **#7 OrvynAI (`orvyn_interview`)** — Adaptive technical interviewer, STAR + Systems Design rubric evaluator, and resume-to-role gap analyzer.
8. **#8 Spare-GPU (`spare_gpu`)** — Idle-capacity hardware telemetry gate and automated background repository maintenance chore scheduler.
9. **#9 PayGuard AI (`payguard_upi`)** — Explainable UPI QR (`upi://pay?...`) decoder, collect-request scam shield, and itemized bill risk auditor.
10. **#10 Anonymous-Campus (`anonymous_campus`)** — Zero-identity PII-scrubbed feedback vault with cryptographic SHA-256 receipts and issue routing.

## Deep-Space Scroll-Driven 3D UI

`index.html` features an interactive **Deep-Space Scroll-Driven 3D Starfield & Orbital Parallax Engine** (`#spaceCanvas`, `#spaceOrbitalRingOverlay`, `#spaceScrollProgressBar`, `#spaceWarpBadge`) that responds dynamically to scroll velocity and wheel delta across the chat stream and command hubs.

## Integration status

The repository declares 63 upstream engine entries in `.gitmodules` and keeps descriptive metadata in `aura_agent.py`. In the current checkout, the engine audit reports those submodules as uninitialized. Listing or cloning an upstream project does **not** make its code callable by AURA; those entries are not all wired into the product pipeline. `engine_auditor.py` checks submodule metadata and local checkout state only—it does not test runtime integration or compatibility.

The current master pipeline connects the CoderX and Godot paths. Media is an explicit optional capability. Other registered engines, desktop automation, and broad SaaS integrations should be treated as separate or experimental until they have an implemented adapter, an end-to-end test, and an approval flow appropriate to their effects.

## Next priorities

1. Route every legacy file, shell, browser, and device-changing entry point through the same user-visible consent gate; the pipeline and OS-controller gates do not cover every direct API/tool route yet.
2. Replace the static engine catalog with truthful runtime capability checks, then integrate only a small, tested coding/game toolchain.
3. Add end-to-end workflow tests that exercise code generation, Godot validation, and artifact delivery without relying on fixed local machine state.

# AURA AGENT

AURA is an early-stage project exploring a local, human-supervised AI automation system. The repository currently contains a Gemini-backed Python CLI prototype, a kinetic UI preview, a static local preview server, and 32 upstream Git submodule pointers. It is not a trained language model, a fully integrated agent platform, or a verified production system.

## What is in the repository

- `.gitmodules` declares 32 upstream repositories under `engines/`. Each submodule entry is a pinned Git pointer; it does not mean that the source is downloaded, imported, or integrated.
- `aura_brain.py` sends requests to the configured Gemini API and declares eight Python tools for shell execution, browser launch, webpage reading, file read/write, SQLite memory, and screenshots.
- `aura_chat.py` is a local terminal loop around `AuraBrain`. It now reports whether a key is configured, but the network connection is only tested when the first request runs.
- `aura_memory.db` is created locally by the Python brain and is ignored by Git.
- `index.html` is a self-contained kinetic interface preview. It does not call Gemini, connect to the CLI, read the SQLite database, or execute the prompts it displays.
- `aura_web.py` serves that page on loopback for preview only. Its chat/settings API routes are disabled; use `aura_chat.py` for the Gemini CLI.
- `engine_auditor.py` reports declared submodule metadata and local checkout status. It does not test compatibility, safety, or runtime integration.
- `setup_engines.py` lists registry entries by default. Source downloads require an explicit `--init` selection or `--all`.

## Important tool-safety limitation

The current Python CLI is not safe for unattended automation. When Gemini requests a registered function, `aura_brain.py` executes it immediately. In particular, the shell tool accepts arbitrary PowerShell commands, file writes are not restricted to a workspace, and webpage fetching has no URL allow-list. `aura_settings.py` and `aura_config.json` do not currently enforce approval gates in the brain. Do not expose this CLI as a web service or run it with sensitive access until a permission system, isolation, and user approvals are implemented and tested.

The browser UI is disconnected and makes no network calls. Its controls only affect the local preview, while prompt examples and the composer are demonstrations. A real web client needs an authenticated local API, scoped tool permissions, explicit approvals, request cancellation, and protection against browser prompt injection before it should connect to the CLI.

## Getting started

Requirements: Python 3.10 or newer. The core client uses Python's standard library. The Gemini API requires a key in a local `.env` file next to `aura_brain.py`:

    GEMINI_API_KEY=your_key_here

Keep `.env` private; it is ignored by Git. Starting the CLI creates/opens `aura_memory.db` and may send prompts to Google's Gemini API. The model and connection have not been verified by this documentation.

From the repository root:

    python aura_chat.py
    python aura_agent.py --json
    python setup_engines.py --list
    python -B -m unittest discover -v

The UI preview can be opened directly as `index.html`, or served locally with `python aura_web.py`. The server hosts only the static page; it does not expose chat or settings APIs.

To download only selected upstream source:

    python setup_engines.py --init open-interpreter

To download all 32 repositories (which may use substantial time, bandwidth, and disk):

    python setup_engines.py --all

Downloaded upstream code is not executed or verified by Aura. Review the pinned commit, dependencies, maintenance, security posture, license, and redistribution obligations before using or shipping any upstream project.

## Registry inventory

The declared repositories span desktop automation, browser automation, coding assistance, orchestration, model interfaces, retrieval and storage, integrations, durable workflows, inference, and observability. Exact URLs and pinned commits are in `.gitmodules` and the parent Git tree. `REPOSITORIES_PROOF.md` documents the limits of this inventory.

## Engineering direction

Build one narrow, reviewable vertical slice at a time:

1. Define supported tasks, trust boundaries, and prohibited actions.
2. Add durable task state with cancellation, retries, and audit events.
3. Use a typed model adapter and keep provider credentials out of the browser.
4. Add low-risk integrations with least privilege, dry-run previews, idempotency, and approvals for external changes.
5. Isolate browser workflows and evaluate prompt injection, secrets, downloads, and destructive actions.
6. Add evaluations for task completion, correctness, safe refusal, latency, and cost.
7. Add privacy controls, redaction, retention limits, and opt-out before telemetry.

Combining repositories does not train a model or automatically combine capabilities. Model quality requires a suitable base model, data rights, curated data, compute, evaluation, and iteration. This project makes no claim of guaranteed expertise, 95% automation, reliability, or superiority over other assistants.

## Upstream identity and licensing

Aura branding applies only to Aura-authored material. Upstream project names, ownership, notices, trademarks, and license terms remain with their respective maintainers. This repository does not claim to own or relicense submodules. Review each pinned revision's license and notices before packaging, modifying, or redistributing upstream source.

# AURA AGENT

Aura is an early-stage project for exploring a safe, human-supervised AI automation system. This repository currently contains 32 upstream Git submodule pointers and two small Python utilities. It is not a trained language model, a functioning autonomous agent, or a verified integration of the listed projects.

## What is in this repository today

- .gitmodules declares 32 upstream projects beneath engines/.
- The parent Git tree pins one commit for each submodule; a pointer is not the upstream source itself.
- aura_agent.py reports local submodule states. It does not import or run engine code, count source files, call a model, or execute user goals.
- setup_engines.py lists metadata by default. It initializes source only when you explicitly select modules with --init or request all with --all.
- test_aura_agent.py contains offline tests for registry parsing and status reporting.

The project currently has no model weights, training pipeline, model adapter, task planner, durable job worker, browser or desktop runtime, tool permissions system, or end-to-end integration tests.

## Getting started

Requirements: Python 3.10+ and Git. No Python package installation is needed.

From an Aura checkout:

    python setup_engines.py --list
    python aura_agent.py
    python -m unittest -v test_aura_agent.py

The default setup command only lists the registry. To initialize selected source:

    python setup_engines.py --init open-interpreter

To initialize every registered submodule:

    python setup_engines.py --all

That operation downloads 32 repositories and can use substantial time, bandwidth, and disk space. Downloaded source is not executed or verified by Aura. Review each selected project, its pinned commit, dependencies, security posture, and license before use or redistribution.

## Registry inventory

The upstream entries cover desktop automation (Open Interpreter); browser automation (Browser Use, Playwright Python, Skyvern, Stagehand); coding assistance (Aider, OpenHands); orchestration (CrewAI, LangGraph, Microsoft Agent Framework, OpenAI Agents SDK, Semantic Kernel); model interfaces (LiteLLM, PydanticAI, DSPy); retrieval/storage (Haystack, LlamaIndex, Qdrant, pgvector); integrations (Dify, n8n, Activepieces, Composio, MCP Python SDK); durable workflows (Temporal, Prefect); inference (llama.cpp, Ollama, Transformers, vLLM); and observability/evaluation (Langfuse, Arize Phoenix).

See .gitmodules and REPOSITORIES_PROOF.md for exact URLs and what the registry does and does not prove.

## Engineering direction

Build one small, reviewable vertical slice before combining more frameworks:

1. Define Aura's users, supported tasks, trust boundaries, and prohibited actions.
2. Implement durable task state with cancellation, retries, and audit events.
3. Add one model adapter behind a typed interface; choose local or hosted inference based on hardware, privacy, latency, and cost.
4. Add one low-risk tool integration with least-privilege credentials, dry-run preview, idempotency, and human approval before external changes.
5. Add isolated browser workflows only after threat modeling prompt injection, secrets, downloads, and destructive actions.
6. Create evaluations for task success, factuality, tool correctness, refusal behavior, latency, and cost; gate releases on measured results.
7. Add telemetry with privacy controls, redaction, retention limits, and a way to disable collection.

Adding repositories does not train a model or automatically combine their capabilities. Model quality depends on a suitable base model, data rights and curation, compute, evaluation, and iteration. This repository makes no speed, capability, reliability, or competitor-beating claim.

## Upstream identity and licensing

Aura branding applies to Aura-authored documentation and utilities. Upstream names, ownership, notices, trademarks, and licenses remain with their maintainers. This repository does not claim to own or relicense submodules. Review each pinned commit's license, notices, and redistribution obligations before packaging or distributing an Aura product; terms can differ between projects.


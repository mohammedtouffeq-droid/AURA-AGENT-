# Upstream repository inventory and verification limits

## What the parent repository proves

The `.gitmodules` file declares 32 upstream repository URLs under `engines/`, and the parent Git tree pins a commit for each submodule. These are Git links to specific upstream commits. A pointer does not prove that a checkout exists locally, that the source runs, that it has been integrated into AURA, or that the projects are mutually compatible.

Use `python aura_agent.py --json` to inspect the declared entries and the current local checkout state. The audit reads Git metadata only; it does not import, execute, download, or security-review upstream code. `python setup_engines.py --list` is metadata-only. Network downloads happen only after explicit `--init NAME_OR_PATH` or `--all`.

## Declared projects

The upstream URLs are maintained in `.gitmodules`. Current categories include desktop and browser automation, coding assistants, agent orchestration, model routing, retrieval and databases, workflow tools, inference engines, and observability/evaluation systems. The list is a research inventory, not an integration claim or a ranking of the world's best tools.

No star count, source-file count, compatibility claim, or blanket license claim is asserted here. Repository popularity changes over time, and license/notice obligations must be verified at each pinned revision before distribution.

## Attribution and reuse

Keep upstream project identity, copyrights, notices, trademarks, and license terms intact when using or redistributing upstream source. Aura branding applies to Aura-authored code and documentation only. Review every dependency and pinned revision independently; licenses and attribution requirements may differ.

## Current product boundary

AURA's Python prototype and its static kinetic UI preview are separate. `aura_web.py` serves the preview page only; it does not expose chat/settings endpoints or connect to Gemini, the terminal process, browser automation, or SQLite. The Python CLI currently executes a model-requested tool call without a separate approval prompt, so it must not be described as unattended-safe or exposed as a browser service.

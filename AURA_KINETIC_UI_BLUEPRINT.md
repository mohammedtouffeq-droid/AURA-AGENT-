# AURA Kinetic UI — design and integration boundary

## Current implementation

`index.html` is a responsive, self-contained visual preview with a kinetic orb, restrained particle animation, glass panels, responsive layout, keyboard-accessible drawer, local appearance preferences, prompt examples, and a copyable CLI command. It does not send prompts or connect to `aura_chat.py`, Gemini, SQLite, browser automation, or PowerShell. `aura_web.py` serves the static preview only; its former chat/settings HTTP routes are disabled. Its status labels describe the configured model and unverified CLI state; they do not claim a live browser connection.

The UI should remain clearly marked as a preview until a real service exists. Never place a Gemini key in frontend JavaScript or local storage.

## Visual direction

- Dark graphite surfaces, restrained cyan/violet accents, legible type, deliberate spacing, and subtle glass treatment.
- The animated orb is a brand element, not a live visualization of model state.
- Animation respects `prefers-reduced-motion`, has a local pause control, and stays secondary to readable content.
- Layout supports narrow mobile widths, visible focus, keyboard navigation, descriptive button labels, and scalable system fonts.
- Local theme, motion, and particle-speed settings affect this page only; they do not edit `aura_config.json`.

## Before connecting a browser UI to the CLI

The current brain executes model-requested PowerShell and file-write tools immediately, uses unrestricted local file paths, and fetches arbitrary URLs. The `ask_first` configuration is not enforced by the brain. Do not add a browser endpoint that exposes these tools until all of the following have a reviewed implementation:

1. A loopback-only service with authenticated, short-lived sessions and CSRF/origin protections.
2. Explicit user approval for every command, write, download, external navigation, or other side effect; deny by default.
3. Workspace-scoped filesystem access, command allow-listing or a disposable isolated environment, strict timeouts, and output limits.
4. URL/network policy to prevent local-network and metadata-service access, redirect bypass, and unbounded downloads.
5. Visible activity, cancellation, audit history with secret redaction, and clear treatment of untrusted webpage content.
6. Automated tests for denial paths, path traversal, malicious links, timeouts, process termination, and persistence failures.

## Release checks

- Keep all current claims tied to verified implementation.
- Run Python unit tests and Python compilation checks.
- Extract the embedded JavaScript from `index.html` and run `node --check`.
- Test at mobile and desktop viewports, keyboard-only navigation, reduced motion, and large text in a real browser before calling the interface visually verified.
- Do not call the CLI or external APIs as part of a UI preview check.

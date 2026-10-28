# Aura capability roadmap and release gates

## Product boundary

Aura is an early-stage project. Its current implementation audits a Git submodule registry and offers explicit source initialization. It does not yet contain a model, planner, desktop controller, browser controller, hosting service, or general task execution runtime.

The long-term idea—helping with code, websites, games, videos, files, and publishing—must be delivered as individually enabled capabilities. “Can access anything on the laptop or internet” is not a safe or testable release criterion. Every tool needs a named permission scope, visible preview, cancellation, audit trail, and recovery path. Irreversible or externally visible operations require human confirmation.

## Proposed engineering slices

### Slice 0: Repository integrity (current)

- Keep upstream repositories as pinned submodule references and describe them as candidates.
- Audit the registry without importing or executing upstream code.
- Keep downloads opt-in and test that list mode never invokes Git.
- Run offline unit tests in CI.

### Slice 1: One model-backed, read-only task

- Select one target use case and one model provider after deciding privacy, hardware, latency, and cost needs.
- Define a typed request/response interface; keep provider credentials outside source control.
- Add a task record with stable ID, state, timestamps, cancellation, timeout, and structured errors.
- Start with read-only operations in a dedicated project folder. No unrestricted shell, browser writes, or desktop input.

### Slice 2: Bounded project-file coding

- Add a capability API that can list/read files only within an explicitly selected workspace.
- Generate a patch first; show the diff and require approval before applying it.
- Reject paths outside the workspace, protect secrets and hidden configuration, and keep an undoable change log.
- Run formatters and tests in an isolated process with resource limits. Never treat model output as trusted shell syntax.

### Slice 3: Browser and desktop tasks

- Start with one browser workflow on an allow-listed site and a separate browser profile.
- Treat page content as untrusted input; do not follow webpage instructions that conflict with the user's task or system policy.
- Use screenshots and action previews. Require approval before submitting forms, sending messages, purchasing, deleting, publishing, or changing account settings.
- Add desktop control only with explicit per-session opt-in, a visible target window, an emergency stop, and a strict action log.

### Slice 4: Durable background execution

- If tasks must continue after the laptop shuts down, deploy a server-side worker and durable queue; a local process cannot run while its only computer is powered off.
- Add authentication, per-user isolation, encrypted secret storage, tenant quotas, idempotent retries, monitoring, backups, cancellation, and incident response.
- Start with a narrow set of low-impact tasks. No unattended account access or irreversible actions.

### Slice 5: Broader production capability

- Add tools only when an evaluated workflow needs them. Avoid loading many overlapping frameworks into one runtime.
- Build a versioned evaluation set for task success, correctness, unsafe-action rate, recovery, latency, and cost.
- Add localization, accessibility, data export/deletion, support operations, and market-specific privacy/legal review before global availability.
- Publish measurable support boundaries and limitations. Do not advertise a capability based only on a repository being listed.

## Release gates

A capability is not supported until isolated tests pass, failures are recoverable, permissions are enforced, logs contain no secrets, and representative evaluation tasks meet a published threshold. For external actions, test that approval gates cannot be bypassed. Measure p50/p95 latency and cost per completed task; do not promise a fixed success rate without results.

Use the NIST AI Risk Management Framework and its Generative AI Profile as governance references, and map application threats to the current OWASP Top 10 for LLM Applications. Legal requirements vary by launch market and product use; obtain qualified review before release. These references are engineering guides, not a compliance certification.

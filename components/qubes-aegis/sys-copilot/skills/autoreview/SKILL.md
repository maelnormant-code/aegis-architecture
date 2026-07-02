---
name: autoreview
description: "Pre-commit code review for Qubes Aegis: delegate review of code changes to sys-ai before finalizing."
---

# Auto Review

Run a structured review closeout check using `sys-ai`. This is code review, not Guardian `auto_review` approval routing.

For user-visible behavior, pair autoreview with behavior validation. Autoreview is source-aware and judges the change bundle; behavior validation is source-blind and judges the running product against a behavior contract.

Use when:
- The user asks for a review of local changes.
- After non-trivial code edits in any Aegis component, before committing or finalizing.

## Contract

- Treat review output as advisory.
- Verify every finding by reading the real code path and adjacent files.
- Reject unrealistic edge cases, speculative risks, broad rewrites, and fixes that over-complicate the Qubes architecture.
- Prefer small fixes at the right ownership boundary (e.g., `guest`, `sys-ai`, `sys-copilot`); no refactoring unless it clearly improves security.
- Security perspective is always included. Report security findings only when the change creates a concrete, actionable risk (e.g., bypassing `qrexec` policies, opening unrestricted network ports, missing sanitization).
- Do not invoke built-in review from inside the review itself. One pass, one validation, and stop.
- Stop as soon as the review returns no accepted/actionable findings.

## Scope Governor

Autoreview is a closeout gate, not permission to rewrite the task.

Before patching a finding, classify it:
- **In-scope blocker**: the finding is introduced by the current diff and can be fixed without changing the task's contract.
- **Follow-up**: the finding is real but belongs to an adjacent bug class or broader hardening track.
- **Stop-and-escalate**: the finding requires a new `qrexec` policy, a different VM boundary, or a design choice outside the original request.

## Execution

To execute this, `sys-copilot` should package the `git diff` or changed files and send a query to `sys-ai` asking for a structured code review based on these rules.

1. Gather changes: `git diff` or read modified files.
2. Delegate to `sys-ai` using the `handoff` skill or direct inference request.
3. Present the findings clearly to the user and ask for approval to patch in-scope blockers.

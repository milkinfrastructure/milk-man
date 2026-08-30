---
name: milk-system
description: Work on the Milk Carton Rust data plane or Milk Man agentic harness. Use for local implementation, testing, and review of Milk tasks.
license: MIT
---

# Milk system

Read the admitted `milk.local-agent-task.v1` document before changing files.
Verify every repository's current commit and working status. Stop if a source
checkout is dirty or its commit differs from the task.

## Boundaries

- Milk Carton owns operator-issued-key authentication, the OpenAI-compatible
  Rust request path, sampling, route selection, fallback, and signed route
  enforcement.
- Milk Man owns local coding iteration and admitted deterministic summary,
  classifier, readiness, eval-generation, and unsigned-proposal job calls.
- The checked-in deterministic engine behind argument-free
  `milk_jobs.reconcile()` is an implementation detail, not a third product or
  service.
- Durable state belongs in local or qualified S3-compatible object storage.
  Never store credentials or signing keys there.
- Do not add a database, queue, resident manager, scheduler service, generic
  provider layer, or Rust agent framework.
- Do not read browser state, memory folders, Keychain, SSH configuration,
  `.env` files, production traffic, or raw credentials.
- The configured agent model may run only within the task's model budget. A
  fixed Milk job may run only when `milk_job_call` is admitted. Do not make a
  Milk provider call, push, deploy to cloud, write remote objects, prepare a
  route, sign, or publish unless the task separately enables that exact action.
  A local coding task normally enables none of them.
- Never pass a model-provided command, path, configuration, scope, budget,
  credential, or write target to a Milk job.
- Never interpret a passing local gate as a live deployment result.

## Fixed local gates

Only use the gate selected by the task:

- `milk-carton:test`: `cargo +1.95.0 test --locked --offline --workspace --all-targets`
- `milk-man:check`: `npm run check`

Run from the named repository root. Do not alter a gate command or replace a
failure with a narrower test. Return the exit code, duration, bounded failure
tail, and diff. Do not include environment values or file contents unrelated
to the task.

## Completion

Finish only when every acceptance item and fixed gate passes. Leave a clean,
reviewable diff. Do not commit or push unless the task separately allows it.
Use supplemental refinement only for a small repeated lesson; never refine
limits, permissions, credentials, gate commands, or route policy.

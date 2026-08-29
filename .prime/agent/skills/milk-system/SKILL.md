---
name: milk-system
description: Work on the Milk Rust gateway, deterministic object-store harness, or Milk Churn fork. Use for local implementation, testing, and review of Milk tasks.
license: MIT
---

# Milk system

Read the admitted `milk.local-agent-task.v1` document before changing files.
Verify every repository's current commit and working status. Stop if a source
checkout is dirty or its commit differs from the task.

## Boundaries

- `milk-gateway` owns the OpenAI-compatible Rust request path, sampling, route
  selection, and signed route enforcement.
- `milk-harness` owns deterministic finite S3-compatible summary, classifier,
  readiness, eval-generation, and unsigned proposal jobs.
- Milk Churn owns local coding iteration only.
- Do not add a database, queue, resident manager, scheduler, planner, generic
  provider layer, or Rust agent framework.
- Do not read browser state, memory folders, Keychain, SSH configuration,
  `.env` files, production traffic, or raw credentials.
- The configured agent model may run only within the task's model budget. Do
  not make separate Milk provider calls, push, deploy to cloud, write remote
  objects, sign routes, or publish routes unless the task explicitly enables
  that exact action. A local task normally enables none of them.
- Never interpret a passing local gate as a live deployment result.

## Fixed local gates

Only use the gate selected by the task:

- `milk-gateway:test`: `cargo +1.95.0 test --locked --workspace`
- `milk-harness:test`: `python3 -m unittest discover -s milk_harness -p 'test_*.py'`
- `milk-churn:check`: `npm run check`

Run from the named repository root. Do not alter a gate command or replace a
failure with a narrower test. Return the exit code, duration, bounded failure
tail, and diff. Do not include environment values or file contents unrelated
to the task.

## Completion

Finish only when every acceptance item and fixed gate passes. Leave a clean,
reviewable diff. Do not commit or push unless the task separately allows it.
Use supplemental refinement only for a small repeated lesson; never refine
limits, permissions, credentials, gate commands, or route policy.

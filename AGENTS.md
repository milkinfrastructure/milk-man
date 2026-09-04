# Milk Man repository policy

Read `goal_tracker.md` before changing code. Milk Man is an autonomous,
prompt-driven Bash agent for operating and improving models, compute, and the
Milk system. Milk Parlor is the separate Rust gateway.

- Treat the newest human objective as the task boundary. Continue through its
  necessary steps until complete or a specific external blocker is proven.
- Preserve Headlong's reasoning -> Bash -> result loop. Reuse existing jobs;
  when a task needs a missing capability, add or repair the smallest
  repository-owned script and make it reusable without changing the harness
  engine.
- Jobs select behavior through environment variables and report progress,
  results, status, and cleanup. Never print credentials or raw production
  traffic.
- Milk Man may deploy, operate, benchmark, tune, and stop resources when the
  task calls for it and the required environment is configured. Do not require
  a separate confirmation for each command or introduce hidden provider
  fallback.
- Implement and preserve one lightweight heartbeat in this repository. Idle
  checks use no model call, back off, inspect only changed state, and have one
  owner per task. Do not add a separate scheduler service, database, or queue.
- Preserve immutable object identity and conditional current pointers under
  `milk/v2/scopes/<scope_uuid>/`. Never write `milk/v1`.
- Keep model weights out of Git and lightweight runtime images. Reuse provider
  caches or volumes.
- Use the smallest direct check and one real smoke. Do not add fixture suites,
  broad unit-test scaffolding, generated reports, or compatibility code.
- Preserve Headlong's Apache-2.0 license and `vendor/headlong/UPSTREAM.md`.
- Preserve unrelated work. Stage named files only; never force-push or reset.

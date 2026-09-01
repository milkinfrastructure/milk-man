# Milk Man repository policy

Read `goal_tracker.md` before changing code. Milk Man is a local Bash
development harness and a deterministic one-shot jobs runtime. Milk Parlor is
the separate Rust gateway.

- Keep `bin/man` supervised and local-first. It may edit and commit locally;
  it does not push, deploy, sign routes, or receive production credentials.
- Keep `bin/milk` deterministic. Fixed code selects handlers and reviewed
  environment-variable names select object, inference, and GPU bindings.
- Production operation is one external invocation of `bin/milk operate --once`.
  Do not add a sleeping loop, tick, daemon, database, queue, resident manager,
  generic provider layer, or arbitrary command from configuration.
- Preserve immutable object identity and conditional current pointers under
  `milk/v2/scopes/<scope_uuid>/`. Never write `milk/v1`.
- Credentials stay in environment variables and enter only the job that needs
  them. Do not log secrets or raw production traffic.
- An idle run must make zero inference and provider calls.
- Use the smallest direct check and one end-to-end smoke. Do not add fixture
  suites, broad unit-test scaffolding, generated reports, or compatibility code.
- Preserve Headlong's Apache-2.0 license and `vendor/headlong/UPSTREAM.md`.
- Preserve unrelated work. Stage named files only; never force-push or reset.

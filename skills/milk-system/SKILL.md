---
name: milk-system
description: Work safely across the Milk Man and Milk Parlor repositories.
---

# Milk system

Use this skill for any Milk code change.

1. For a concrete task, inspect only its affected state and code. Read the
   relevant `goal_tracker.md` section only when asked to continue the plan.
2. Inspect each unknown in the narrow call path once, then act. Do not repeat an
   unchanged read, check, or poll.
3. Keep Milk Parlor a CPU-only Rust proxy: authentication, routing, exact
   asynchronous capture, and status only.
4. Keep orchestration in deterministic `milk` jobs. Development reasoning may
   propose or implement code but cannot sign or activate routes.
5. Store durable data beneath `milk/v2/scopes/<scope_uuid>/`; raw captures and
   versioned artifacts are immutable, while small `current.json` objects are
   conditional pointers.
6. Select object store, inference, Modal, and Baseten bindings only through the
   reviewed environment-variable contract. Never print secret values.
7. Treat Baseten and Modal as separate named jobs. Select exactly one from the
   system prompt or operator task; never turn one provider's failure into a call
   to the other provider.
8. Make one bounded change, run the narrowest real check, inspect the diff, and
   leave a reviewable commit only when the human task permits it.

Do not add Prime, Exo, Docker to the local harness, a database, queue, tick
loop, standing GPU, generic provider abstraction, compatibility layer, broad
fixture suite, or product budget system.

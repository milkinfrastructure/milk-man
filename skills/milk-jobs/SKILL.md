---
name: milk-jobs
description: Invoke reviewed deterministic Milk jobs from the local harness.
---

# Milk jobs

Use only the public `milk` CLI. Begin with `milk status`; invoke a named job
with `milk run <name>` or one reconciliation with `milk operate --once`.

- Treat stdout as the single `milk.job-result.v2` JSON result and stderr as
  diagnostics.
- A model may choose only a reviewed job name. The job definition owns its
  handler, environment bindings, object prefixes, prompt, timeout, and teardown.
- Never pass credentials, provider accounts, object prefixes, images, GPU
  types, model revisions, signing keys, or shell commands as model arguments.
- An `idle` result is successful and must not be converted into polling.
- On an ambiguous provider result, run the fixed reconciliation job. Do not
  retry creation or select a fallback until the first identity is resolved.
- Before reporting success, inspect the returned artifact keys and digests and
  the authoritative provider or object-store state appropriate to the job.

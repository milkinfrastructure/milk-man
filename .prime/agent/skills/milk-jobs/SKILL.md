---
name: milk-jobs
description: Run one deterministic Milk summary, readiness, eval-generation, validation, score, and route-proposal reconciliation pass. Use when Milk traffic in object storage needs bounded processing.
license: MIT
---

# Milk jobs

The operator must set the exact Milk Man revision and one absolute config path:

- `MILK_MAN_REVISION`: the 40-character commit for the running Milk Man checkout.
- `MILK_RUN_ONCE_CONFIG`: the admitted run configuration.

Run the fixed reconciliation call:

```python
report = await milk_jobs.reconcile()
```

The call accepts no command, path, provider, signing, publication, or routing
arguments. It returns the parsed
`milk.run-once-report.v2` report. Strict `artifact_refs` are derived from the
admitted config and fixed job children; model-authored keys are rejected. It
never activates or signs a route.

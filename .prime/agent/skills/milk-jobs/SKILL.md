---
name: milk-jobs
description: Run one deterministic Milk summary, readiness, eval-generation, and route-proposal reconciliation pass through the operator-configured Milk Harness. Use when Milk traffic in object storage needs bounded processing.
license: MIT
---

# Milk jobs

The operator must set both absolute paths before starting Milk Man:

- `MILK_HARNESS_ROOT`: the pinned Milk Harness checkout.
- `MILK_RUN_ONCE_CONFIG`: the admitted run configuration.

Run the fixed reconciliation call:

```python
report = await milk_jobs.reconcile()
```

`await milk_jobs()` is equivalent. The call accepts no command, path, provider,
signing, publication, or routing arguments. It returns the parsed
`milk.run-once-report.v2` report. Strict `artifact_refs` are derived from the
admitted config and fixed job children; model-authored keys are rejected. It
never activates or signs a route.

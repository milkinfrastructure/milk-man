---
name: milk-jobs
description: Discover and run environment-configured Milk jobs.
---

# Milk jobs

When the job name is known, use `milk jobs <name>` to read only its actions and
environment names. Use `milk jobs` for initial discovery. Read existing progress
with `milk status`. Run a job with
`milk run <name>`; executable jobs may also expose `status` and `stop` actions.

For long commands, use `background /absolute/private/run-dir -- bin/milk run NAME`,
then `man heartbeat wait -- background /absolute/private/run-dir status` and yield.
The detached command survives a heartbeat restart. Reusing the directory only
reads its saved run; it never launches again. Status returns PID and private log
paths, not their contents. Inspect the exit receipt and job result before retrying
with an intentionally new directory. Keep credentials in environment variables.

- Treat stdout as the single `milk.job-result.v2` JSON result and stderr as
  diagnostics.
- Reuse job scripts. Add or adapt a repository executable and its catalog entry
  when the task needs a missing capability; do not extend the harness engine.
- Job definitions identify environment names; scripts resolve their values.
  Configure the model, GPU, and inference settings needed for the objective.
  Keep credentials in environment variables, never prompts or printed output.
- Baseten and Modal are separate jobs. Use the selected provider; do not
  silently fall back to another provider.
- An `idle` result is successful. If the task requires a later check, register
  a read-only heartbeat watch and yield rather than repeatedly calling a model.
- On an ambiguous provider result, run that provider's fixed reconciliation
  job. Do not retry creation or invoke another provider until the first identity
  is resolved.
- Before reporting success, inspect the returned artifact keys and digests and
  the authoritative provider or object-store state appropriate to the job.

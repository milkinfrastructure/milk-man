# Milk Man

Follow the most recent human task; it is authoritative. Use current files
and only the relevant part of the active goal; locate it with `rg` instead of
reading the whole tracker. Reuse successful observations already recorded in
the trajectory. Read each required skill only once per trajectory:
`milk-system` before editing and `milk-jobs` before running a job. After at most
two read-only turns, make the smallest useful change, finish, or report one
precise blocker.

Use the local shell. Preserve unrelated work, run one narrow check, and inspect
the diff. Never invent a trajectory approval parser, authority, configuration,
credentials, providers, or jobs. Use only commands and named jobs verified in
the repository. Do not
push, deploy, sign, or create paid resources unless the human task says so.

End every turn with exactly one fenced Bash block. Omit `FINAL` while work
remains. When finished, and only after requested checks and diff inspection,
set `FINAL` to a non-empty user-facing completion or blocker summary; never set
it to `0`, `1`, `true`, or `false`.

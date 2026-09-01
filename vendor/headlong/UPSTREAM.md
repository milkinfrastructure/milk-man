# Headlong attribution

This directory is a reduced derivative of
[`laude-institute/headlong`](https://github.com/laude-institute/headlong) at
commit `24e7ce77404357aef7b3fc87567e7be908258853`.

Milk Infrastructure changed the retained files to remove Docker, daemons,
messaging, UI, multi-provider branches, and deployment machinery. The retained
design is Headlong's Bash model loop: an OpenAI-compatible completion produces
one Bash block, the local shell executes it, and an append-only trajectory
feeds the next completion.

Headlong is licensed under Apache License 2.0. See `LICENSE` in this directory.

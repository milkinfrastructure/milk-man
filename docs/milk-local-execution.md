# Local Milk Man execution

Milk Man uses Prime Agent's source runner directly. There is no Milk daemon,
planner, scheduler, or wrapper service.

## Build

```sh
npm ci
npm run check
```

Node 22.8 or newer and Python 3.11 or newer are required. Run from source with
`./prime-agent.sh`.

## Isolated configuration

Create a temporary owner-only configuration directory outside the target
repository. Copy `milk/models.example.json` to `models.json` there only when a
model-backed run is required. Supply `BASETEN_API_KEY` through the process
environment; never place its value in the task document, command line, or
repository.

Use `DO_NOT_TRACK=1`, `PI_SKIP_VERSION_CHECK=1`, and a task-specific session
directory. Load only the checked-in Milk skill:

```sh
DO_NOT_TRACK=1 \
PI_SKIP_VERSION_CHECK=1 \
PRIME_AGENT_CODING_AGENT_DIR=/absolute/private/config \
./prime-agent.sh \
  --cwd /absolute/disposable/worktree \
  --session-dir /absolute/private/sessions \
  --no-extensions \
  --no-skills \
  --skill /absolute/milk-man/.prime/agent/skills/milk-system/SKILL.md \
  --no-prompt-templates \
  --no-themes \
  --model milk-teacher/zai-org/GLM-5.3-Flash \
  --thinking low \
  --autonomous \
  --autonomous-gate "npm run check" \
  --autonomous-max-continuations 2 \
  --autonomous-max-turns 4 \
  --autonomous-max-tokens 20000 \
  --autonomous-timeout-ms 900000 \
  @/absolute/reviewed-task.json
```

The gate shown is only for a Milk Man worktree. Use the exact fixed command
listed by the Milk skill for a gateway or harness task. The operator chooses
the command from the admitted gate ID; the model does not construct it.

Prime Agent runs generated code with the user's permissions and is not a
security sandbox. Use a disposable trusted worktree. A production-grade broker
may later place that same command in a network-denied VM, but that is not a
reason to build another framework now.

## Result

A successful local run yields a diff and passing gate. It does not commit,
push, deploy to cloud, spend outside the declared model limit, write remote
objects, sign a route, or publish a route. Those remain explicit operator
actions.

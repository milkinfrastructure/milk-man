<p align="center">
  <img alt="Milk pixel carton" src="assets/milk/milk-carton.png" width="128">
</p>

<h3 align="center">
Milk Man
</h3>

<p align="center">
  Milk's local self-iterating agentic harness
</p>

<p align="center">
  <a href="docs/milk-man-transition.md">Milk system boundary</a> &bull;
  <a href="docs/local-proof-receipt.md">Local proof</a> &bull;
  <a href="packages/coding-agent/docs/index.md">Documentation</a> &bull;
  <a href="https://github.com/PrimeIntellect-ai/prime-agent">Upstream</a>
</p>

Milk Man is the Milk-maintained fork of
[Prime Agent](https://github.com/PrimeIntellect-ai/prime-agent), pinned initially
to commit `5b6c0e94e11a97fcfdd7a9fc9dc4f7acbda9c853`. It edits and tests trusted
`milk-man` and `milk-carton` checkouts, and runs admitted deterministic Milk jobs
through fixed Python calls. The executable remains `prime-agent` so upstream
updates stay reviewable and small.

Milk-specific code is limited to three Bash entrypoints, one deterministic job
skill, and documentation. Milk Carton is the Rust request and routing data
plane. Local or qualified S3-compatible object storage is durable system
memory; secrets and signing keys never enter it.
Existing Prime Agent goals, schedules, subagents, autonomous gates, and session
storage coordinate the work. A model may select an admitted job call, but it
cannot change that job's scope, configuration, budget, write target, or signing
boundary. Cloud deploys, paid calls, route signing, and route publication remain
separate operator actions unless the reviewed task explicitly admits the exact
action.

The hourly [`Milk Jobs Reconcile`](.github/workflows/milk-jobs.yml) workflow
runs the in-repository deterministic engine through the argument-free
`milk_jobs.reconcile()` wrapper. Its production and isolated mechanics profiles
use checked-in configs; object-store and teacher credentials come only from the
protected `milk-provider-jobs-prod` GitHub environment. The job may write
summary, readiness, eval, validation, score, and unsigned route-proposal
objects. It cannot sign or publish a route.

<p align="center">
  <a href="https://github.com/milkinfrastructure/milk-man/actions/workflows/ci.yml">
    <img src="https://github.com/milkinfrastructure/milk-man/actions/workflows/ci.yml/badge.svg" alt="CI" />
  </a>
  <a href="https://github.com/milkinfrastructure/milk-man/actions/workflows/build-binaries.yml">
    <img src="https://github.com/milkinfrastructure/milk-man/actions/workflows/build-binaries.yml/badge.svg" alt="Release" />
  </a>
  <a href="https://arxiv.org/abs/2608.23552">
    <img src="https://img.shields.io/badge/arXiv-2608.23552-b31b1b.svg" alt="arXiv" />
  </a>
</p>

Prime Agent is an open-source coding and research agent for general and long-running work. It is designed around two core abstractions:

- The **[Recursive Language Model (RLM)](https://www.primeintellect.ai/blog/rlm)** treats context as variables (*prompt-as-a-variable*) and tools like recursive subagents as function calls (*programmatic tool /sub-agent calling*) inside a persistent REPL.
- The **[Continual Harness](https://arxiv.org/abs/2605.09998)** stores supplemental prompts, memories, skill descriptions, and reusable subagent specifications as durable state that Prime Agent can refine through small, evidence-backed updates, local to the session by default.

Prime Agent combines a persistent Python control environment with durable harness state, so useful working context and reusable operating patterns can outlive a single chat window.

- **Everything is programmatic:** a persistent Python REPL is the built-in model tool; file operations, shell commands, tool use, subagents, and context management happen through code.
- **Subagents are built in:** `rlm(...)` spawns real child agents for parallel or background work and returns their results programmatically.
- **The harness can improve:** `/refine` reviews the current trajectory and can apply small, evidence-backed updates to supplemental harness state. It never rewrites the immutable base system prompt, and recorded snapshots support rollback.
- **Skills are executable:** skills are importable Python packages, and the built-in skill creator can turn recurring workflows into project or personal skills.
- **Sessions run in the background:** daemon-backed agents keep running when the terminal disconnects and can be reattached later.
- **Agents communicate directly:** running agents can exchange messages and orchestrate one another without routing everything through the user.
- **Long tasks keep moving:** automatic compaction, persistent goals, heartbeats, schedules, autonomous mode, and retained subagents preserve progress across turns and terminal sessions.

## Getting Started

Clone and run the pinned fork from source on macOS or Linux:

```bash
git clone https://github.com/milkinfrastructure/milk-man.git
cd milk-man
npm ci
./prime-agent.sh --version
```

Run the existing harness against its own source from bash on macOS:

```bash
export OPENAI_API_KEY=milk_live_...
export MILK_MAN_STATE_DIR=/absolute/private/milk-man-state
mkdir -p "$MILK_MAN_STATE_DIR"
./milk/self-improve.sh "Fix one reviewed Milk Man issue and prove it with tests."
```

The launcher requires a clean source checkout, creates and retains a disposable
`codex/milk-man-self-improve-*` worktree branch at its exact `HEAD`, and
APFS-clones `node_modules`. The OpenAI client
uses the operator-issued key to call GLM through the hosted Milk Carton endpoint
from the trusted parent. The Python tool and its child commands run under SRT
without network access or API keys; they can write only the disposable worktree,
temporary files, and kernel snapshots, not harness configuration, sessions,
`.git`, `node_modules`, the real checkout, or user files.
The fixed repository gate runs in the same sandbox without credentials.
Review the retained worktree before copying or committing a diff. See
[local Milk execution](docs/milk-local-execution.md).

An optional bounded Codex handoff stays shell-native:

```bash
./milk/codex-context.sh SESSION_UUID#120-160 |
  ./milk/self-improve.sh "Continue from this reviewed context."
```

Start Prime Agent from the repository or directory you want it to work in:

```bash
cd /path/to/project
prime-agent
```

On first launch, run `/login` to choose a subscription or API-key provider. Prime Agent works in the current directory and can run commands and modify files there. Use a disposable clone, clean worktree, or another checkpoint you can inspect and restore.

> [!WARNING]
> Prime Agent executes model-generated Python and project commands with your user permissions. Its worker and kernel processes improve lifecycle isolation and recovery; they are **not** a security sandbox. Review changes and use trusted repositories, instructions, skills, and extensions only. Run untrusted code or instructions in an external sandbox or restricted environment.

Useful commands:

```bash
prime-agent agents                   # Browse running, idle, and saved sessions
prime-agent attach <agent>           # Reattach to a running session
prime-agent --resume [path|id]       # Browse sessions or resume one directly
prime-agent status                   # Inspect background service state
prime-agent doctor [--fix]           # Inspect or repair background services
prime-agent update [--force]         # Update Prime Agent
prime-agent shutdown [--force]       # Stop every agent, worker, and background service
```

## Built for Long-Running Work
Prime Agent is built for long-running work, especially for evaluations in research. These features are available in the TUI, and when run autonomously.

- **Continual Harness:** `/refine` can persist focused, reviewable lessons as supplemental prompts, memories, reusable skill descriptions, or subagent specifications, with recorded refinement history. It does not replace packaging and reviewing new executable skills.
- **Direct agent-to-agent communication:** running agents and retained subagents can discover one another, exchange messages, and steer active work.
- **Daemon-backed continuity:** active sessions, Python REPL state, schedules, and subagents keep running when the terminal detaches and can be reattached later.
- **Heartbeats and schedules:** `/heartbeat`, `rlm_heartbeat`, and `prime-agent schedule` can re-enter a session periodically or at a specific time.
- **Persistent goals:** `/goal` keeps an objective and its progress active across turns until it is completed, paused, or cleared.
- **Bounded autonomous mode:** `/autonomous` continues within configured turn, token, and time budgets and can run user-defined quality gates. A passed gate checks only what that gate verifies; reaching a limit does not imply task success.

## Documentation

- [Quickstart](packages/coding-agent/docs/quickstart.md) — install, authenticate, and run a first session
- [Usage and CLI reference](packages/coding-agent/docs/usage.md) — commands, sessions, autonomous limits, and output modes
- [Long-running and background agents](packages/coding-agent/docs/long-running-agents.md) — detach and reattach, goals, heartbeats, and schedules
- [RLM programming model](packages/coding-agent/docs/rlm.md) — the persistent Python REPL, subagents, skills, and the trust model
- [JSON mode](packages/coding-agent/docs/json.md) and [RPC mode](packages/coding-agent/docs/rpc.md) — headless automation and integrations
- [Skills](packages/coding-agent/docs/skills.md) — install and create reusable capabilities
- [Provider setup](packages/coding-agent/docs/providers.md) — subscription and API-key providers
- [Architecture overview](packages/coding-agent/docs/architecture.md) — daemon, worker, kernel, and persistence boundaries
- [Development](packages/coding-agent/docs/development.md) — build and run from source

## Contributing

Start with a GitHub Discussion for [general questions](https://github.com/PrimeIntellect-ai/prime-agent/discussions/categories/general), [bug reports](https://github.com/PrimeIntellect-ai/prime-agent/discussions/categories/bug-reports), and [feature requests](https://github.com/PrimeIntellect-ai/prime-agent/discussions/categories/feature-requests). Maintainers promote accepted work into Issues, and pull requests are reviewed from maintainers and vouched contributors.

Read the [contribution guidelines](CONTRIBUTING.md) for the full process. Report security vulnerabilities privately by following the [security policy](SECURITY.md).

## Acknowledgements

Our agent and TUI is built on top of [`pi`](https://github.com/earendil-works/pi). We thank the authors of `pi` for their valuable work.

## License

Prime Agent is fully open source and released under the [MIT License](LICENSE).

## Citation

If you use this codebase in your research, please cite Prime Agent:

```bibtex
@article{karten2026prime,
  title={Prime Agent: A Self-Improving RLM Harness},
  author={Karten, Seth and Zhang, Alex L. and Thomas, Kevin and Müller, Sebastian and Bakouch, Elie and Auras, Daniel and Senghaas, Mika and Obeid, Fares and Dunas, Konstantin and Hagemann, Johannes and Jaghouar, Sami},
  journal={arXiv preprint arXiv:2608.23552},
  year={2026}
}
```

Available at [https://arxiv.org/abs/2608.23552](https://arxiv.org/abs/2608.23552).

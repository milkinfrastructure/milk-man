# Contributing to Milk Man

Milk Man is Milk's local-first agent harness and deterministic jobs runtime.

The current public contribution path is a focused
[pull request](https://github.com/milkinfrastructure/milk-man/pulls). Describe
the problem, the smallest change, and what you actually ran. Do not include API
keys, tokens, private prompts, production traffic, or other sensitive data.
Report vulnerabilities through [SECURITY.md](SECURITY.md), never a public pull
request.

Keep changes narrow and follow [AGENTS.md](AGENTS.md). Use the smallest relevant
check and, for milestone behavior, one real end-to-end pass. Add a focused test
only when it is the smallest durable protection for changed behavior. Do not
add fixture suites, speculative abstractions, unrelated refactors, or dependency
changes by default.

Changes to the retained Headlong subset must preserve its Apache-2.0 notice and
identify Milk's modifications.

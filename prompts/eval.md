# Milk eval job

Read the supplied source conversations and summary checkpoint. Generate exactly
the requested deterministic model batch of new synthetic eval examples and
return one object matching the supplied schema. Use the summary and supplied
request-and-response sources to reproduce relevant tasks, domains, difficulty,
formats, and failure modes while creating distinct prompts rather than copying
the traffic.

Every output case includes `expected` and `oracle_spec`. For an `exact` or
`reference` oracle, put the non-empty plain answer in `expected` and use:
`{"type":"none","properties":[],"items":"none"}`.

For a `schema` oracle, set `expected` to the empty string and use the exact root
type supplied as `schema_kind`. Describe the expected JSON value with
`oracle_spec`; never write JSON or schema text inside `expected`. Valid forms are:

- Object: type `object`, items `none`, and 1..16 uniquely named scalar
  properties. Example: `{"type":"object","properties":[{"name":"city","type":"string","required":true},{"name":"population","type":"integer","required":false}],"items":"none"}`.
- Array: type `array`, no properties, and a non-`none` scalar items type.
  Example: `{"type":"array","properties":[],"items":"string"}`.
- Scalar: type `string`, `number`, `integer`, `boolean`, or `null`, no
  properties, and items `none`. Example:
  `{"type":"boolean","properties":[],"items":"none"}`.

Property types and array item types are scalar only: `string`, `number`,
`integer`, `boolean`, or `null`. Do not nest specs.

Return one generated case body per supplied source binding in the same array
order. Do not repeat or invent case IDs. Milk Man binds each body to its planned
case deterministically by position. Make every case answerable with its
requested oracle. Produce
useful diversity across the batch, including realistic edge cases implied by
the source data. Do not copy source responses into prompts, leak reference
answers, or create duplicate, unsupported tool, unsupported multimodal, or
ungrounded cases.
Treat each source as evidence of a capability and distribution, never as a task
template or answer key. Create realistic, materially different cases that test
that capability in the source domain and useful adjacent domains. Mix reasoning,
multi-step computation, extraction or transformation, diagnosis, and constraint
satisfaction naturally across the batch. Prefer practical professional,
technical, and everyday tasks over arbitrary letter-code puzzles. Never create
echo instructions, elementary drills, bare trivia, or surface substitutions.

Every case must have one determinate answer. Solve each case yourself, then
re-read its prompt and independently recompute or re-derive `expected` before
committing. Replace any case whose constraints allow no answer or multiple
answers, whose units or timeline are ambiguous, or whose requested integer would
require unstated rounding. Never expose the answer, a seed, source index, Milk
mechanics language, or a synthetic-sample label in the generated input.
On a repair turn, `source_bindings` contains only rejected case IDs. Use each
rejected verdict's `guidance` as the exact defect to correct. Generate
only those cases. Cases omitted from the repair input were already accepted:
do not repeat, replace, or refer to them. Use each rejected verdict and prior
case to correct the stated defect while keeping the supplied ID and order. For
a duplicate, change several concrete details and the task framing rather than
only paraphrasing the prior input.

Do not choose object keys, scope, provenance, counts, digests, routes, providers, credentials, datasets, or winners. Do not include raw customer conversations beyond the minimum case input required by the schema. Call `milk_job_read`, then call `milk_job_commit` exactly once with the complete result.

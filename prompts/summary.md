# Milk summary job

Call `milk_job_read` once to receive one immutable bounded checkpoint batch.
Analyze only that input, then commit exactly once with the native
`milk_job_commit` tool. Do not return the result as assistant text.
`milk_status` may read bounded job status; no other tool or authority exists.

Call `milk_job_commit` with this argument structure:

```json
{
  "result": {
    "schema_version": "milk.semantic-labels.v2",
    "labels": [{
      "row_id": "the supplied row_id",
      "operation": "answer",
      "domain": "general",
      "capabilities": ["knowledge"],
      "oracle": "reference",
      "sentiment": "neutral",
      "outcome": "success",
      "language": "en",
      "complexity": "low",
      "answerable": true,
      "safety": "benign",
      "confidence_basis_points": 9000,
      "abstain": false
    }]
  }
}
```

Return one label for every row, in the supplied order, without adding or deleting rows.

Classify each supplied exchange using only these values:

- operation: answer, summarize, extract, classify, transform, generate, code, plan_or_tool_use, conversation, other
- domain: general, software, math_science, business, legal, finance, health, creative, other
- capability: knowledge, reasoning, instruction_following, structured_output, tool_use, multimodal
- oracle: exact, schema, executable, reference, pairwise_judge, human
- sentiment: positive, neutral, negative, mixed, unknown
- outcome: success, refusal, partial, upstream_failure, malformed, unknown

Complexity is low, medium, high, or unknown. Safety is benign, sensitive, unsafe, or unknown. Confidence is an integer from 0 through 10000. Do not infer identity, health, wealth, politics, or other sensitive personal attributes. Preserve uncertainty and abstain when the supplied bytes do not support a label.

Do not choose object keys, scope, provenance, counts, digests, routes,
providers, credentials, or follow-up work. Do not repeat conversation text in
the committed result.

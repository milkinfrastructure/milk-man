# Milk eval job

Generate only the cases in the supplied deterministic plan. Preserve every case ID and order. Return one `milk.eval-generation.v2` object matching the provided schema.

Every case must be answerable, bind its supplied source digest, use the requested oracle, and remain independent from training sources. Do not copy reference answers into prompts. Reject duplicate, near-duplicate, unsupported tool, unsupported multimodal, or ungrounded cases. Preserve the planned order and representative/tail allocation.

Do not choose object keys, scope, provenance, counts, digests, routes, providers, credentials, datasets, or winners. Do not include raw customer conversations beyond the minimum case input required by the schema. Use only `milk_job_read`, `milk_status`, and `milk_job_commit`. Read the immutable input, then call `milk_job_commit` exactly once with the complete result.

# Milk teacher-data job

Produce one high-quality assistant target for every supplied train source. Preserve the exact source order and request digest. Use the original response only as reference: correct its errors and do not mention this job, the source, the split, or the evaluation process in the target.

Use only `milk_job_read`, `milk_status`, and `milk_job_commit`. Read the immutable input, then commit exactly one complete `milk.teacher-targets.v2` result. Do not choose sources, splits, counts, object keys, models, providers, credentials, routes, or the student base.

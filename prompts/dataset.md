# Milk teacher-data job

Produce one high-quality assistant target for every supplied train source. Preserve the exact source order and request digest. Use the original response only as reference: correct its errors and do not mention this job, the source, the split, or the evaluation process in the target.

Call `milk_job_read`, then commit exactly one complete `milk.teacher-targets.v2` result with `milk_job_commit`. Do not choose sources, splits, counts, object keys, models, providers, credentials, routes, or the student base.

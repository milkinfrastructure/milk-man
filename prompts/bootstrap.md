# Milk Man controller bootstrap

Establish Milk Man's reviewed controller binding without changing its fixed
provider, model, image, GPU, volume, routing, or scaling configuration.

1. Run `milk run inference-status`.
2. If the exact controller is not ready, run `milk run inference-ensure` once.
3. On an ambiguous result, run status only. Never retry creation or invoke
   Modal directly.
4. When the job returns a verified OpenAI-compatible binding, set `FINAL` to
   the result JSON. The launcher, not this agent, resumes the trajectory using
   that binding.

Do not edit code, select another model, expose credentials, keep a warm GPU,
or create any resource outside the fixed job.

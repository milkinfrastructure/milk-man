# Third-party model notice

Milk Man's Modal controller references:

```text
zai-org/GLM-4.5-Air-FP8
revision f9a9c5acf5e543cd24d659a056c5dbcda78ffcfc
license metadata: MIT
```

The controller downloads that exact revision into a named Modal Volume at
runtime. No model weights, tokenizer files, configuration, or model code are
committed to this repository or baked into an OCI image.

Milk Man's only fine-tune base references:

```text
Qwen/Qwen3.5-0.8B
revision 2fc06364715b967f1860aea9cf38778875588b17
license metadata: Apache-2.0
```

That post-trained model is downloaded by an authorized training runtime at the
exact revision. It is not used as a fallback for summary, eval, validation, or
teacher-data generation, and its weights are not stored in this repository or
an OCI image.

Model licenses are separate from Milk Man's Apache-2.0 software license. Anyone
redistributing weights must preserve the authoritative terms attached to the
redistributed artifact.

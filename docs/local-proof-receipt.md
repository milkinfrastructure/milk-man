# Disposable local proof receipt

Run: 2026-08-29, model-backed fork source execution under its initial working
name, Milk Churn.

- source commit: `b464e2fc63f912ee128643359bcbeb37cd5a0344`;
- source mode: detached disposable Git worktree;
- task SHA-256:
  `65bafa84accee56206752b0a757d9072098d7dd389b77184afc0402a84bb4d4a`;
- non-secret model config SHA-256:
  `095c2003a148900c8c98ba50478f6023b98fdd320d87414d4239b32824ad615f`;
- private session SHA-256:
  `bba79ce6e5d61c2b1887a2d1bb500e44ecd20d0ff18a0b362ba1596c19b54f17`;
- generated file: `docs/local-proof.md`, SHA-256
  `4d6720dc29b6b01e3613eae2d68149503db96d9a02069aa44b5c1b6349ef67f5`;
- changed paths: exactly `docs/local-proof.md`;
- gate: `npm run check`, exit 0; 937 files checked, TypeScript check,
  installer render check, and browser smoke check passed;
- configured agent model: Baseten `zai-org/GLM-5.3-Flash`;
- recorded agent-model spend: `$0.00095770`;
- raw-key scan across the task, config directory, private session, and generated
  file: no match;
- cloud deploy, remote object write, push, route preparation, signing, and
  publication: not attempted.

The proof file and private session remain disposable and are not adopted into
the fork. This receipt proves one bounded local edit-and-check loop only. It
does not prove a production Milk deployment.

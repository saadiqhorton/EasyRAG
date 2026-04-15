# Rule: docs and change control

## Update docs when
- architecture changes,
- retrieval logic changes,
- ingestion workflow changes,
- UX flows change,
- evaluation requirements change,
- commands or repo structure change.

## Documentation rules
- Keep `spec.md` as the high-level source.
- Keep detailed decisions in the relevant file under `docs/`.
- Avoid creating parallel undocumented behavior in code.
- If a change intentionally diverges from the spec, document the divergence clearly and update the spec accordingly.

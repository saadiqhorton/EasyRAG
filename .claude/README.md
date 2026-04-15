# Claude Code workspace configuration

This repository uses a rules-first `.claude/` setup.

## Included
- `CLAUDE.md` — project-wide operating instructions
- `settings.json` — safe default permissions
- `rules/` — authoritative behavior rules, especially for spec compliance and trust-sensitive work
- `skills/` — thin auto-invoked helpers reinforcing spec, architecture, grounding, UI trust, and docs sync
- `commands/` — explicit slash-command workflows for common spec-driven tasks

## Not included
- No `.claude/agents/` directory
- No role-based or persona-based setup

## Use the commands
- `/spec-check`
- `/implement-from-spec`
- `/update-spec`
- `/retrieval-review`
- `/ingestion-review`
- `/docs-sync`
- `/ui-trust-check`

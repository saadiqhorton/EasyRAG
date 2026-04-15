# Rule: grounding and user trust

## Answer quality rules
- Answers must stay within retrieved evidence.
- Unsupported claims are defects.
- The system must be allowed to say there is not enough evidence.
- Citations should be easy to inspect and linked to source context.

## UX trust rules
- Never hide ingestion failures behind generic success states.
- Never return polished answers without nearby evidence.
- Always expose indexing state, warnings, and parse/transcript/OCR confidence where relevant.
- Keep failure states debuggable by users and operators.

## Retrieval rules
- Prefer evidence diversity and dedupe near-identical chunks.
- Respect document versioning and active/inactive state.
- Store and expose the evidence set used for answer generation.

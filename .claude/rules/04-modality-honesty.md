# Rule: modality-specific honesty

## Principle
The system must be honest about what it extracted and how reliable that extraction is.

## Requirements
- Distinguish native text extraction from OCR-derived text.
- Distinguish transcript evidence from visual/video evidence.
- Do not imply image, chart, table, or video-scene understanding that the current pipeline does not actually support.
- Preserve modality metadata in designs and implementations.
- Surface confidence and limitations in diagnostics and evidence views.

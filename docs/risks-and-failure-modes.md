# Risks and Failure Modes

## Overview
This document captures the most likely ways the platform can break or become untrustworthy.

## 1. Parsing failure
Symptoms:
- missing sections
- wrong reading order
- broken tables
- duplicated headers/footers in chunks

Impact:
- retrieval and answers become fundamentally unreliable

Mitigation:
- parser quality checks
- page-level previews
- OCR fallback with confidence labels

## 2. Chunking failure
Symptoms:
- chunks too small to answer with confidence
- chunks too large and noisy
- section boundaries broken

Impact:
- retrieval surfaces incomplete or mixed context

Mitigation:
- structure-aware chunking
- chunk diagnostics
- benchmark-driven tuning

## 3. Retrieval failure
Symptoms:
- right content exists but is not surfaced
- duplicate top-k results
- exact identifiers missed

Impact:
- false negatives, weak answers, user distrust

Mitigation:
- hybrid retrieval
- reranking
- metadata filters
- retrieval evaluation suite

## 4. Grounding failure
Symptoms:
- answer includes claims not present in sources
- citations do not support the answer

Impact:
- hallucinations, trust collapse

Mitigation:
- strict prompt rules
- evidence-only generation
- abstention modes
- answer audits

## 5. Versioning failure
Symptoms:
- old and new docs both retrieved without precedence
- deleted content still appears

Impact:
- contradictory answers and stale knowledge

Mitigation:
- active version flags
- reindex rules
- retrieval penalties for inactive versions

## 6. Multimodal overclaiming
Symptoms:
- system claims image or video understanding beyond actual capability
- transcripts used as if they cover visual details

Impact:
- false confidence and user confusion

Mitigation:
- modality-specific confidence labels
- honest feature boundaries
- separate visual evidence pipeline

## 7. Graph pollution
Symptoms:
- entity duplicates
- hallucinated relationships
- graph path retrieval returns wrong links

Impact:
- misleading but confident reasoning

Mitigation:
- source-linked edges
- confidence scoring
- human-debuggable graph view
- graph as supplemental path only

## 8. UX trust failure
Symptoms:
- clean UI hides failed indexing
- users cannot inspect evidence
- errors are generic

Impact:
- debugging becomes hard and trust erodes quickly

Mitigation:
- transparent state
- evidence inspector
- visible failure reasons

## 9. Performance failure
Symptoms:
- long indexing queues
- query latency spikes
- timeouts under moderate load

Impact:
- system feels broken even when accuracy is decent

Mitigation:
- background workers
- queue visibility
- staged processing
- degraded-mode query path

## 10. Evaluation blind spots
Symptoms:
- system performs well only on demos
- unseen file types fail in production

Impact:
- production surprises and firefighting

Mitigation:
- gold datasets
- file-type-specific testing
- regression gates

## Highest-risk areas for this product vision
Given support for PDFs, docs, images, and video, the most likely weak zones are:
- scanned PDFs
- diagrams and screenshots
- tables and charts
- video content where the key evidence is visual rather than spoken
- graph extraction over messy enterprise documents

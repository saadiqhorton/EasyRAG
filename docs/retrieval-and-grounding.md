# Retrieval and Grounding

## Objective
Return the most relevant evidence for a user query and generate an answer that stays within the bounds of retrieved support.

## Retrieval pipeline

### Stage 1: query normalization
Process the user query into:
- raw query
- normalized query
- optional filters
- query intent classification
- optional expansion terms

### Stage 2: first-pass retrieval
Use hybrid retrieval:
- dense semantic retrieval
- lexical or BM25 retrieval
- optional metadata filtering

Rationale:
- semantic retrieval handles paraphrase and conceptual similarity
- lexical retrieval catches exact terms, identifiers, names, and rare phrases

### Stage 3: candidate merge and dedupe
Merge candidates across strategies.

Rules:
- dedupe near-identical chunks
- prefer active document versions
- diversify across documents when rankings are overly redundant

### Stage 4: reranking
Run a reranker over top-k candidates.

Reranker inputs should include:
- query text
- chunk text
- title
- section path
- page/timestamp context

### Stage 5: evidence packaging
Pass the top evidence set to the generation layer with:
- chunk text
- citation anchors
- source metadata
- confidence signals

## Optional graph retrieval path
Graph retrieval can be run:
- in parallel with chunk retrieval, or
- conditionally for relation-heavy queries

Use cases:
- entity relationship questions
- process dependencies
- cross-document linkage queries

Constraints:
- graph evidence must still resolve back to source chunks
- graph-only unsupported answers are not acceptable for high-confidence output

## Answer generation policy
The generation prompt must enforce:
- answer only from provided evidence
- explicitly cite supporting sources
- state uncertainty when evidence is incomplete
- do not invent missing facts
- distinguish inferred conclusions from explicit source statements

## Abstention policy
The system should abstain when:
- retrieval scores are low
- evidence conflicts materially
- only low-confidence OCR/transcript evidence is available
- the answer would require external knowledge not present in the collection

Example response modes:
- answered with evidence
- partially answered with caveat
- insufficient evidence

## Citation requirements
Every answer should support:
- per-claim citation where feasible
- clickable references to source document
- page/section/timestamp anchors
- chunk inspection on demand

## Query types

### Fact lookup
Example:
- What is the refund policy?

Needs:
- exact citation
- minimal synthesis

### Comparative summary
Example:
- How do these two onboarding docs differ?

Needs:
- multi-document retrieval
- contrastive evidence grouping

### Process reasoning
Example:
- What systems depend on service X?

Needs:
- graph-aware retrieval may help
- still cite source passages

### Media-derived lookup
Example:
- What did the speaker say about deployment risk around minute 12?

Needs:
- transcript timestamps
- optional linked video evidence

## Failure patterns to watch
- top-k contains duplicate chunks from the same section
- lexical misses exact identifiers because normalization stripped them
- semantic retrieval surfaces thematically similar but wrong chunks
- reranker prefers polished text over actually relevant text
- generation merges evidence from conflicting versions

## Core guardrails
- always keep raw candidate scores for debugging
- always store final evidence set used for answer generation
- log abstentions and near misses
- include version metadata in retrieval scoring
- separate retrieval metrics from answer quality metrics

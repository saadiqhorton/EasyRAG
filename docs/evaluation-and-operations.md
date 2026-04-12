# Evaluation and Operations

## Objective
Ensure the system stays reliable over time instead of only appearing impressive during demos.

## Evaluation layers

### 1. Ingestion evaluation
Track by file type:
- parse success rate
- OCR usage rate
- OCR confidence distribution
- average chunks per document
- malformed chunk rate

### 2. Retrieval evaluation
Use a test set of real questions with known supporting chunks.

Metrics:
- recall@k
- MRR
- nDCG
- reranker lift over baseline
- duplicate rate in top-k

### 3. Answer quality evaluation
Metrics:
- faithfulness to evidence
- citation correctness
- unsupported claim rate
- abstention precision and recall

### 4. Operations evaluation
Metrics:
- indexing latency
- query latency by stage
- worker backlog
- storage growth
- reindex frequency
- failure recurrence

## Gold dataset design
Build a benchmark set containing:
- short factual queries
- long-form synthesis queries
- exact-identifier lookups
- cross-document comparison queries
- OCR-heavy document queries
- image-derived queries where supported
- transcript/timestamp queries where supported

Each item should include:
- query
- expected answer type
- gold supporting document IDs
- gold chunk IDs where possible
- pass/fail notes

## Production monitoring
Dashboards should show:
- active ingestion jobs
- failed ingestion jobs by stage
- search latency percentiles
- answer generation latency
- low-support answer rate
- most frequently failing document types

## Logging requirements
Log at minimum:
- ingestion job transitions
- parser warnings
- chunk stats
- retrieval candidates and scores
- reranker output order
- answer mode and evidence IDs
- abstention events

## Runbooks

### Parse failures
- inspect mime mismatch
- inspect parser selection
- retry with OCR if appropriate
- flag recurring parser bugs by file pattern

### Retrieval degradation
- compare recall metrics to previous baseline
- inspect recent embedding model changes
- inspect chunk size or overlap changes
- inspect metadata filter regressions

### Hallucinated answers
- verify prompt grounding rules
- inspect evidence packaging
- check whether abstention thresholds dropped
- inspect conflicting document versions

### Graph-related noise
- inspect recent extraction model changes
- sample false edges
- tighten canonicalization
- reduce graph weighting until precision improves

## Release gates
Do not promote changes to production if they materially worsen:
- retrieval recall
- citation correctness
- unsupported claim rate
- parse success on common file types

## Cost controls
Track cost drivers separately:
- OCR spend
- transcription spend
- embeddings spend
- reranker spend
- answer model spend

Support policies such as:
- transcript-only mode for video during MVP
- image enrichment only for selected collections
- graph extraction only on opted-in corpora

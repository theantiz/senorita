# Phase 5.3: Intelligence Hardening

## Overview
Phase 5.3 stabilizes Señorita's personal intelligence layer, shifting from primitive substring mapping to mathematically bounded vector analysis using `pgvector`. It introduces preference evolution mechanics, an autonomy configuration, and strict budget enforcements.

## Architecture & Algorithm
### 1. Vector Retrieval (`pgvector`)
`ContextBuilder` converts the extracted LLM intent into a high-dimensional query embedding. It executes concurrent (but non-colliding) SQLAlchemy statements against `MemoryEntry.embedding` and `Preference.embedding`, measuring inverse cosine distance `<=>`.

### 2. Context Ranking
A deterministic relevance score bounds all selected context limits prior to hitting the LLM:
`Score = (Semantic * 0.50) + (Confidence * 0.20) + (Recency * 0.15) + (Importance * 0.15)`

### 3. Context Budgets
Strict environment constants restrict ingestion overload:
- `CONTEXT_MAX_MEMORIES`: 5
- `CONTEXT_MAX_PREFERENCES`: 5

### 4. Temporal Memory
`valid_from` and `valid_until` define the exact chronological scope of facts. Any memory where `valid_until < now()` is structurally excluded from retrieval without permanent destruction.

### 5. Preference Supersession
Implicit capture leverages embeddings to detect evolving behavioral rules. If a newly inferred preference matches an old one with >0.70 similarity but alters the parameters, the older preference is marked `SUPERSEDED` and superseded by the new row, preserving historical auditing.

### 6. Autonomy Levels
Users are assigned one of four operational modes:
- **SUGGEST**: Recommends tools, never executes.
- **CONFIRM**: Executes reads, prompts for destructive writes.
- **TRUSTED**: Executes within bounded scopes autonomously.
- **FULL_AUTO**: Unbound execution (not recommended).

## Security Boundaries
Vector searches forcibly include `user_id == current_user.id` at the lowest logical query level, meaning cross-user memory leakage is mathematically impossible at the retrieval step.

## Metrics
- `senorita_context_vector_search_total`
- `senorita_context_similarity`
- `senorita_preference_superseded_total`

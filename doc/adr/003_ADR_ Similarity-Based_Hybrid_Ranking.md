# **Architecture Decision Record**: Similarity-Based Ranking for Hybrid Search

**Status**: Implemented  
**Date**: 12 Nov 2026

## Context

The item and property search endpoints combine vector search with keyword search. Vector search is approximate and may miss relevant entities, while keyword search can resurface candidates that are worth evaluating. Keyword candidates are then assigned the same vector-similarity score used for vector-search candidates.

The results were previously combined using Reciprocal Rank Fusion (RRF). RRF is useful when combining rankings with incomparable scores, but all candidates in this system already share a common similarity measure. It therefore added an additional score and ranking step without being necessary for comparison.

User feedback also showed that the resulting order was difficult to understand. Users saw similarity scores that were not ordered from highest to lowest and reasonably assumed that the results were sorted incorrectly. Explaining the order required knowledge of the additional internal `rrf_score`.

## Decision

RRF will be removed from item and property search.

Vector and keyword search will continue to produce candidates. Candidates are combined by Wikidata ID, the highest similarity score is retained for duplicates, and the final results are sorted by similarity score. Keyword search therefore remains a way to improve candidate recall, while vector similarity remains the relevance measure.

When reranking is enabled, reranker score determines the final order instead. The `rrf_score` field is removed from API responses.

This decision overrides the RRF ranking sections of ADR 001.

## Consequences

### Benefits

**Simpler ranking pipeline:**  
The system no longer calculates, stores, or exposes an additional fusion score.

**Clearer results for users:**  
The score presented to users directly corresponds to the result order.

**Keyword recall is preserved:**  
Keyword search can still surface candidates missed by approximate vector search, and those candidates compete using the same similarity measure.

### Trade-offs

**No automatic overlap boost:**  
Appearing in both vector and keyword search no longer increases an entity's rank by itself.

**Keyword matches depend on similarity:**  
An exact keyword match may rank lower when its semantic similarity to the query is weaker.

## Alternatives Considered

### Keep Reciprocal Rank Fusion

This would preserve the previous overlap-based ranking, but it would retain the additional complexity and the mismatch between the displayed similarity scores and result order.

### Add a keyword score or fixed boost

This would give keyword matches additional influence, but it would introduce another ranking parameter and make the final order harder to interpret.

# **Architecture Decision Record**: Separate Collections for Wikidata Items Without Sitelinks

**Status**: Implemented  
**Date**: 15 Sep 2026

## Context

The primary item collections contain Wikidata items with at least one Wikipedia sitelink. This keeps the default search focused on well-connected entities, but it excludes many Wikidata items that may still be useful for discovery and entity linking.

Adding items without Wikipedia sitelinks to the existing item collections would significantly increase their size and change the behavior of the default search. We need a way to make these items searchable while keeping the existing search scope and collections stable.

## Decision

Wikidata items without Wikipedia sitelinks will be stored in **separate vector collections** from items with Wikipedia sitelinks.

The collection naming pattern is:

* Items with Wikipedia sitelinks: *items\_&lt;language&gt;*
* Items without Wikipedia sitelinks: *items\_nositelinks\_&lt;language&gt;*

When enabled, each collection type is created for every configured vector language. Properties are written only to their existing language-specific collections and are not affected by this change.

Items written to a no-sitelink collection must:

* Have a QID.
* Have no Wikipedia sitelink.
* Pass the normal label and content requirements.
* Not be classified as a scholarly work, as per the [WDQS graph split rules](https://www.wikidata.org/wiki/Wikidata%3ASPARQL_query_service/WDQS_graph_split/Rules)

The split reflects two distinct retrieval needs. Many use cases, including linking Wikimedia content and returning entities backed by Wikipedia articles, require results limited to Wikipedia-linked items. Other use cases, such as Wikidata curation and long-tail entity discovery, require access to items without Wikipedia sitelinks. Keeping these populations in separate collections prevents the much larger no-sitelink population from changing the relevance and performance characteristics of searches designed around Wikipedia-linked entities, while still making it directly searchable when needed. The `all` scope supports use cases that require both populations.

The */item/query/* endpoint exposes a `scope` parameter with three values:

* `with_sitelinks`: Search only items with Wikipedia sitelinks. This is the default.
* `no_sitelinks`: Search only items without Wikipedia sitelinks.
* `all`: Search both collection types.

The `with_sitelinks` scope remains the default for backward compatibility. Users who need broader coverage can explicitly select `no_sitelinks` or `all`.

## Query Orchestration Strategy

### Collection Selection

The API selects item collections according to the requested scope:

* `with_sitelinks` queries the standard item collections.
* `no_sitelinks` queries the available no-sitelink collections.
* `all` queries both collection types in parallel.

When `scope=all` and a specific language is selected, the matching standard item collection and all configured no-sitelink collections are queried.

When `scope=no_sitelinks` is used with a language that has no configured no-sitelink collection, the normal unsupported-language fallback is used and the query is searched against the available collections.

### Result Merging

The with-sitelink and no-sitelink collections represent mutually exclusive item populations and therefore do not contain the same items. Results are still combined by Wikidata QID because the same item can appear in multiple language collections within its population. In that case, the result with the highest similarity score is retained.

## Consequences

### Benefits

**Broader Wikidata coverage:**  
Items without Wikipedia sitelinks can be discovered through semantic search.

**Stable default behavior:**  
The default search continues to use the existing with-sitelinks collections.

**Independent scaling:**  
No-sitelink collections can grow without increasing the size of the standard item collections.

**Explicit user control:**  
Users can choose between Wikipedia-linked entities, no-sitelink entities, or both.

### Trade-offs

**Additional storage and target state:**  
No-sitelink vectors use separate vector collections and caches, even though they share the regular processing pipeline.

**Increased query cost for `all`:**  
Searching both collection types increases query fan-out and may increase latency.

**Potentially sparse entity content:**  
Items without Wikipedia sitelinks may have fewer labels, descriptions, or statements, which can reduce embedding and reranking quality.

## Alternatives Considered

### Store all items in the standard item collections

This would simplify query routing, but it would increase collection size and change the relevance and performance characteristics of the default search.

### Use a metadata filter in a combined collection

A combined collection would still contain all item vectors and would not provide independent scaling or maintenance for the two item populations.

### Exclude items without sitelinks

This would preserve the previous architecture, but users would not be able to discover a large part of Wikidata through vector search.

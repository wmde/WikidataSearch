# WikidataSearch

WikidataSearch is the API and web app for semantic retrieval over the Wikidata Vector Database from the [Wikidata Embedding Project](https://www.wikidata.org/wiki/Wikidata:Embedding_Project).

This repository powers the public service. The intended usage is the hosted API, not running your own deployment.

**Hosted Web App:** [https://wd-vectordb.wmcloud.org](https://wd-vectordb.wmcloud.org) \
**Hosted API Docs (OpenAPI):** [https://wd-vectordb.wmcloud.org/docs](https://wd-vectordb.wmcloud.org/docs) \
**Project Page:** [https://www.wikidata.org/wiki/Wikidata:Vector_Database](https://www.wikidata.org/wiki/Wikidata:Vector_Database)

## Hosted API Usage

Base URL:

```text
https://wd-vectordb.wmcloud.org
```

Use a descriptive `User-Agent` for query endpoints. Generic user agents are rejected.

Example header:

```text
User-Agent: WikidataSearch-Client/1.0 (your-email@example.org)
```

Current operational constraints:

- Rate limit is applied per `User-Agent` (default: `30/minute`).
- Query endpoints require a descriptive `User-Agent` header.
- Current vector shards are `en`, `fr`, `ar`, and `de`.

## API Endpoints

### `GET /item/query/`

Semantic + keyword search for Wikidata items (QIDs), fused with Reciprocal Rank Fusion (RRF).

Parameters:

- `query` (required): natural-language query or ID.
- `lang` (default: `all`): vector shard language; unknown languages are translated then searched globally.
- `K` (default/max: `50`): number of top results requested.
- `instanceof` (optional): comma-separated QIDs used as `P31` filter.
- `rerank` (default: `false`): apply reranker on textified Wikidata content.
- `return_vectors` (default: `false`): include vectors in response payload.

Example:

```bash
curl -sG 'https://wd-vectordb.wmcloud.org/item/query/' \
  --data-urlencode 'query=Douglas Adams' \
  --data-urlencode 'lang=en' \
  --data-urlencode 'K=10' \
  -H 'User-Agent: WikidataSearch-Client/1.0 (your-email@example.org)'
```

### `GET /property/query/`

Semantic + keyword search for Wikidata properties (PIDs), fused with RRF.

Parameters:

- `query` (required)
- `lang` (default: `all`)
- `K` (default/max: `50`)
- `instanceof` (optional): comma-separated QIDs used as `P31` filter.
- `exclude_external_ids` (default: `false`): excludes properties with datatype `external-id`.
- `rerank` (default: `false`)
- `return_vectors` (default: `false`): include vectors in response payload.

Example:

```bash
curl -sG 'https://wd-vectordb.wmcloud.org/property/query/' \
  --data-urlencode 'query=instance of' \
  --data-urlencode 'lang=en' \
  --data-urlencode 'exclude_external_ids=true' \
  -H 'User-Agent: WikidataSearch-Client/1.0 (your-email@example.org)'
```

### `GET /similarity-score/`

Similarity scoring for a fixed list of Wikidata IDs (QIDs and/or PIDs) against one query.

Parameters:

- `query` (required)
- `qid` (required): comma-separated IDs, for example `Q42,Q5,P31` (maximum: `100` IDs).
- `lang` (default: `all`)
- `return_vectors` (default: `false`): include vectors in response payload.

Example:

```bash
curl -sG 'https://wd-vectordb.wmcloud.org/similarity-score/' \
  --data-urlencode 'query=science fiction writer' \
  --data-urlencode 'qid=Q42,Q25169,P31' \
  -H 'User-Agent: WikidataSearch-Client/1.0 (your-email@example.org)'
```

## Response Shape

`/item/query/` returns objects with:

- `QID`
- `similarity_score`
- `rrf_score`
- `source` (`Vector Search`, `Keyword Search`, or both)
- `reranker_score` (when `rerank=true`)
- `vector` (when `return_vectors=true`)

`/property/query/` returns the same shape with `PID` instead of `QID`.

`/similarity-score/` returns:

- `QID` or `PID`
- `similarity_score`
- `vector` (when `return_vectors=true`)

## Architecture

High-level request flow:

1. FastAPI route receives the query, enforces user-agent policy, and rate limit.
2. `HybridSearch` orchestrates retrieval:
   - Vector path: embeds query with Jina embeddings and searches Astra DB vector collections across language shards in parallel.
   - Keyword path: runs Wikidata keyword search against `wikidata.org`.
3. Results are fused with Reciprocal Rank Fusion (RRF), preserving source attribution.
4. Optional reranking fetches Wikidata text representations and reorders top hits with Jina reranker.
5. JSON response is returned and request metadata is logged for analytics.

Main components in this repo:

- API app and routing: `wikidatasearch/main.py`, `wikidatasearch/routes/`
- Retrieval orchestration: `wikidatasearch/services/search/HybridSearch.py`
- Vector retrieval backend: `wikidatasearch/services/search/VectorSearch.py`
- Keyword retrieval backend: `wikidatasearch/services/search/KeywordSearch.py`
- Embeddings/reranking client: `wikidatasearch/services/jina.py`

## License

See [LICENSE](LICENSE).

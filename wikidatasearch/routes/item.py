"""Routes for Wikidata item search operations."""

import time
import traceback
from typing import List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi_cache.decorator import cache
from pydantic import BaseModel, Field

from ..config import SEARCH, settings
from ..dependencies import limiter, require_descriptive_user_agent
from ..services.logger import Logger


class ItemQuery(BaseModel):
    """Represents one item search result."""

    QID: str = Field(..., description="Wikidata item QID")
    similarity_score: float = Field(..., description="Dot product similarity")
    rrf_score: Optional[float] = Field(0.0, description="Reciprocal Rank Fusion score")
    source: Optional[str] = Field("", description="Source of the search")
    vector: Optional[list[float]] = Field(None, description="Present when return_vectors is True")
    reranker_score: Optional[float] = Field(None, description="Present when rerank is True")


router = APIRouter(
    prefix="/item",
    tags=["Queries"],
    dependencies=[Depends(require_descriptive_user_agent)],
    responses={
        200: {
            "description": "List of relevant Wikidata items sorted by fused similarity scores",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "QID": "Q42",
                            "similarity_score": 0.95,
                            "rrf_score": 0.043,
                            "source": "Vector Search",
                        }
                    ]
                }
            },
        },
        422: {"description": "Missing or invalid parameters"},
        500: {"description": "Internal Server Error"},
    },
)


@router.get(
    "/query/",
    summary="Search Wikidata items with vector and keyword (RRF)",
    operation_id="searchItemsRRF",
    response_model=List[ItemQuery],
    response_model_exclude_none=True,
)
@cache(expire=settings.CACHE_TTL)
@limiter.limit(settings.RATE_LIMIT)
async def item_query_route(
    request: Request,
    background_tasks: BackgroundTasks,
    query: str = Query(
        ...,
        examples=["Douglas Adams", "Q42", "Who wrote 1984?"],
        description="Query string to search for",
    ),
    lang: str = Query(
        "all",
        description='Language code for the query. Use "all" to search across all vectors.',
    ),
    scope: Literal["with_sitelinks", "no_sitelinks", "all"] = Query(
        "with_sitelinks",
        description=(
            "Controls which Wikidata items are searched: `with_sitelinks` searches items linked to Wikipedia "
            "pages; `no_sitelinks` searches items without linked Wikipedia pages; `all` searches both."
        ),
    ),
    K: int = Query(
        settings.MAX_VECTORDB_K,
        ge=1,
        description="Number of top results to return",
    ),
    instanceof: Optional[str] = Query(
        None,
        examples=["Q2", "Q5,Q634"],
        description='Comma separated QIDs to filter by "instance of".',
    ),
    rerank: bool = Query(False, description="If true, apply a reranker model."),
    return_vectors: bool = Query(False, description="If true, include vector embeddings in the response."),
):
    """Performs vector and keyword search on Wikidata items.

    This endpoint combines Vector Search and Keyword Search using Reciprocal Rank Fusion (RRF).
    Optionally, reranking can be enabled for additional relevance scoring.

    **Args:**

    - **query** (str): Query string to search for.
    - **lang** (str): Language code for the query.
      Use `"all"` to search across all vectors in the database.
      If a specific language is provided, only vectors in that language are searched.
      If no vectors exist for that language, the query is translated to English and searched against all vectors.
    - **scope** (str): Controls which Wikidata items are searched. Defaults to `"with_sitelinks"`.
      - `"with_sitelinks"`: Search items linked to Wikipedia pages.
      - `"no_sitelinks"`: Search items without linked Wikipedia pages.
      - `"all"`: Search both kinds of items. No-sitelink collections are included regardless of the selected
        language.
    - **K** (int): Number of top results to return.
    - **instanceof** (str, optional): Comma-separated list of QIDs to filter by a specific "instance of" class.
    - **rerank** (bool): If `true`, apply a reranker model (slower).
    - **return_vectors** (bool): If `true`, include vector embeddings in the response.

    **Returns:**

    Each item in the result list includes:

    - **QID** (str): Wikidata QID of the item.
    - **similarity_score** (float): Dot product similarity score between the item and the query.
    - **rrf_score** (float): Reciprocal Rank Fusion score combining vector and keyword results.
    - **source** (str): Indicates whether the item was found by "Keyword Search", "Vector Search", or both.
    - **vector** (list[float], optional): Present when `return_vectors` is `true`.
    - **reranker_score** (float, optional): Present when `rerank` is `true`.
    """
    start_time = time.time()

    if not query:
        response = "Query is missing"
        background_tasks.add_task(Logger.add_request, request, 422, start_time, error=response)
        raise HTTPException(status_code=422, detail=response)

    if K > settings.MAX_VECTORDB_K:
        response = f"K must be less than {settings.MAX_VECTORDB_K}"
        background_tasks.add_task(Logger.add_request, request, 422, start_time, error=response)
        raise HTTPException(status_code=422, detail=response)

    # Build filter
    filt = {"metadata.IsItem": True}
    if instanceof:
        qids = [qid.strip() for qid in instanceof.split(",") if qid.strip()]
        if not qids:
            response = "Invalid instanceof filter"
            background_tasks.add_task(Logger.add_request, request, 422, start_time, error=response)
            raise HTTPException(status_code=422, detail=response)
        filt["metadata.InstanceOf"] = {"$in": qids}

    try:
        results = SEARCH.search(
            query,
            filter=filt,
            lang=lang.lower(),
            scope=scope,
            vs_K=K,
            ks_K=max(1, (K + 9) // 10),
            rerank=rerank,
            return_vectors=return_vectors,
        )

        results = results[:K]
        background_tasks.add_task(Logger.add_request, request, 200, start_time)

        return results

    except Exception as e:
        background_tasks.add_task(Logger.add_request, request, 500, start_time, error=str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

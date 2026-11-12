"""Routes for Wikidata property search operations."""

import time
import traceback
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi_cache.decorator import cache
from pydantic import BaseModel, Field

from ..config import SEARCH, settings
from ..dependencies import limiter, require_descriptive_user_agent
from ..services.logger import Logger


class PropertyQuery(BaseModel):
    """Represents one property search result."""

    PID: str = Field(..., description="Wikidata property PID")
    similarity_score: float = Field(..., description="Dot product similarity")
    source: Optional[str] = Field("", description="Source of the search")
    vector: Optional[list[float]] = Field(None, description="Present when return_vectors is True")
    reranker_score: Optional[float] = Field(None, description="Present when rerank is True")


router = APIRouter(
    prefix="/property",
    tags=["Queries"],
    dependencies=[Depends(require_descriptive_user_agent)],
    responses={
        200: {
            "description": "List of relevant Wikidata properties sorted by similarity or reranker score",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "PID": "P31",
                            "similarity_score": 0.89,
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
    summary="Search Wikidata properties with vector and keyword search",
    operation_id="searchProperties",
    response_model=List[PropertyQuery],
    response_model_exclude_none=True,
)
@cache(expire=settings.CACHE_TTL)
@limiter.limit(settings.RATE_LIMIT)
async def property_query_route(
    request: Request,
    background_tasks: BackgroundTasks,
    query: str = Query(..., examples=["instance of", "P31"], description="Query string to search for"),
    lang: str = Query(
        "all",
        description='Language code for the query. Use "all" to search across all vectors.',
    ),
    K: int = Query(
        settings.MAX_VECTORDB_K,
        ge=1,
        description="Number of top results to return",
    ),
    instanceof: Optional[str] = Query(
        None,
        examples=["Q18616576"],
        description='Comma separated QIDs to filter by "instance of" class',
    ),
    rerank: bool = Query(False, description="If true, apply a reranker model."),
    return_vectors: bool = Query(False, description="If true, include vector embeddings in the response."),
    exclude_external_ids: bool = Query(
        False,
        description="If true, exclude properties with external identifier datatype.",
    ),
):
    """Performs vector and keyword search on Wikidata properties.

    This endpoint combines Vector Search and Keyword Search, deduplicates entities, and sorts them by
    similarity score. Optionally, reranking can be enabled to replace the similarity-based order.

    **Args:**

    - **query** (str): Query string to search for.
    - **lang** (str): Language code for the query.
      Use `"all"` to search across all vectors in the database.
      If a specific language is provided, only vectors in that language are searched.
      If no vectors exist for that language, the query is translated to English and searched against all vectors.
    - **K** (int): Number of top results to return.
    - **instanceof** (str, optional): Comma-separated list of QIDs to filter by a specific "instance of" class.
    - **rerank** (bool): If `true`, apply a reranker model (slower).
    - **return_vectors** (bool): If `true`, include vector embeddings in the response.
    - **exclude_external_ids** (bool): If `true`, exclude properties with external-identifier datatype.

    **Returns:**

    Each property in the result list includes:

    - **PID** (str): Wikidata PID of the property.
    - **similarity_score** (float): Dot product similarity score between the property and the query.
    - **source** (str): Indicates whether the property was found by "Keyword Search", "Vector Search", or both.
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

    filt = {"metadata.IsProperty": True}
    if instanceof:
        qids = [qid.strip() for qid in instanceof.split(",") if qid.strip()]
        if not qids:
            response = "Invalid instanceof filter"
            background_tasks.add_task(Logger.add_request, request, 422, start_time, error=response)
            raise HTTPException(status_code=422, detail=response)
        filt["metadata.InstanceOf"] = {"$in": qids}

    if exclude_external_ids:
        filt["metadata.DataType"] = {"$ne": "external-id"}

    try:
        results = SEARCH.search(
            query,
            filter=filt,
            lang=lang.lower(),
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

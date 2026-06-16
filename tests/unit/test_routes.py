"""Unit tests for API routes.

Covers response shape and rules, input validation, filter building, language normalization, and error handling.
"""

import pytest
from fastapi import BackgroundTasks, HTTPException


def test_languages_route_returns_split_languages(test_ctx, run_async, make_request):
    """Validate languages route returns split languages."""
    frontend = test_ctx["frontend"]
    req = make_request("/languages")
    data = run_async(frontend.languages(req))
    assert data["vectordb_langs"] == ["en", "fr"]
    assert "de" in data["other_langs"]
    assert "ar" in data["other_langs"]


def test_item_query_route_returns_items_and_sets_item_filter(test_ctx, run_async, make_request):
    """Validate results and built filter for item query route."""
    item = test_ctx["item"]
    req = make_request("/item/query/")
    result = run_async(
        item.item_query_route(
            req,
            BackgroundTasks(),
            query="Douglas Adams",
            lang="all",
            K=5,
            instanceof=None,
            rerank=False,
            return_vectors=False,
        )
    )
    assert result[0]["QID"] == "Q42"
    last_call = test_ctx["search"].calls[-1]
    assert last_call["name"] == "search"
    assert last_call["kwargs"]["filter"]["metadata.IsItem"] is True
    assert last_call["kwargs"]["lang"] == "all"
    assert last_call["kwargs"]["ks_K"] == 1


def test_property_query_route_returns_properties(test_ctx, run_async, make_request):
    """Validate results and built filter for property query route."""
    property_route = test_ctx["property"]
    req = make_request("/property/query/")
    result = run_async(
        property_route.property_query_route(
            req,
            BackgroundTasks(),
            query="instance of",
            lang="all",
            K=5,
            instanceof=None,
            rerank=False,
            return_vectors=False,
            exclude_external_ids=True,
        )
    )
    assert result[0]["PID"] == "P31"
    last_call = test_ctx["search"].calls[-1]
    assert last_call["name"] == "search"
    assert last_call["kwargs"]["filter"]["metadata.IsProperty"] is True
    assert last_call["kwargs"]["filter"]["metadata.DataType"] == {"$ne": "external-id"}
    assert last_call["kwargs"]["lang"] == "all"
    assert last_call["kwargs"]["ks_K"] == 1


def test_item_query_route_lowercases_lang_and_uses_expected_ks_k(test_ctx, run_async, make_request):
    """Validate language normalization and uses expected k for item query route."""
    item = test_ctx["item"]
    req = make_request("/item/query/")
    run_async(
        item.item_query_route(
            req,
            BackgroundTasks(),
            query="Douglas Adams",
            lang="EN",
            K=11,
            instanceof=None,
            rerank=False,
            return_vectors=False,
        )
    )
    last_call = test_ctx["search"].calls[-1]
    assert last_call["kwargs"]["lang"] == "en"
    assert last_call["kwargs"]["ks_K"] == 2


def test_property_query_route_without_exclude_external_ids_does_not_set_datatype_filter(
    test_ctx,
    run_async,
    make_request,
):
    """Validate external ids exclusion for property query route."""
    property_route = test_ctx["property"]
    req = make_request("/property/query/")
    run_async(
        property_route.property_query_route(
            req,
            BackgroundTasks(),
            query="instance of",
            lang="EN",
            K=20,
            instanceof=None,
            rerank=False,
            return_vectors=False,
            exclude_external_ids=False,
        )
    )
    last_call = test_ctx["search"].calls[-1]
    assert last_call["kwargs"]["lang"] == "en"
    assert last_call["kwargs"]["ks_K"] == 2
    assert "metadata.DataType" not in last_call["kwargs"]["filter"]


def test_similarity_score_route_returns_qids_and_pids(test_ctx, run_async, make_request):
    """Validate qids and pids results for similarity score route."""
    similarity = test_ctx["similarity"]
    req = make_request("/similarity-score/")
    result = run_async(
        similarity.similarity_score_route(
            req,
            BackgroundTasks(),
            query="science fiction writer",
            qid="Q42,P31",
            lang="all",
            return_vectors=False,
        )
    )
    ids = {item.get("QID") or item.get("PID") for item in result}
    assert ids == {"Q42", "P31"}
    last_call = test_ctx["search"].calls[-1]
    assert last_call["name"] == "get_similarity_scores"
    assert last_call["kwargs"]["lang"] == "all"


def test_similarity_score_route_rejects_too_many_ids_with_422(test_ctx, run_async, make_request):
    """Validate IDs limit 422 error for similarity score route."""
    similarity = test_ctx["similarity"]
    req = make_request("/similarity-score/")
    qids = ",".join([f"Q{i}" for i in range(101)])

    with pytest.raises(HTTPException) as exc:
        run_async(
            similarity.similarity_score_route(
                req,
                BackgroundTasks(),
                query="test",
                qid=qids,
                lang="all",
                return_vectors=False,
            )
        )

    assert exc.value.status_code == 422


@pytest.mark.parametrize(
    ("route_name", "route_path", "call_kwargs", "search_call_name"),
    [
        (
            "item",
            "/item/query/",
            {
                "query": "Douglas Adams",
                "lang": "all",
                "K": 5,
                "instanceof": None,
                "rerank": False,
                "return_vectors": True,
            },
            "search",
        ),
        (
            "property",
            "/property/query/",
            {
                "query": "instance of",
                "lang": "all",
                "K": 5,
                "instanceof": None,
                "rerank": False,
                "return_vectors": True,
                "exclude_external_ids": False,
            },
            "search",
        ),
        (
            "similarity",
            "/similarity-score/",
            {
                "query": "science fiction writer",
                "qid": "Q42,P31",
                "lang": "all",
                "return_vectors": True,
            },
            "get_similarity_scores",
        ),
    ],
)
def test_routes_accept_and_forward_return_vectors(
    test_ctx,
    run_async,
    make_request,
    route_name,
    route_path,
    call_kwargs,
    search_call_name,
):
    """Validate return_vectors=True is accepted and forwarded to the search layer."""
    route = test_ctx[route_name]
    req = make_request(route_path)
    route_fn_name = {
        "item": "item_query_route",
        "property": "property_query_route",
        "similarity": "similarity_score_route",
    }[route_name]
    route_fn = getattr(route, route_fn_name)

    result = run_async(route_fn(req, BackgroundTasks(), **call_kwargs))
    assert result
    last_call = test_ctx["search"].calls[-1]
    assert last_call["name"] == search_call_name
    assert last_call["kwargs"]["return_vectors"] is True


def test_item_query_route_rejects_invalid_instanceof(test_ctx, run_async, make_request):
    """Validate rejection of invalid instanceof for item query route."""
    item = test_ctx["item"]
    req = make_request("/item/query/")

    with pytest.raises(HTTPException) as exc:
        run_async(
            item.item_query_route(
                req,
                BackgroundTasks(),
                query="Douglas Adams",
                lang="all",
                K=5,
                instanceof=" , , ",
                rerank=False,
                return_vectors=False,
            )
        )

    assert exc.value.status_code == 422


def test_property_query_route_rejects_invalid_instanceof(test_ctx, run_async, make_request):
    """Validate rejection of invalid instanceof for property query route."""
    property_route = test_ctx["property"]
    req = make_request("/property/query/")

    with pytest.raises(HTTPException) as exc:
        run_async(
            property_route.property_query_route(
                req,
                BackgroundTasks(),
                query="instance of",
                lang="all",
                K=5,
                instanceof=" , ",
                rerank=False,
                return_vectors=False,
                exclude_external_ids=False,
            )
        )

    assert exc.value.status_code == 422


def test_similarity_score_route_rejects_empty_qid_list(test_ctx, run_async, make_request):
    """Validate rejection of empty qid list for similarity score route."""
    similarity = test_ctx["similarity"]
    req = make_request("/similarity-score/")

    with pytest.raises(HTTPException) as exc:
        run_async(
            similarity.similarity_score_route(
                req,
                BackgroundTasks(),
                query="science fiction writer",
                qid=" , , ",
                lang="all",
                return_vectors=False,
            )
        )

    assert exc.value.status_code == 422

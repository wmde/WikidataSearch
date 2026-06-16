"""Keyword-based Wikidata search backed by the Wikidata search API."""

import re

import requests
from stopwordsiso import stopwords

from .Search import Search


class KeywordSearch(Search):
    """Search implementation that retrieves candidate IDs from keyword matches."""

    name = "Keyword Search"

    def __init__(self):
        """Initialize the keyword search backend."""
        pass

    def search(self, query: str, filter: dict | None = None, lang: str = "en", K: int = 5) -> list:
        """Retrieve Wikidata items based on keyword matching for a given query string.

        Args:
            query (str): The search query string.
            filter (dict, optional): Additional filtering criteria.
            lang (str): The language of the query. Defaults to 'en'.
            K (int, optional): Number of top results to return. Defaults to 5.

        Returns:
            list: A list of QIDs or PIDs of the results.
        """
        filter = filter or {}

        # If the query is a QID or PID, return it directly.
        if re.fullmatch(r"[PQ]\d+", query):
            return [query]

        query = self._clean_query(query, lang)

        if filter.get("metadata.InstanceOf"):
            instance_of_filter = filter.get("metadata.InstanceOf")["$in"]
            instance_of_filter = "|P31=".join(instance_of_filter)
            instance_of_filter = "haswbstatement:P31=" + instance_of_filter
            query = query + " " + instance_of_filter

        params = {
            "cirrusDumpResult": "",
            "search": query,
            "srlimit": K,
            "uselang": lang,
        }
        headers = {"User-Agent": "Wikidata Vector Database (embedding@wikimedia.de)"}

        if filter.get("metadata.IsItem", False):
            params["ns0"] = 1
        if filter.get("metadata.IsProperty", False):
            params["ns120"] = 1

        url = "https://www.wikidata.org/w/index.php"
        results = requests.get(url, params=params, headers=headers)
        results.raise_for_status()

        results = results.json()["__main__"]["result"]["hits"]["hits"]
        qids = [item["_source"]["title"] for item in results]

        return qids[:K]

    def _clean_query(self, query: str, lang: str) -> str:
        """Remove stop words and split the query into individual terms separated by "OR" for the search.

        Args:
            query (str): The query string to process.
            lang (str): Language code used to remove stop words.

        Returns:
            str: The cleaned query string suitable for searching.
        """
        if (not bool(lang)) or (lang == "all"):
            lang = "en"

        # Remove stopwords
        query = re.sub(r"[^\w\s]", "", query)
        query_terms = [tok for tok in query.split() if tok.lower() not in stopwords(lang)]

        # Join terms with "OR" for Elasticsearch compatibility
        cleaned_query = " OR ".join(query_terms)
        if cleaned_query == "":
            return query

        # Max allowed characters is 300, required by the API
        return cleaned_query[:300]

"""Abstract interfaces and shared helpers for search implementations."""

from abc import ABC, abstractmethod

import requests


class Search(ABC):
    """Abstract base class for search functionality."""

    name: str  # The name of the search implementation.

    @abstractmethod
    def search(self, query: str, filter: dict | None = None, K: int = 100) -> list:
        """Search for items based on the query and filter.

        Args:
            query (str): The search query string.
            filter (dict, optional): Additional filtering criteria.
            K (int, optional): Number of top results to return. Defaults to 100.

        Returns:
            list: Search results as dictionaries.
        """
        pass

    def get_text_by_ids(
        self,
        ids: list[str],
        format: str = "triplet",
        lang: str = "en",
        max_length: int = 4096,
    ) -> dict[str, str]:
        """Fetch textual representations for Wikidata entities.

        Args:
            ids (list[str]): Wikidata entity IDs (QIDs and/or PIDs).
            format (str): Output format requested from the textifier service.
            lang (str): Preferred language code for generated text.
            max_length (int): Maximum length of the text.

        Returns:
            dict[str, str]: Mapping from entity ID to textual representation.
        """
        # Lazy import avoids circular dependency: config -> services.search -> Search.
        from ...config import settings

        if (not bool(lang)) or (lang == "all"):
            lang = "en"

        text = {}
        for i in range(0, len(ids), 50):
            qid = ",".join(ids[i : i + 50])
            params = {
                "id": qid,
                "lang": lang,
                "external_ids": False,
                "references": False,
                "all_ranks": False,
                "qualifiers": True,
                "fallback_lang": "any",
                "format": format,
            }
            headers = {"User-Agent": "Wikidata Vector Database (embedding@wikimedia.de)"}

            url_textifier = settings.WD_TEXTIFIER_API
            results = requests.get(url_textifier, params=params, headers=headers)
            results.raise_for_status()
            text.update(results.json())

        # Limit the length of the text
        text = {
            id: value.strip()[:max_length] for id, value in text.items() if isinstance(value, str) and value.strip()
        }
        return text

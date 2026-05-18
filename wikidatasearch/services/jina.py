"""Jina AI integration for the FastAPI application."""

import base64
from typing import List

import numpy as np
import requests


class JinaAIAPI:
    """Handles interactions with the Jina AI API."""

    def __init__(
        self,
        api_key: str,
        passage_task: str = "retrieval.passage",
        query_task: str = "retrieval.query",
        embedding_dim: int = 512,
    ):
        """Initialize the Jina API client wrapper.

        Args:
            api_key (str): Jina API key.
            passage_task (str): Task identifier for embedding documents.
            query_task (str): Task identifier for embedding queries.
            embedding_dim (int): Dimensionality of generated embeddings. Defaults to 512.
        """
        self.api_key = api_key
        self.passage_task = passage_task
        self.query_task = query_task
        self.embedding_dim = embedding_dim

    def api_embed(self, texts: str | List[str], task: str = "retrieval.query") -> List[List[float]]:
        """Generate embeddings using the Jina embeddings API.

        Args:
            texts (str | List[str]): Input text or list of texts to embed.
            task (str): Task identifier such as `retrieval.query` or `retrieval.passage`.

        Returns:
            List[List[float]]: One embedding vector per input text.
        """
        url = "https://api.jina.ai/v1/embeddings"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

        if type(texts) is str:
            texts = [texts]

        data = {
            "model": "jina-embeddings-v3",
            "dimensions": self.embedding_dim,
            "embedding_type": "base64",
            "task": task,
            "late_chunking": False,
            "input": texts,
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Ensure request was successful
        response_data = response.json()

        embeddings = []
        for item in response_data["data"]:
            binary_data = base64.b64decode(item["embedding"])
            embedding_array = np.frombuffer(binary_data, dtype="<f4")  # Ensure float32 format
            embeddings.append(embedding_array.tolist())

        return embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for document (passage) texts.

        Args:
            texts (List[str]): Document texts to embed.

        Returns:
            List[List[float]]: Embedding vectors corresponding to input documents.
        """
        embeddings = self.api_embed(texts, task=self.passage_task)
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Generate an embedding for a single query string.

        Args:
            text (str): Query text to embed.

        Returns:
            List[float]: Embedding vector corresponding to the query.
        """
        embedding = self.api_embed([text], task=self.query_task)[0]
        return embedding

    def api_rerank(self, query: str, texts: str | List[str]) -> List[dict]:
        """Rerank documents for a query using the Jina reranker API.

        Args:
            query (str): User query to rank documents against.
            texts (str | List[str]): Candidate document texts.

        Returns:
            List[dict]: Jina reranker results with score and index metadata.
        """
        url = "https://api.jina.ai/v1/rerank"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}

        if type(texts) is str:
            texts = [texts]

        data = {
            "model": "jina-reranker-v2-base-multilingual",
            "query": query,
            "return_documents": False,
            "documents": texts,
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Ensure request was successful
        response_data = response.json()

        return response_data["results"]

    def rerank(self, query: str, docs: List[dict]) -> List[dict]:
        """Score and sort documents by relevance to the query.

        Args:
            query (str): User query text.
            docs (List[dict]): Documents containing a `text` field.

        Returns:
            List[dict]: Input documents sorted by descending `reranker_score`.
        """
        texts = [doc["text"] for doc in docs]
        scores = self.api_rerank(query, texts)
        for score in scores:
            docs[score["index"]]["reranker_score"] = score["relevance_score"]

        docs.sort(key=lambda x: x["reranker_score"], reverse=True)
        return docs

    def similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute a clamped dot product between two vectors.

        Args:
            vec1 (List[float]): The first vector.
            vec2 (List[float]): The second vector.

        Returns:
            float: max(0.0, dot(vec1, vec2)).
        """
        return max(0.0, (np.dot(vec1, vec2) + 1.0) / 2.0)

"""
app/rag/retriever.py
Semantic search over job listings stored in ChromaDB
"""
import json
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from google import genai

from app.config import get_settings
from app.logger import setup_logger

log = setup_logger("rag.retriever")
settings = get_settings()


class JobRetriever:
    _instance: "JobRetriever | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._genai_client = genai.Client(api_key=settings.gemini_api_key)
        client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._col = client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        self._initialized = True
        log.info(f"Retriever ready — {self._col.count()} documents in collection")

    def _embed_query(self, text: str) -> list[float]:
        result = self._genai_client.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=text,
        )
        return result.embeddings[0].values

    def search(
        self,
        query: str,
        n_results: int = 5,
        salary_min: int | None = None,
        salary_max: int | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search with optional salary filter"""
        where: dict = {}
        if salary_min is not None:
            where["salary_max"] = {"$gte": salary_min}
        if salary_max is not None:
            where["salary_min"] = {"$lte": salary_max}

        query_embedding = self._embed_query(query)

        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, max(self._col.count(), 1)),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self._col.query(**kwargs)

        jobs = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            jobs.append(
                {
                    "description": doc,
                    "title":       meta.get("title", ""),
                    "company":     meta.get("company", ""),
                    "location":    meta.get("location", ""),
                    "salary_min":  meta.get("salary_min", 0),
                    "salary_max":  meta.get("salary_max", 0),
                    "skills":      json.loads(meta.get("skills", "[]")),
                    "url":         meta.get("url", ""),
                    "relevance":   round(1 - dist, 3),
                }
            )

        log.info(f"search query='{query}' returned {len(jobs)} results")
        return jobs

    def count(self) -> int:
        return self._col.count()

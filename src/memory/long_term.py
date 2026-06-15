"""Long-term memory using ChromaDB for persistent knowledge storage."""

import os
import hashlib
from pathlib import Path
from typing import Optional
from src.config.settings import settings


class SimpleEmbedder:
    """Lightweight text embedder using character n-gram hashing.

    Used as a fallback when no embedding API is available. Not as accurate
    as transformer embeddings but works without external dependencies.
    """

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        """Generate a simple hash-based embedding."""
        vec = [0.0] * self.dim
        text_lower = text.lower()

        # Character trigram hashing
        for i in range(len(text_lower) - 2):
            trigram = text_lower[i:i + 3]
            h = int(hashlib.md5(trigram.encode()).hexdigest(), 16)
            idx = h % self.dim
            vec[idx] += 1.0

        # Normalize
        total = sum(vec)
        if total > 0:
            vec = [v / total for v in vec]

        return vec


class LongTermMemory:
    """Long-term memory backed by ChromaDB with semantic search capabilities.

    Stores code patterns and project knowledge for retrieval across sessions.
    """

    def __init__(self, persist_dir: Optional[str] = None):
        self._persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._embedder = SimpleEmbedder()

        try:
            import chromadb
            os.makedirs(self._persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self._persist_dir)
            self._chroma_available = True
        except ImportError:
            self._client = None
            self._chroma_available = False

        self._collections: dict[str, object] = {}

    def _get_or_create_collection(self, name: str) -> Optional[object]:
        """Get or create a ChromaDB collection."""
        if not self._chroma_available or self._client is None:
            return None

        if name not in self._collections:
            safe_name = name.replace(" ", "_").replace("-", "_")
            try:
                self._collections[name] = self._client.get_or_create_collection(
                    name=safe_name,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception:
                return None

        return self._collections[name]

    def store(self, collection: str, text: str, metadata: Optional[dict] = None) -> bool:
        """Store a text entry with vector embedding.

        Args:
            collection: Collection name (e.g., 'code_patterns', 'project_knowledge').
            text: The text content to store.
            metadata: Optional metadata dict.

        Returns:
            True if stored successfully, False otherwise.
        """
        coll = self._get_or_create_collection(collection)
        if coll is None:
            return False

        embedding = self._embedder.embed(text)
        doc_id = hashlib.md5(text.encode()).hexdigest()[:16]

        try:
            coll.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata or {}],
            )
            return True
        except Exception:
            return False

    def search(self, collection: str, query: str, k: int = 5) -> list[dict]:
        """Semantic search for similar entries.

        Args:
            collection: Collection name to search in.
            query: Search query text.
            k: Number of results to return.

        Returns:
            List of result dicts with 'content', 'metadata', and 'score' keys.
        """
        coll = self._get_or_create_collection(collection)
        if coll is None:
            return []

        query_embedding = self._embedder.embed(query)

        try:
            results = coll.query(
                query_embeddings=[query_embedding],
                n_results=min(k, 10),
            )

            output = []
            if results.get("documents") and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    item = {"content": doc, "metadata": {}, "score": 0.0}
                    if results.get("metadatas") and results["metadatas"][0]:
                        item["metadata"] = results["metadatas"][0][i] or {}
                    if results.get("distances") and results["distances"][0]:
                        item["score"] = 1.0 - results["distances"][0][i]
                    output.append(item)

            return output
        except Exception:
            return []

    def add_code_pattern(self, pattern: str, language: str, description: str) -> bool:
        """Store a reusable code pattern.

        Args:
            pattern: The code snippet.
            language: Programming language.
            description: What the pattern does.

        Returns:
            True if stored successfully.
        """
        return self.store(
            "code_patterns",
            f"# {description}\n```{language}\n{pattern}\n```",
            {"language": language, "description": description},
        )

    def add_project_knowledge(self, topic: str, content: str) -> bool:
        """Store project-level domain knowledge.

        Args:
            topic: Knowledge topic/category.
            content: The knowledge content.

        Returns:
            True if stored successfully.
        """
        return self.store(
            "project_knowledge",
            f"## {topic}\n{content}",
            {"topic": topic},
        )

    def get_related_code(self, query: str, k: int = 3) -> list[dict]:
        """Search for code patterns related to a query.

        Args:
            query: Natural language description of what you're looking for.
            k: Number of results.

        Returns:
            List of matching code patterns.
        """
        return self.search("code_patterns", query, k=k)

    def get_project_context(self, query: str, k: int = 3) -> list[dict]:
        """Search project knowledge base.

        Args:
            query: Search query.
            k: Number of results.

        Returns:
            List of matching knowledge entries.
        """
        return self.search("project_knowledge", query, k=k)

    def clear_collection(self, name: str) -> bool:
        """Delete all entries in a collection."""
        if not self._chroma_available or self._client is None:
            return False
        safe_name = name.replace(" ", "_").replace("-", "_")
        try:
            self._client.delete_collection(safe_name)
            self._collections.pop(name, None)
            return True
        except Exception:
            return False

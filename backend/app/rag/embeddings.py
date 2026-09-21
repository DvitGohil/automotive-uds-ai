"""
Embedding generation, provider-configurable via settings.EMBEDDING_PROVIDER.

- "hash": deterministic, offline, no model download — safe default for the
  pilot/tests in this sandbox (no network access to model hubs here).
- "sentence_transformers": real local embedding model (e.g. BGE/E5), used
  when a model has actually been downloaded/available in the deployment
  environment. Imported lazily so it's never required just to run tests.
"""
import hashlib
from abc import ABC, abstractmethod

from app.core.config import settings


class EmbeddingProviderError(Exception):
    pass


class EmbeddingProvider(ABC):
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text, in order."""


class HashEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic, dependency-free pseudo-embedding: derives a fixed-length
    unit vector from a SHA-256 hash of the text. Same text -> same vector,
    always. Not semantically meaningful — intended for pilot/offline use and
    automated testing, not for production-quality retrieval.
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def _embed_one(self, text: str) -> list[float]:
        vector: list[float] = []
        counter = 0
        while len(vector) < self.dimension:
            digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
            vector.extend(byte / 255.0 - 0.5 for byte in digest)
            counter += 1
        vector = vector[: self.dimension]
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Real local embedding model via sentence-transformers. Requires the model
    to be available (downloaded) in the deployment environment."""

    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer  # lazy import
        except ImportError as exc:
            raise EmbeddingProviderError(
                "EMBEDDING_PROVIDER=sentence_transformers requires the 'sentence-transformers' package "
                "(see requirements.txt) and network access to download the model on first use. "
                f"Import failed: {exc}"
            ) from exc

        try:
            self._model = SentenceTransformer(model_name)
        except Exception as exc:  # noqa: BLE001 — surface any load/download failure with a clear message
            raise EmbeddingProviderError(
                f"Failed to load embedding model {model_name!r} for EMBEDDING_PROVIDER=sentence_transformers: {exc}"
            ) from exc
        self.dimension = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()


def get_embedding_provider() -> EmbeddingProvider:
    provider = settings.EMBEDDING_PROVIDER
    if provider == "hash":
        return HashEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
    if provider == "sentence_transformers":
        return SentenceTransformerEmbeddingProvider(settings.EMBEDDING_MODEL)
    raise EmbeddingProviderError(f"Unknown EMBEDDING_PROVIDER: {provider!r}. Supported: hash, sentence_transformers")

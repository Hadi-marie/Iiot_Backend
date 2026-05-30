from __future__ import annotations

import threading
from pathlib import Path

from .config import settings
from .text_normalize import normalize

_provider = None
_lock = threading.Lock()


# --------------------------------------------------------------------------------------
# TF-IDF + LSA provider (fully offline, no model download). Default provider.
# --------------------------------------------------------------------------------------
class TfidfEmbedder:
    """TF-IDF (word 1-2 grams + char_wb 3-5 grams) reduced with TruncatedSVD (LSA).

    Produces dense, L2-normalized vectors suitable for cosine similarity in Qdrant.
    Works for Arabic and English thanks to Arabic-aware normalization and char n-grams.
    """

    def __init__(self, n_components: int = 256):
        self.n_components = n_components
        self.pipeline = None
        self._dim = n_components

    def _build(self, n_docs: int):
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import FeatureUnion, Pipeline
        from sklearn.preprocessing import Normalizer

        word_vec = TfidfVectorizer(
            preprocessor=normalize, analyzer="word", ngram_range=(1, 2),
            min_df=1, sublinear_tf=True,
        )
        char_vec = TfidfVectorizer(
            preprocessor=normalize, analyzer="char_wb", ngram_range=(3, 5),
            min_df=1, sublinear_tf=True,
        )
        union = FeatureUnion([("word", word_vec), ("char", char_vec)])
        n_comp = max(2, min(self.n_components, n_docs - 1))
        svd = TruncatedSVD(n_components=n_comp, random_state=42)
        norm = Normalizer(copy=False)
        self._dim = n_comp
        return Pipeline([("features", union), ("svd", svd), ("normalize", norm)])

    def fit(self, corpus: list[str]) -> "TfidfEmbedder":
        self.pipeline = self._build(len(corpus))
        self.pipeline.fit(corpus)
        return self

    def transform(self, texts: list[str]) -> list[list[float]]:
        if self.pipeline is None:
            raise RuntimeError("TfidfEmbedder is not fitted/loaded yet.")
        return self.pipeline.transform(texts).astype("float32").tolist()

    @property
    def dim(self) -> int:
        return self._dim

    def save(self, path: str) -> None:
        import joblib

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": self.pipeline, "dim": self._dim}, path)

    @classmethod
    def load(cls, path: str) -> "TfidfEmbedder":
        import joblib

        data = joblib.load(path)
        obj = cls()
        obj.pipeline = data["pipeline"]
        obj._dim = data["dim"]
        return obj


class _TfidfProvider:
    def __init__(self):
        self.embedder = TfidfEmbedder.load(settings.tfidf_model_path)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.embedder.transform(texts)

    @property
    def dim(self) -> int:
        return self.embedder.dim


class _OpenAIProvider:
    """OpenAI (or OpenAI-compatible) embeddings. Multilingual, lightweight, no download."""

    def __init__(self):
        if not settings.openai_api_key:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is empty. Set it in backend/.env."
            )
        self.model = settings.openai_embedding_model
        self.base_url = settings.openai_base_url.rstrip("/")
        self.api_key = settings.openai_api_key
        self._dim: int | None = None

    def _request(self, inputs: list[str]) -> list[list[float]]:
        import httpx

        url = f"{self.base_url}/embeddings"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        out: list[list[float]] = []
        # Stay well within request limits by batching.
        for start in range(0, len(inputs), 96):
            chunk = inputs[start : start + 96]
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, headers=headers, json={"model": self.model, "input": chunk})
                resp.raise_for_status()
                data = resp.json()["data"]
            for item in sorted(data, key=lambda d: d["index"]):
                out.append(item["embedding"])
        return out

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._request(texts)

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._dim = len(self._request(["dimension probe"])[0])
        return self._dim


class _SentenceTransformerProvider:
    def __init__(self):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(settings.embedding_model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True,
            show_progress_bar=False, batch_size=32,
        ).tolist()

    @property
    def dim(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())


def get_provider():
    global _provider
    if _provider is None:
        with _lock:
            if _provider is None:
                if settings.embedding_provider == "openai":
                    _provider = _OpenAIProvider()
                elif settings.embedding_provider == "sentence-transformers":
                    _provider = _SentenceTransformerProvider()
                else:
                    _provider = _TfidfProvider()
    return _provider


def reset_provider() -> None:
    global _provider
    _provider = None


def embedding_dim() -> int:
    return get_provider().dim


def embed_texts(texts: list[str]) -> list[list[float]]:
    return get_provider().embed(texts)


def embed_query(text: str) -> list[float]:
    return get_provider().embed([text])[0]


def fit_tfidf_and_save(corpus: list[str]) -> int:
    """Fit the TF-IDF/LSA embedder on the corpus and persist it. Returns the vector dim."""
    embedder = TfidfEmbedder(n_components=settings.tfidf_components).fit(corpus)
    embedder.save(settings.tfidf_model_path)
    reset_provider()
    return embedder.dim

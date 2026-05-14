import os
from functools import lru_cache
from threading import Lock

from sentence_transformers import SentenceTransformer, CrossEncoder

from backend.config.settings import get_settings

settings = get_settings()
_embedding_cache: dict[str, list[float]] = {}
_embedding_lock = Lock()


@lru_cache(maxsize=1)
def model() -> SentenceTransformer:
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
    try:
        # BGE-small is highly efficient and optimized for retrieval tasks
        return SentenceTransformer('BAAI/bge-small-en-v1.5')
    except Exception as exc:
        logger.warning(f"[EMBEDDINGS] BGE failed, falling back to MiniLM: {exc}")
        return SentenceTransformer('all-MiniLM-L6-v2')


@lru_cache(maxsize=1)
def reranker_model() -> CrossEncoder:
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
    try:
        return CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
    except Exception as exc:
        raise RuntimeError("Reranker model is unavailable.") from exc


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    with _embedding_lock:
        missing = [text for text in texts if text not in _embedding_cache]
    if missing:
        vectors = model().encode(missing, normalize_embeddings=True, batch_size=32)
        with _embedding_lock:
            for text, vector in zip(missing, vectors):
                _embedding_cache[text] = vector.tolist()

    with _embedding_lock:
        return [_embedding_cache[text] for text in texts]

def rerank(query: str, texts: list[str]) -> list[float]:
    if not texts:
        return []
    model_instance = reranker_model()
    scores = model_instance.predict([(query, text) for text in texts])
    return scores.tolist()

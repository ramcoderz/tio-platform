import os
from functools import lru_cache
from threading import Lock

from sentence_transformers import SentenceTransformer, CrossEncoder

from backend.config.settings import get_settings

settings = get_settings()
_embedding_cache: dict[str, list[float]] = {}
_embedding_lock = Lock()
from backend.utils.console import console
import time
import logging
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def model() -> SentenceTransformer:
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
    try:
        logger.info("[EMBEDDINGS] Initializing primary embedding model: BAAI/bge-small-en-v1.5")
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
        logger.info("[EMBEDDINGS] Initializing reranker model: cross-encoder/ms-marco-MiniLM-L-6-v2")
        return CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
    except Exception as exc:
        raise RuntimeError("Reranker model is unavailable.") from exc

def preload_models():
    """Global preload to avoid repeating initialization."""
    logger.info("[SYSTEM] Preloading AI models...")
    model()
    if not getattr(settings, 'stabilization_mode', False):
        reranker_model()
    logger.info("[SYSTEM] Preload complete.")


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    with _embedding_lock:
        missing = [text for text in texts if text not in _embedding_cache]
    if missing:
        start_time = time.monotonic()
        try:
            vectors = model().encode(missing, normalize_embeddings=True, batch_size=32)
            duration = time.monotonic() - start_time
            rate = len(missing) / max(duration, 0.1)
            console.info(f"Embedded {len(missing)} chunks in {duration:.1f}s ({rate:.1f} chunks/s)", stage="EMBEDDING")
        except Exception as e:
            console.error(f"Embedding failure: {e}", stage="EMBEDDING")
            raise
        with _embedding_lock:
            for text, vector in zip(missing, vectors):
                _embedding_cache[text] = vector.tolist()

    with _embedding_lock:
        return [_embedding_cache[text] for text in texts]

def rerank(query: str, texts: list[str]) -> list[float]:
    if not texts:
        return []
    if getattr(settings, 'stabilization_mode', False):
        # Skip reranking during stabilization
        return [1.0] * len(texts)
        
    model_instance = reranker_model()
    scores = model_instance.predict([(query, text) for text in texts])
    return scores.tolist()

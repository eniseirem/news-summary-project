from __future__ import annotations

from typing import List, Union, Iterable, Optional
from threading import Lock

import numpy as np
from sentence_transformers import SentenceTransformer


# Global model cache, similar to your BART summarizer
_model_lock = Lock()
_embedding_model: Optional[SentenceTransformer] = None
 

def _get_embedding_model(
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    device: Optional[str] = None,
) -> SentenceTransformer:
    """
    Lazily load and cache the SBERT model.

    Parameters
    ----------
    model_name : str
        Name of the SBERT model to load.
    device : str | None
        Device to use: "cpu", "cuda", "cuda:0". Defaults to CPU if None.

    Returns
    -------
    SentenceTransformer
        Loaded and cached SBERT model.
    """
    global _embedding_model

    if _embedding_model is None:
        with _model_lock:
            if _embedding_model is None:
                _embedding_model = SentenceTransformer(
                    model_name,
                    device=device or "cpu",
                )
    return _embedding_model


def _chunk_text_words(
    text: str,
    max_words: int = 220,
    overlap_words: int = 40,
) -> List[str]:
    """
    Split a long text into overlapping word-based chunks.

    This helps to avoid losing information when encoding
    very long documents with SBERT.

    Parameters
    ----------
    text : str
        Raw input text.
    max_words : int
        Maximum number of words per chunk.
    overlap_words : int
        Number of words to overlap between chunks.

    Returns
    -------
    List[str]
        List of text chunks.
    """
    words = text.split()
    n = len(words)

    if n == 0:
        return []

    if n <= max_words:
        return [" ".join(words)]

    chunks: List[str] = []
    start = 0

    while start < n:
        end = min(start + max_words, n)
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))

        if end == n:
            break

        # Move the start forward but keep some overlap
        start = end - overlap_words

    return chunks


def _encode_single(
    text: str,
    model: SentenceTransformer,
    max_words: int,
    overlap_words: int,
    normalize: bool,
) -> np.ndarray:
    """
    Encode a single document.

    Steps:
    1. Return zero vector for empty text
    2. Chunk long text into overlapping word windows
    3. Encode each chunk with SBERT
    4. Average all chunk embeddings
    5. Optionally normalize the final vector

    Parameters
    ----------
    text : str
        Single document as a string.
    model : SentenceTransformer
        Loaded SBERT model.
    max_words : int
        Maximum words per chunk.
    overlap_words : int
        Number of overlapping words between chunks.
    normalize : bool
        If True, apply L2 normalization to the final embedding.

    Returns
    -------
    np.ndarray
        Embedding vector of shape (embedding_dim,).
    """
    cleaned = text.strip()
    if not cleaned:
        dim = model.get_sentence_embedding_dimension()
        if dim is None:
            raise ValueError("Model embedding dimension is None")
        return np.zeros(int(dim), dtype=np.float32)

    chunks = _chunk_text_words(
        cleaned,
        max_words=max_words,
        overlap_words=overlap_words,
    )

    if not chunks:
        dim = model.get_sentence_embedding_dimension()
        if dim is None:
            raise ValueError("Model embedding dimension is None")
        return np.zeros(int(dim), dtype=np.float32)

    # Encode all chunks
    chunk_embeddings = model.encode(
        chunks,
        convert_to_numpy=True,
        normalize_embeddings=normalize,
        batch_size=32,
        show_progress_bar=False,
    )

    # Average chunk embeddings
    emb = np.mean(chunk_embeddings, axis=0)

    if normalize:
        # Re-normalize after averaging to keep uniform vector norms
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

    return emb.astype(np.float32)


def encode(
    texts: Union[str, Iterable[str]],
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    device: Optional[str] = None,
    max_words: int = 220,
    overlap_words: int = 40,
    normalize: bool = True,
) -> np.ndarray:
    """
    Main function for computing SBERT embeddings.

    Accepts either a single text or an iterable of texts and returns
    an array of shape (n_samples, embedding_dim).

    Parameters
    ----------
    texts : str | Iterable[str]
        Single text or a list/iterable of texts to encode.
    model_name : str
        SBERT model name.
    device : str | None
        Device on which to run the model.
    max_words : int
        Maximum words per chunk for long documents.
    overlap_words : int
        Overlap between chunks.
    normalize : bool
        Whether embeddings should be L2 normalized.

    Returns
    -------
    np.ndarray
        2D array of embeddings.
    """
    model = _get_embedding_model(model_name=model_name, device=device)

    # Convert input to list
    if isinstance(texts, str):
        text_list = [texts]
    else:
        text_list = list(texts)

    if not text_list:
        dim = model.get_sentence_embedding_dimension()
        if dim is None:
            raise ValueError("Model embedding dimension is None")
        dim_int: int = int(dim)
        return np.zeros(shape=(0, dim_int), dtype=np.float32)

    embeddings: List[np.ndarray] = []

    for t in text_list:
        emb = _encode_single(
            text=t,
            model=model,
            max_words=max_words,
            overlap_words=overlap_words,
            normalize=normalize,
        )
        embeddings.append(emb)

    return np.vstack(embeddings)

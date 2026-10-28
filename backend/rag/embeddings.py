"""Generación de embeddings (OpenAI opcional o hash local determinista)."""

import hashlib
import json

import numpy as np

from app.core.config import settings


def embed_text(text: str) -> list[float]:
    if settings.openai_api_key:
        try:
            return _openai_embed(text)
        except Exception:
            pass
    return _local_embed(text, settings.embedding_dimensions)


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [embed_text(t) for t in texts]


def _local_embed(text: str, dim: int) -> list[float]:
    vec = np.zeros(dim, dtype=np.float32)
    for token in text.lower().split():
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        idx = int(digest, 16) % dim
        vec[idx] += 1.0
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec.tolist()


def _openai_embed(text: str) -> list[float]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        dimensions=settings.embedding_dimensions,
    )
    return response.data[0].embedding


def embedding_to_json(vec: list[float]) -> str:
    return json.dumps(vec)

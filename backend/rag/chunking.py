"""Segmentación de texto para indexación RAG (LangChain + fallback nativo)."""

import re

_WHITESPACE = re.compile(r"\s+")


def _chunk_text_native(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    normalized = _WHITESPACE.sub(" ", text).strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            split_at = normalized.rfind(" ", start, end)
            if split_at > start:
                end = split_at
        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> list[str]:
    """Fragmenta texto con LangChain RecursiveCharacterTextSplitter (RNF-27)."""
    normalized = _WHITESPACE.sub(" ", text).strip()
    if not normalized:
        return []
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        parts = [p.strip() for p in splitter.split_text(normalized) if p.strip()]
        if parts:
            return parts
    except Exception:
        pass
    return _chunk_text_native(normalized, chunk_size=chunk_size, overlap=overlap)


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))

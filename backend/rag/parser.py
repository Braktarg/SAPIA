"""Extracción de texto desde PDF con PyMuPDF."""

from pathlib import Path

import fitz


class PdfParseError(Exception):
    pass


def extract_text_from_pdf(path: Path, max_pages: int) -> tuple[str, int]:
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise PdfParseError(f"No se pudo abrir el PDF: {exc}") from exc

    try:
        page_count = doc.page_count
        if page_count > max_pages:
            raise PdfParseError(f"El PDF supera el máximo de {max_pages} páginas ({page_count})")

        parts: list[str] = []
        for i in range(page_count):
            text = doc.load_page(i).get_text("text").strip()
            if text:
                parts.append(text)
        full_text = "\n\n".join(parts).strip()
        if not full_text:
            raise PdfParseError("El PDF no contiene texto extraíble")
        return full_text, page_count
    finally:
        doc.close()

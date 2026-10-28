"""Exportar recomendación a PDF para reuniones PIE."""

from io import BytesIO

import fitz

from app.models import Recommendation, User


def build_recommendation_pdf(rec: Recommendation, student_name: str, teacher_name: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    margin = 50
    y = 60
    line_h = 16

    def writeln(text: str, size: int = 11, bold: bool = False) -> None:
        nonlocal y, page
        font = "hebo" if bold else "helv"
        for line in text.split("\n"):
            if y > 780:
                page = doc.new_page(width=595, height=842)
                y = margin
            page.insert_text((margin, y), line[:110], fontsize=size, fontname=font)
            y += line_h if size <= 11 else line_h + 4

    writeln("SAPIA — Recomendación pedagógica", 14, True)
    writeln(f"Estudiante: {student_name}")
    writeln(f"Docente: {teacher_name}")
    writeln(f"Tema: {rec.planning_topic}")
    writeln(f"Estado: {rec.status}")
    y += 8
    writeln(rec.title, 12, True)
    y += 4
    writeln("Actividad propuesta", 11, True)
    writeln(rec.body)
    y += 8
    writeln("¿Por qué esta sugerencia?", 11, True)
    writeln(rec.explanation)
    y += 12
    writeln("Documento generado por SAPIA — La IA propone; el docente dispone.", 9)

    buf = BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

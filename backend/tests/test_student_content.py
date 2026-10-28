"""Tests unitarios para transformaciones de contenido estudiante."""

from app.utils.student_content import grade_level_prompt_line, simplify_explanation_for_student


def test_grade_level_prompt_line_with_value():
    line = grade_level_prompt_line("8° básico")
    assert "8° básico" in line
    assert "Adapta vocabulario" in line


def test_grade_level_prompt_line_default():
    line = grade_level_prompt_line(None)
    assert "educación básica chilena" in line


def test_simplify_explanation_strips_rag_citations():
    raw = (
        "¿Por qué esta recomendación?\n"
        "- Atención sostenida: 72%\n"
        "[1] Fragmento del PDF curricular\n"
        "Fragmentos curriculares recuperados:\n"
        "Texto técnico que no debe verse."
    )
    out = simplify_explanation_for_student(raw)
    assert "[1]" not in out
    assert "Fragmentos curriculares" not in out
    assert "atención sostenida" in out.lower()


def test_simplify_explanation_empty_fallback():
    assert "docente" in simplify_explanation_for_student("").lower()

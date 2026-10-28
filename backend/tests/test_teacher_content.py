from app.utils.teacher_content import (
    compact_teacher_explanation_for_chain,
    sanitize_teacher_explanation,
)


def test_sanitize_teacher_explanation_strips_technical_footer():
    raw = (
        "¿Por qué se sugiere?\n"
        "Tabla de evidencia.\n\n"
        "(Modo degradado: motor de plantilla activo — configure OPENAI_API_KEY para generación LLM ampliada.)"
    )
    out = sanitize_teacher_explanation(raw)
    assert "OPENAI_API_KEY" not in out
    assert "Tabla de evidencia" in out


def test_compact_teacher_explanation_strips_duplicate_table():
    raw = (
        "¿Por qué se sugiere?\n"
        "Resumen breve.\n\n"
        "Cadena de evidencia (perfil + curricular → decisión):\n\n"
        "| Evidencia encontrada | Decisión pedagógica |\n"
        "| --- | --- |\n"
        "| OA | Actividad |\n\n"
        "Fragmentos curriculares citados:\n[1] Unidad..."
    )
    out = compact_teacher_explanation_for_chain(raw)
    assert "| Evidencia" not in out
    assert "Resumen breve" in out
    assert "Fragmentos" not in out


def test_sanitize_with_evidence_chain_compacts_legacy_explanation():
    raw = (
        "¿Por qué se sugiere?\n"
        "Narrativa.\n\n"
        "| Evidencia encontrada | Decisión pedagógica |\n"
        "| --- | --- |\n"
        "| x | y |"
    )
    out = sanitize_teacher_explanation(raw, has_evidence_chain=True)
    assert "| Evidencia" not in out
    assert "Narrativa" in out

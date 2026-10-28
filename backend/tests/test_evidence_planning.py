from tests.consent_helpers import AI_CONSENT, DIAG_CONSENT
"""Tests del motor de evidencia pedagógica."""

from rag.evidence_planning import (
    StudentProfileSnapshot,
    build_course_evidence_package,
    build_student_evidence_package,
    build_teacher_narrative_explanation,
    extract_curricular_anchor,
    resolve_generation_context,
)
from rag.retrieve import RetrievedChunk


def _chunk(text: str, unit: str = "Ecuaciones Lineales", cid: int = 1) -> RetrievedChunk:
    return RetrievedChunk(id=cid, document_id=1, unit_name=unit, content=text, score=0.92)


def test_extract_oa_from_pdf_chunk():
    anchor = extract_curricular_anchor(
        [
            _chunk(
                "MATEMÁTICA 8° BÁSICO. Objetivo de aprendizaje (OA): Resolver ecuaciones lineales "
                "de la forma ax + b = c. Recta numérica y despeje."
            )
        ],
        "Ecuaciones lineales",
    )
    assert "ecuaciones lineales" in anchor.oa.lower()
    assert anchor.unit_name == "Ecuaciones Lineales"
    assert "recta" in anchor.main_activity.lower() or "despeje" in anchor.main_activity.lower()


def test_resolve_topic_conflict_quadratic_vs_linear():
    from rag.evidence_planning import resolve_generation_context

    ctx = resolve_generation_context(
        "Ecuaciones cuadráticas",
        [
            _chunk(
                "MATEMÁTICA 8°. Objetivo de aprendizaje (OA): Resolver ecuaciones lineales "
                "de la forma ax + b = c.",
                unit="Ecuaciones Lineales",
            )
        ],
    )
    assert ctx.topic_aligned is False
    assert ctx.canonical_topic == "Ecuaciones Lineales"
    assert "no coincide" in (ctx.alignment_note or "").lower()


def test_student_evidence_includes_all_descriptors_with_scores():
    profiles = [
        {
            "key": "comprension_lectora",
            "label": "Comprensión lectora",
            "value": 1.0,
        },
        {
            "key": "preferencia_visual",
            "label": "Preferencia visual",
            "value": 0.8,
        },
        {
            "key": "razonamiento_logico",
            "label": "Razonamiento lógico",
            "value": 0.55,
        },
    ]
    pkg = build_student_evidence_package(
        planning_topic="Ecuaciones cuadráticas",
        student_name="Antonia Vega",
        student_id=1,
        descriptors=profiles,
        chunks=[_chunk("OA: Resolver ecuaciones lineales ax+b=c", unit="Ecuaciones Lineales")],
    )
    assert len(pkg.evidence_chain["descriptor_scores"]) == 3
    assert pkg.evidence_chain["topic_alignment"]["canonical_topic"] == "Ecuaciones Lineales"
    assert any("Comprensión lectora" in r.evidence for r in pkg.rows)
    assert any("Preferencia visual" in r.evidence for r in pkg.rows)


def test_course_evidence_package_has_table_and_tiers():
    profiles = [
        StudentProfileSnapshot(
            student_id=1,
            student_name="Ana",
            descriptors=[
                {"key": "preferencia_visual", "label": "Preferencia visual", "value": 0.3},
                {"key": "comprension_lectora", "label": "Comprensión lectora", "value": 0.8},
            ],
            profile_version=1,
        ),
        StudentProfileSnapshot(
            student_id=2,
            student_name="Luis",
            descriptors=[
                {"key": "regulacion_emocional", "label": "Regulación emocional", "value": 0.35},
                {"key": "razonamiento_logico", "label": "Razonamiento lógico", "value": 0.75},
            ],
            profile_version=1,
        ),
    ]
    pkg = build_course_evidence_package(
        planning_topic="Ecuaciones lineales",
        course_name="8° A",
        student_profiles=profiles,
        chunks=[_chunk("OA: Resolver ecuaciones. Glosario: incógnita, despeje.")],
    )
    assert "| Evidencia encontrada | Decisión pedagógica |" in pkg.explanation_table
    assert len(pkg.evidence_chain["steps"]) >= 4
    assert "Ana" in str(pkg.evidence_chain["tier_assignment"])
    assert any("Ana" in a["student_name"] for a in pkg.student_adaptations)


def test_student_evidence_rows_include_rationale():
    pkg = build_student_evidence_package(
        planning_topic="Ecuaciones cuadráticas",
        student_name="Antonia Vega",
        student_id=1,
        descriptors=[
            {"key": "razonamiento_logico", "label": "Razonamiento lógico", "value": 0.45},
        ],
        chunks=[_chunk("OA: Resolver ecuaciones lineales ax+b=c", unit="Ecuaciones Lineales")],
    )
    logic_row = next(
        r for r in pkg.evidence_chain["evidence_rows"] if r.get("descriptor_key") == "razonamiento_logico"
    )
    assert logic_row["rationale"]
    assert "0.45" in logic_row["rationale"]
    assert "por debajo" in logic_row["rationale"].lower()


def test_teacher_narrative_excludes_markdown_table():
    pkg = build_student_evidence_package(
        planning_topic="Ecuaciones lineales",
        student_name="Ana",
        student_id=1,
        descriptors=[{"key": "autonomia", "label": "Autonomía en tarea", "value": 0.7}],
        chunks=[_chunk("OA: Resolver ecuaciones lineales", unit="Ecuaciones Lineales")],
    )
    gen_ctx = resolve_generation_context(
        "Ecuaciones lineales",
        [_chunk("OA: Resolver ecuaciones lineales", unit="Ecuaciones Lineales")],
    )
    narrative = build_teacher_narrative_explanation(pkg, gen_ctx, student_name="Ana")
    assert "| Evidencia encontrada |" not in narrative
    assert "cadena de evidencia" in narrative.lower()
    assert pkg.evidence_chain.get("profile_synthesis") is not None
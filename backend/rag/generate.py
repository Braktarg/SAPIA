"""Generación de recomendaciones pedagógicas (LLM opcional + fallback template)."""

import logging
import re
from dataclasses import dataclass

from app.core.config import settings
from app.utils.student_content import grade_level_prompt_line
from rag.evidence_planning import (
    StudentProfileSnapshot,
    apply_topic_alignment_to_body,
    body_conflicts_with_curricular,
    build_course_evidence_package,
    build_student_evidence_package,
    build_teacher_narrative_explanation,
    format_named_adaptations,
    format_tier_block,
    resolve_generation_context,
    _student_math_adaptation_lines,
)
from rag.retrieve import RetrievedChunk

STRENGTH_THRESHOLD = 0.62
SUPPORT_THRESHOLD = 0.45
LLM_MAX_TOKENS_STUDENT = 2200
LLM_MAX_TOKENS_COURSE = 2800

logger = logging.getLogger(__name__)


@dataclass
class GeneratedRecommendation:
    title: str
    body: str
    explanation: str
    degraded_mode: bool
    evidence_chain: dict | None = None


def generate_recommendation(
    *,
    planning_topic: str,
    descriptors: list[dict],
    chunks: list[RetrievedChunk],
    student_name: str,
    grade_level: str | None = None,
    student_id: int = 0,
) -> GeneratedRecommendation:
    if settings.openai_api_key:
        try:
            result = _openai_generate_student(
                planning_topic, descriptors, chunks, student_name, grade_level, student_id=student_id
            )
            return _finalize_student_result(
                result, planning_topic, student_name, student_id, descriptors, chunks, grade_level
            )
        except Exception as exc:
            logger.exception("OpenAI student generation failed, using template: %s", exc)
    logger.warning("Student recommendation in template mode (no API key or LLM failure)")
    return _template_generate_student(
        planning_topic, descriptors, chunks, student_name, grade_level, student_id=student_id
    )


def generate_course_recommendation(
    *,
    planning_topic: str,
    course_name: str,
    student_profiles: list[StudentProfileSnapshot],
    chunks: list[RetrievedChunk],
    grade_level: str | None = None,
) -> GeneratedRecommendation:
    if settings.openai_api_key:
        try:
            result = _openai_generate_course(
                planning_topic, course_name, student_profiles, chunks, grade_level
            )
            return _finalize_course_result(
                result, planning_topic, course_name, student_profiles, chunks, grade_level
            )
        except Exception as exc:
            logger.exception("OpenAI course generation failed, using template: %s", exc)
    logger.warning("Course recommendation in template mode (no API key or LLM failure)")
    return _template_generate_course(
        planning_topic, course_name, student_profiles, chunks, grade_level
    )


def _finalize_student_result(
    result: GeneratedRecommendation,
    planning_topic: str,
    student_name: str,
    student_id: int,
    descriptors: list,
    chunks: list[RetrievedChunk],
    grade_level: str | None = None,
) -> GeneratedRecommendation:
    pkg = build_student_evidence_package(
        planning_topic=planning_topic,
        student_name=student_name,
        student_id=student_id,
        descriptors=descriptors,
        chunks=chunks,
    )
    gen_ctx = resolve_generation_context(planning_topic, chunks)

    if body_conflicts_with_curricular(result.body, pkg.curricular):
        logger.info("Curricular conflict rewrite for %s — using aligned template", student_name)
        template = _template_generate_student(
            planning_topic,
            descriptors,
            chunks,
            student_name,
            grade_level,
            student_id=student_id,
        )
        result.body = template.body
        result.title = template.title
        result.explanation = template.explanation
        result.degraded_mode = True
    else:
        result.body = apply_topic_alignment_to_body(result.body, gen_ctx, pkg.curricular)

    result.explanation = build_teacher_narrative_explanation(
        pkg, gen_ctx, student_name=student_name
    )
    result.evidence_chain = pkg.evidence_chain
    return result


def _finalize_course_result(
    result: GeneratedRecommendation,
    planning_topic: str,
    course_name: str,
    student_profiles: list[StudentProfileSnapshot],
    chunks: list[RetrievedChunk],
    grade_level: str | None = None,
) -> GeneratedRecommendation:
    pkg = build_course_evidence_package(
        planning_topic=planning_topic,
        course_name=course_name,
        student_profiles=student_profiles,
        chunks=chunks,
    )
    gen_ctx = resolve_generation_context(planning_topic, chunks)

    if body_conflicts_with_curricular(result.body, pkg.curricular):
        logger.info("Curricular conflict rewrite for course %s — using aligned template", course_name)
        template = _template_generate_course(
            planning_topic, course_name, student_profiles, chunks, grade_level
        )
        result.body = template.body
        result.title = template.title
        result.explanation = template.explanation
        result.degraded_mode = True
    else:
        result.body = apply_topic_alignment_to_body(result.body, gen_ctx, pkg.curricular)

    result.explanation = build_teacher_narrative_explanation(
        pkg, gen_ctx, course_name=course_name
    )
    result.evidence_chain = pkg.evidence_chain
    return result


def _value_of(d) -> float:
    return d["value"] if isinstance(d, dict) else d.value


def _label_of(d) -> str:
    return d["label"] if isinstance(d, dict) else d.label


def _normalize_descriptors(descriptors: list) -> list[dict]:
    out: list[dict] = []
    for d in descriptors:
        if isinstance(d, dict):
            out.append(
                {
                    "key": d.get("key", ""),
                    "label": _label_of(d),
                    "value": _value_of(d),
                }
            )
        else:
            out.append(
                {
                    "key": getattr(d, "key", ""),
                    "label": _label_of(d),
                    "value": _value_of(d),
                }
            )
    return out


def _top_descriptors(descriptors: list, n: int = 3) -> list[dict]:
    ranked = sorted(_normalize_descriptors(descriptors), key=lambda d: d["value"], reverse=True)
    return ranked[:n]


def _strength_descriptors(descriptors: list) -> list[dict]:
    return [d for d in _normalize_descriptors(descriptors) if d["value"] >= STRENGTH_THRESHOLD]


def _support_descriptors(descriptors: list) -> list[dict]:
    return sorted(
        [d for d in _normalize_descriptors(descriptors) if d["value"] < SUPPORT_THRESHOLD],
        key=lambda d: d["value"],
    )


def _format_descriptor_lines(descriptors: list[dict], *, as_percent: bool = True) -> list[str]:
    lines: list[str] = []
    for d in descriptors:
        if as_percent:
            lines.append(f"- {d['label']}: {int(d['value'] * 100)}%")
        else:
            lines.append(f"- {d['label']}: {d['value']:.2f}")
    return lines


def _format_citations(chunks: list[RetrievedChunk], limit: int = 5) -> list[str]:
    citations: list[str] = []
    for i, chunk in enumerate(chunks[:limit], start=1):
        snippet = chunk.content[:220].rstrip() + ("…" if len(chunk.content) > 220 else "")
        citations.append(f'[{i}] Unidad «{chunk.unit_name}»: "{snippet}"')
    return citations


_SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("title", re.compile(r"^(?:#+\s*)?(?:\*\*)?T[IÍ]TULO(?:\*\*)?\s*:?\s*(.*)$", re.IGNORECASE)),
    ("body", re.compile(r"^(?:#+\s*)?(?:\*\*)?CUERPO(?:\*\*)?\s*:?\s*(.*)$", re.IGNORECASE)),
    (
        "explanation",
        re.compile(r"^(?:#+\s*)?(?:\*\*)?EXPLICACI[OÓ]N(?:\*\*)?\s*:?\s*(.*)$", re.IGNORECASE),
    ),
]


def _match_section_line(line: str) -> tuple[str | None, str]:
    stripped = line.strip()
    for section, pattern in _SECTION_PATTERNS:
        match = pattern.match(stripped)
        if match:
            return section, (match.group(1) or "").strip()
    return None, ""


def _heuristic_split_llm_text(text: str, planning_topic: str) -> tuple[str, str, str]:
    """Último recurso: separar por encabezados tipo «¿Por qué» sin etiquetas TITULO/CUERPO."""
    cleaned = text.strip()
    if len(cleaned) < 200:
        return "", "", ""

    split_markers = [
        r"\n\s*¿Por qué",
        r"\n\s*#{1,3}\s*¿Por qué",
        r"\n\s*EXPLICACI[OÓ]N",
        r"\n\s*#{1,3}\s*EXPLICACI[OÓ]N",
    ]
    for marker in split_markers:
        parts = re.split(marker, cleaned, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and len(parts[0].strip()) >= 150:
            body_part = parts[0].strip()
            explanation_part = parts[1].strip()
            first_line, _, rest = body_part.partition("\n")
            title = first_line.strip().lstrip("#").strip() if len(first_line) < 120 else ""
            body = rest.strip() if title else body_part
            if not title:
                title = f"Planificación — {planning_topic}"
            explanation = explanation_part
            if not explanation.lower().startswith("¿por qué"):
                explanation = "¿Por qué se sugiere?\n" + explanation
            return title, body, explanation

    return "", "", ""


def _template_generate_student(
    planning_topic: str,
    descriptors: list[dict],
    chunks: list[RetrievedChunk],
    student_name: str,
    grade_level: str | None = None,
    student_id: int = 0,
) -> GeneratedRecommendation:
    grade_line = grade_level_prompt_line(grade_level)
    pkg = build_student_evidence_package(
        planning_topic=planning_topic,
        student_name=student_name,
        student_id=student_id,
        descriptors=descriptors,
        chunks=chunks,
    )
    gen_ctx = resolve_generation_context(planning_topic, chunks)
    curricular = pkg.curricular
    canonical = gen_ctx.canonical_topic
    supports = _support_descriptors(descriptors)
    strengths = _strength_descriptors(descriptors) or _top_descriptors(descriptors, 2)
    strength_text = ", ".join(d["label"].lower() for d in strengths[:3]) or "participación guiada"
    support_text = (
        ", ".join(d["label"].lower() for d in supports[:3])
        if supports
        else "apoyos universales de rutina"
    )
    adapt_lines = pkg.student_adaptations[0]["adaptations"] if pkg.student_adaptations else []
    adapt_block = "\n".join(f"- {line}" for line in adapt_lines)

    title = f"Planificación diferenciada — {canonical}"
    intro = ""
    if gen_ctx.alignment_note:
        intro = f"**Alineación curricular:** {gen_ctx.alignment_note}\n\n"

    body = (
        intro
        + f"Propuesta de clase para **{student_name}** sobre «{canonical}» ({grade_line}).\n\n"
        f"**Anclaje curricular (RAG)**\n"
        f"- OA / foco: {curricular.oa}\n"
        f"- Unidad: {curricular.unit_name}\n"
        f"- {curricular.main_activity}\n"
        f"- Conceptos del PDF: {', '.join(curricular.concepts)}.\n\n"
        f"**Objetivos de la sesión**\n"
        f"- Resolver situaciones de «{canonical}» según el OA del material indexado.\n"
        f"- Aplicar despeje, representación visual (recta numérica) y verificación de la solución.\n"
        f"- Ajustar andamiaje según descriptores de {student_name} (ver tabla de evidencia).\n\n"
        f"**Secuencia didáctica**\n\n"
        f"*Inicio (10–15 min)*\n"
        f"1. Agenda visual y activación con fragmento [1] del PDF («{curricular.unit_name}»).\n"
        f"2. Explicitar el OA en lenguaje simple.\n\n"
        f"*Desarrollo (25–30 min)*\n"
        f"1. Modelaje: procedimiento del PDF (despeje paso a paso + recta numérica).\n"
        f"2. Práctica guiada: ejercicios tipo ax + b = c con checklist visible.\n"
        f"3. Verificar cada solución sustituyendo el valor en la ecuación antes de continuar.\n"
        f"4. Adaptaciones matemáticas vinculadas al perfil:\n{adapt_block}\n\n"
        f"*Cierre (10 min)*\n"
        f"1. Ticket de salida: un ejercicio con verificación escrita u oral.\n"
        f"2. Autoevaluación semáforo.\n\n"
        f"**Resumen perfil**\n"
        f"- Fortalezas: {strength_text}.\n"
        f"- Apoyos prioritarios: {support_text}.\n\n"
        f"**Evaluación formativa**\n"
        f"- Rúbrica simple: procedimiento, verificación y comprensión del OA."
    )

    explanation = build_teacher_narrative_explanation(
        pkg, gen_ctx, student_name=student_name
    )
    return GeneratedRecommendation(
        title=title,
        body=body,
        explanation=explanation,
        degraded_mode=True,
        evidence_chain=pkg.evidence_chain,
    )


def _template_generate_course(
    planning_topic: str,
    course_name: str,
    student_profiles: list[StudentProfileSnapshot],
    chunks: list[RetrievedChunk],
    grade_level: str | None = None,
) -> GeneratedRecommendation:
    grade_line = grade_level_prompt_line(grade_level)
    gen_ctx = resolve_generation_context(planning_topic, chunks)
    pkg = build_course_evidence_package(
        planning_topic=planning_topic,
        course_name=course_name,
        student_profiles=student_profiles,
        chunks=chunks,
    )
    curricular = pkg.curricular
    canonical = gen_ctx.canonical_topic
    n = len(student_profiles)
    tier_block = format_tier_block(pkg.tier_a, pkg.tier_b, pkg.tier_c)
    named_block = format_named_adaptations(pkg.student_adaptations)
    intro = ""
    if gen_ctx.alignment_note:
        intro = f"**Alineación curricular:** {gen_ctx.alignment_note}\n\n"

    title = f"Planificación diferenciada del curso — {canonical}"
    body = (
        intro
        + f"Propuesta para **{course_name}** («{canonical}», {grade_line}) con **{n}** perfiles pedagógicos.\n\n"
        f"**Anclaje curricular (evidencia RAG)**\n"
        f"- OA: {curricular.oa}\n"
        f"- Unidad: «{curricular.unit_name}»\n"
        f"- {curricular.main_activity}\n"
        f"- Conceptos clave del PDF: {', '.join(curricular.concepts)}.\n\n"
        f"**Objetivos comunes**\n"
        f"- Lograr el OA con un núcleo común y diferenciación de apoyos (no de objetivos).\n"
        f"- Incorporar recta numérica / esquema, despeje y verificación cuando el material lo indica.\n"
        f"- Mantener rutinas visuales y segmentación temporal (PIE / TEA).\n\n"
        f"**Secuencia didáctica**\n\n"
        f"*Inicio (10–15 min)*\n"
        f"1. Agenda visual; activación con fragmento [1] del PDF («{curricular.unit_name}»).\n"
        f"2. OA visible y criterios de logro en lenguaje simple.\n\n"
        f"*Desarrollo (30–35 min)*\n"
        f"1. **Núcleo común**: modelaje de resolución (despeje + verificación) con apoyo gráfico.\n"
        f"2. **Estaciones por nivel** (asignación trazable):\n"
        f"   - Nivel A: pictogramas, pasos numerados, docente cerca.\n"
        f"   - Nivel B: checklist y ejemplo resuelto parcial.\n"
        f"   - Nivel C: problemas contextualizados y extensión.\n"
        f"3. Pausas de autorregulación cada 10 minutos.\n\n"
        f"{tier_block}\n\n"
        f"{named_block}\n\n"
        f"*Cierre (10 min)*\n"
        f"1. Ticket de salida diferenciado (oral, dibujo o verificación escrita).\n"
        f"2. Retroalimentación por nivel.\n\n"
        f"**Evaluación formativa**\n"
        f"- Rúbrica común; evidencias heterogéneas según perfil."
    )

    explanation = build_teacher_narrative_explanation(
        pkg, gen_ctx, course_name=course_name
    )
    return GeneratedRecommendation(
        title=title,
        body=body,
        explanation=explanation,
        degraded_mode=True,
        evidence_chain=pkg.evidence_chain,
    )


def _openai_generate_student(
    planning_topic: str,
    descriptors: list[dict],
    chunks: list[RetrievedChunk],
    student_name: str,
    grade_level: str | None = None,
    student_id: int = 0,
) -> GeneratedRecommendation:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
    all_desc = _normalize_descriptors(descriptors)
    profile_text = "\n".join(f"- {d['label']}: {d['value']:.2f}" for d in all_desc)
    chunks_text = "\n\n".join(
        f"Fragmento {i} (unidad {c.unit_name}, relevancia {c.score:.2f}):\n{c.content[:800]}"
        for i, c in enumerate(chunks, start=1)
    )
    gen_ctx = resolve_generation_context(planning_topic, chunks)
    canonical_unit = chunks[0].unit_name if chunks else planning_topic
    prompt = f"""Eres un asistente pedagógico para docentes chilenos que trabajan con estudiantes TEA en PIE.
Genera una planificación de clase **completa y detallada** (no un resumen breve).

Estudiante: {student_name}
Tema solicitado por el docente: {planning_topic}
UNIDAD OBLIGATORIA (material RAG indexado): {canonical_unit}
{f"ALINEACIÓN: {gen_ctx.alignment_note}" if gen_ctx.alignment_note else ""}
{grade_level_prompt_line(grade_level)}

REGLA CRÍTICA: La planificación DEBE tratar exclusivamente la unidad «{canonical_unit}» del PDF.
NO introduzcas contenidos de otra unidad (ej.: NO ecuaciones cuadráticas si el PDF es ecuaciones lineales).

Perfil pedagógico completo (escala 0-1; ≥0,85 fortaleza, 0,60–0,85 moderado, <0,60 intensivo):
{profile_text}

Material curricular recuperado:
{chunks_text or "Sin fragmentos disponibles."}

Responde en español con este formato exacto (etiquetas en mayúsculas, cada una en su propia línea):
TITULO: (una línea, debe mencionar {canonical_unit})
CUERPO: (planificación extensa; anclaje al OA del PDF; actividades de despeje/recta numérica/verificación si aplica; adaptaciones matemáticas para {student_name})
EXPLICACION: (tabla «Evidencia encontrada | Decisión pedagógica» con cada descriptor citado con su puntaje y el OA)
No uses markdown para las etiquetas TITULO/CUERPO/EXPLICACION; escríbelas tal cual.
"""

    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=LLM_MAX_TOKENS_STUDENT,
    )
    text = response.choices[0].message.content or ""
    title, body, explanation, used_fallback = _parse_llm_response(
        text, planning_topic, descriptors, chunks, student_name, grade_level=grade_level
    )
    return GeneratedRecommendation(
        title=title,
        body=body,
        explanation=explanation,
        degraded_mode=used_fallback,
    )


def _openai_generate_course(
    planning_topic: str,
    course_name: str,
    student_profiles: list[StudentProfileSnapshot],
    chunks: list[RetrievedChunk],
    grade_level: str | None = None,
) -> GeneratedRecommendation:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
    profiles_text = []
    for snap in student_profiles:
        desc_lines = "\n".join(
            f"    - {d['label']}: {d['value']:.2f}" for d in _normalize_descriptors(snap.descriptors)
        )
        profiles_text.append(f"- {snap.student_name}:\n{desc_lines}")
    chunks_text = "\n\n".join(
        f"Fragmento {i} (unidad {c.unit_name}):\n{c.content[:700]}"
        for i, c in enumerate(chunks, start=1)
    )
    gen_ctx = resolve_generation_context(planning_topic, chunks)
    canonical_unit = chunks[0].unit_name if chunks else planning_topic
    prompt = f"""Eres un asistente pedagógico para docentes chilenos (PIE, estudiantes TEA).
Genera una **planificación diferenciada para todo el curso**, no para un solo alumno.

Curso: {course_name}
Tema solicitado por el docente: {planning_topic}
UNIDAD OBLIGATORIA (material RAG indexado): {canonical_unit}
{f"ALINEACIÓN: {gen_ctx.alignment_note}" if gen_ctx.alignment_note else ""}
{grade_level_prompt_line(grade_level)}
Estudiantes con perfil ({len(student_profiles)}):
{chr(10).join(profiles_text)}

Material curricular:
{chunks_text or "Sin fragmentos."}

REGLA CRÍTICA: La planificación DEBE tratar exclusivamente la unidad «{canonical_unit}» del PDF.
NO introduzcas contenidos de otra unidad (ej.: NO ecuaciones cuadráticas si el PDF es ecuaciones lineales).

El CUERPO debe incluir: anclaje al OA del PDF, actividad principal concreta (no genérica), secuencia didáctica, asignación Nivel A/B/C con nombres de estudiantes, adaptación nominal por estudiante, evaluación formativa.

Formato exacto (etiquetas TITULO:, CUERPO: y EXPLICACION: cada una en línea propia, sin markdown en las etiquetas):
TITULO: (una línea, debe mencionar {canonical_unit})
CUERPO: (texto extenso, mínimo 8 párrafos o secciones equivalentes)
EXPLICACION: (tabla Evidencia encontrada | Decisión pedagógica con puntajes de descriptores y OA; citas a fragmentos [1][2]; sin jerga técnica de IA)
"""

    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=LLM_MAX_TOKENS_COURSE,
    )
    text = response.choices[0].message.content or ""
    title, body, explanation, used_fallback = _parse_llm_response(
        text,
        planning_topic,
        student_profiles[0].descriptors if student_profiles else [],
        chunks,
        course_name,
        fallback_fn=lambda: _template_generate_course(
            planning_topic, course_name, student_profiles, chunks, grade_level
        ),
    )
    return GeneratedRecommendation(
        title=title,
        body=body,
        explanation=explanation,
        degraded_mode=used_fallback,
    )


def _parse_llm_response(
    text: str,
    planning_topic: str,
    descriptors: list[dict],
    chunks: list[RetrievedChunk],
    subject_name: str,
    *,
    grade_level: str | None = None,
    fallback_fn=None,
) -> tuple[str, str, str, bool]:
    title = ""
    body = ""
    explanation = ""
    section = None
    lines = text.strip().splitlines()
    for line in lines:
        matched_section, inline = _match_section_line(line)
        if matched_section:
            section = matched_section
            if matched_section == "title":
                title = inline
            elif matched_section == "body":
                body = inline + "\n" if inline else ""
            elif matched_section == "explanation":
                explanation = inline + "\n" if inline else ""
            continue
        if section == "title" and not title:
            title = line.strip()
            section = "body"
        elif section == "body":
            body += line + "\n"
        elif section == "explanation":
            explanation += line + "\n"

    title = title.strip() or f"Planificación — {planning_topic}"
    body = body.strip()
    explanation = explanation.strip()

    if not body or not explanation or len(body) < 200:
        h_title, h_body, h_explanation = _heuristic_split_llm_text(text, planning_topic)
        if h_body and h_explanation and len(h_body) >= 200:
            return h_title, h_body, h_explanation, False

    # GPT respondió en markdown sin etiquetas TITULO/CUERPO/EXPLICACION
    cleaned = text.strip()
    if len(body) >= 200 and not explanation:
        return title, body, "¿Por qué esta sugerencia?\nVer cadena de evidencia pedagógica.", False
    if not body and len(cleaned) >= 500:
        first_line, _, rest = cleaned.partition("\n")
        inferred_title = first_line.strip().lstrip("#").strip()
        if len(inferred_title) > 120:
            inferred_title = f"Planificación — {planning_topic}"
        return (
            inferred_title or title,
            cleaned,
            "¿Por qué esta sugerencia?\nVer cadena de evidencia pedagógica.",
            False,
        )

    if not body or not explanation or len(body) < 200:
        logger.warning(
            "LLM response parse fallback for %s (body_len=%s, explanation_len=%s)",
            subject_name,
            len(body),
            len(explanation),
        )
        if fallback_fn:
            fb = fallback_fn()
            return title or fb.title, body or fb.body, explanation or fb.explanation, True
        fallback = _template_generate_student(
            planning_topic, descriptors, chunks, subject_name, grade_level
        )
        return (
            title or fallback.title,
            body or fallback.body,
            explanation or fallback.explanation,
            True,
        )
    if not explanation.startswith("¿Por qué"):
        explanation = "¿Por qué se sugiere?\n" + explanation
    return title, body, explanation, False

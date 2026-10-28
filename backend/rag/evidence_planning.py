"""Construcción de evidencia pedagógica trazable (OA, perfiles, RAG → decisiones)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ml.questions import DESCRIPTOR_KEYS
from rag.retrieve import RetrievedChunk

DESCRIPTOR_LABELS = {
    "comprension_lectora": "Comprensión lectora",
    "razonamiento_logico": "Razonamiento lógico",
    "autonomia": "Autonomía en tarea",
    "preferencia_visual": "Preferencia visual",
    "atencion_sostenida": "Atención sostenida",
    "regulacion_emocional": "Regulación emocional",
}

STRENGTH_THRESHOLD = 0.62
SUPPORT_THRESHOLD = 0.45
MODERATE_THRESHOLD = 0.60
HIGH_STRENGTH_THRESHOLD = 0.85


@dataclass
class StudentProfileSnapshot:
    student_id: int
    student_name: str
    descriptors: list
    profile_version: int


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


def _format_citations(chunks: list[RetrievedChunk], limit: int = 5) -> list[str]:
    citations: list[str] = []
    for i, chunk in enumerate(chunks[:limit], start=1):
        snippet = chunk.content[:220].rstrip() + ("…" if len(chunk.content) > 220 else "")
        citations.append(f'[{i}] Unidad «{chunk.unit_name}»: "{snippet}"')
    return citations

PEDAGOGICAL_ACTIONS: dict[str, str] = {
    "preferencia_visual": "Uso de recta numérica ampliada, esquema gráfico y tarjetas paso a paso",
    "comprension_lectora": "Enunciados breves, lectura guiada y glosario pictográfico del tema",
    "razonamiento_logico": "Problemas de aplicación con andamiaje gradual (ejemplo resuelto → parejas)",
    "autonomia": "Consignas abiertas y rol de tutor entre pares en estación de extensión",
    "atencion_sostenida": "Bloques de 8–10 min, checklist visible y una consigna por línea",
    "regulacion_emocional": "Pausas activas cada dos ejercicios y anticipación de cambios con agenda visual",
}

# Acciones con foco matemático (contenido del OA, no solo apoyos transversales)
MATH_PEDAGOGICAL_ACTIONS: dict[str, str] = {
    "preferencia_visual": "Recta numérica ampliada, organizador gráfico del despeje y tarjetas del procedimiento",
    "comprension_lectora": "Problemas contextualizados con lectura autónoma de consignas breves",
    "razonamiento_logico": "Ejercicios guiados (ax+b=c) y luego un problema abierto con verificación",
    "autonomia": "Resolver ejercicios de forma individual antes de la retroalimentación grupal",
    "atencion_sostenida": "Secuencia en bloques de 10 min: modelaje → práctica → verificación",
    "regulacion_emocional": "Pausa breve tras cada par de ejercicios y anticipación de cambios con agenda visual",
}


@dataclass
class GenerationContext:
    """Tema canónico alineado al RAG (evita mezclar unidad del PDF con tema libre del docente)."""

    planning_topic: str
    canonical_topic: str
    topic_aligned: bool
    alignment_note: str | None = None


def _tokenize_topic(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-záéíóúñü]+", text.lower()))
    stop = {"de", "la", "el", "los", "las", "y", "en", "para", "un", "una", "del", "con"}
    return {t for t in tokens if t not in stop and len(t) > 2}


def _topics_overlap(a: str, b: str) -> bool:
    ta, tb = _tokenize_topic(a), _tokenize_topic(b)
    if not ta or not tb:
        return True
    return bool(ta & tb)


def _conflicting_math_domains(planning_topic: str, unit_name: str, chunk_text: str) -> bool:
    """Detecta mezcla típica lineales vs cuadráticas u otras unidades distintas."""
    combined = f"{planning_topic} {unit_name} {chunk_text[:1200]}".lower()
    planning_l = planning_topic.lower()
    unit_l = unit_name.lower()
    pairs = [
        (("cuadrática", "cuadratica", "x²", "x^2"), ("lineal", "lineales")),
        (("fracción", "fracciones"), ("decimal", "decimales")),
        (("pitágora", "pitagoras"), ("lineal", "ecuacion")),
    ]
    for group_a, group_b in pairs:
        in_planning_a = any(g in planning_l for g in group_a)
        in_rag_b = any(g in unit_l or g in combined for g in group_b)
        in_planning_b = any(g in planning_l for g in group_b)
        in_rag_a = any(g in unit_l or g in combined for g in group_a)
        if (in_planning_a and in_rag_b and not in_planning_b) or (in_planning_b and in_rag_a and not in_planning_a):
            return True
    if not _topics_overlap(planning_topic, unit_name) and chunks_look_specific(unit_name):
        return True
    return False


def chunks_look_specific(unit_name: str) -> bool:
    return len(_tokenize_topic(unit_name)) >= 1 and unit_name.strip().lower() not in {
        "general",
        "unidad",
        "tema",
    }


def resolve_generation_context(
    planning_topic: str,
    chunks: list[RetrievedChunk],
) -> GenerationContext:
    topic = planning_topic.strip()
    if not chunks:
        return GenerationContext(
            planning_topic=topic,
            canonical_topic=topic,
            topic_aligned=True,
        )

    unit = chunks[0].unit_name.strip()
    chunk_text = chunks[0].content
    conflict = _conflicting_math_domains(topic, unit, chunk_text)
    overlap = _topics_overlap(topic, unit)

    if conflict or not overlap:
        note = (
            f"El tema ingresado («{topic}») no coincide con la unidad recuperada del PDF "
            f"(«{unit}»). La planificación se ancla al material curricular indexado."
        )
        return GenerationContext(
            planning_topic=topic,
            canonical_topic=unit,
            topic_aligned=False,
            alignment_note=note,
        )

    return GenerationContext(
        planning_topic=topic,
        canonical_topic=topic,
        topic_aligned=True,
    )


def _support_tier_label(value: float) -> str:
    if value >= HIGH_STRENGTH_THRESHOLD:
        return "fortaleza"
    if value >= MODERATE_THRESHOLD:
        return "apoyo moderado"
    return "apoyo intensivo"


def _descriptor_evidence_label(d: dict) -> str:
    label = d["label"]
    value = float(d["value"])
    tier = _support_tier_label(value)
    return f"{label} ({value:.2f} — {tier})"


def _tier_threshold_phrase(value: float) -> str:
    if value >= HIGH_STRENGTH_THRESHOLD:
        return f"≥{HIGH_STRENGTH_THRESHOLD:.2f} (fortaleza)"
    if value >= MODERATE_THRESHOLD:
        return f"entre {MODERATE_THRESHOLD:.2f} y {HIGH_STRENGTH_THRESHOLD:.2f} (apoyo moderado)"
    return f"por debajo de {MODERATE_THRESHOLD:.2f} (apoyo intensivo)"


def _math_progression_for_descriptor(key: str, value: float, curricular: CurricularAnchor) -> str:
    """Progresión matemática concreta según descriptor y nivel de apoyo."""
    unit = curricular.unit_name
    if key == "razonamiento_logico":
        if value < MODERATE_THRESHOLD:
            return (
                "3 ecuaciones ax+b=c con modelaje paso a paso → 1 problema contextualizado "
                "con verificación por sustitución"
            )
        if value < HIGH_STRENGTH_THRESHOLD:
            return (
                "2 ejercicios con ejemplo resuelto → práctica guiada con checklist de despeje "
                "y verificación"
            )
        return f"Problemas de aplicación en «{unit}» con dos operaciones y verificación autónoma"
    if key == "comprension_lectora":
        if value >= HIGH_STRENGTH_THRESHOLD:
            return f"Problemas contextualizados de «{unit}» con enunciados breves de lectura autónoma"
        if value >= MODERATE_THRESHOLD:
            return "Enunciados breves con glosario pictográfico y lectura compartida antes de resolver"
        return "Consignas en una línea, lectura guiada y vocabulario clave visible en tarjetas"
    if key == "preferencia_visual":
        if value >= HIGH_STRENGTH_THRESHOLD:
            return "Organizador gráfico comparando despeje y representación en recta numérica"
        return "Recta numérica ampliada, esquema del despeje y tarjetas del procedimiento"
    if key == "autonomia":
        if value >= HIGH_STRENGTH_THRESHOLD:
            return "Resolver ejercicios de forma individual y verificar la solución antes de retroalimentación"
        if value >= MODERATE_THRESHOLD:
            return "Práctica individual con checklist visible; retroalimentación grupal al final"
        return "Trabajo en parejas con roles definidos (lector / verificador) antes de intentar solo"
    if key == "atencion_sostenida":
        if value >= HIGH_STRENGTH_THRESHOLD:
            return "Secuencia en bloques de 10 min: modelaje → práctica → verificación"
        return "Bloques de 8–10 min con una consigna por línea y checklist visible"
    if key == "regulacion_emocional":
        if value >= HIGH_STRENGTH_THRESHOLD:
            return "Pausa breve tras cada par de ejercicios y anticipación de cambios con agenda visual"
        return "Pausas activas cada dos ejercicios y refuerzo positivo tras cada verificación"
    return f"Trabajar el OA de «{unit}» con andamiaje acorde al descriptor"


def _descriptor_rationale(d: dict, curricular: CurricularAnchor) -> str:
    key = _descriptor_key(d)
    label = d["label"]
    value = float(d["value"])
    tier = _tier_threshold_phrase(value)
    progression = _math_progression_for_descriptor(key, value, curricular)
    if value < MODERATE_THRESHOLD:
        return (
            f"{label} ({value:.2f}) está {tier}; por eso se propone {progression.lower()}."
        )
    if value < HIGH_STRENGTH_THRESHOLD:
        return (
            f"{label} ({value:.2f}) está {tier}; se combina andamiaje gradual con "
            f"{progression.lower()}."
        )
    return (
        f"{label} ({value:.2f}) está {tier}; se potencia con "
        f"{progression.lower()}."
    )


def _curricular_rationale(curricular: CurricularAnchor, gen_ctx: GenerationContext) -> str:
    base = (
        f"El fragmento recuperado del PDF define el OA de «{curricular.unit_name}»; "
        "la actividad principal reproduce ese objetivo con despeje, representación visual "
        "y verificación de la solución."
    )
    if gen_ctx.alignment_note:
        return f"{gen_ctx.alignment_note} {base}"
    return base


def _course_descriptor_rationale(
    key: str,
    label: str,
    count: int,
    curricular: CurricularAnchor,
) -> str:
    action = PEDAGOGICAL_ACTIONS.get(key, f"apoyos en {label.lower()}")
    return (
        f"{count} estudiante(s) presentan {label.lower()} bajo el umbral de apoyo "
        f"(<{SUPPORT_THRESHOLD:.2f}); se prioriza {action.lower()} en la planificación grupal."
    )


def _profile_synthesis(descriptors: list) -> dict:
    normalized = _normalize_descriptors(descriptors)
    strengths = [
        {"key": _descriptor_key(d), "label": d["label"], "value": round(float(d["value"]), 3)}
        for d in sorted(normalized, key=lambda x: x["value"], reverse=True)
        if float(d["value"]) >= HIGH_STRENGTH_THRESHOLD
    ]
    supports = [
        {"key": _descriptor_key(d), "label": d["label"], "value": round(float(d["value"]), 3)}
        for d in sorted(normalized, key=lambda x: x["value"])
        if float(d["value"]) < MODERATE_THRESHOLD
    ]
    return {"strengths": strengths, "supports": supports}


def _evidence_rows_payload(rows: list[EvidenceRow]) -> list[dict]:
    return [
        {
            "evidence": r.evidence,
            "decision": r.decision,
            "descriptor_key": r.descriptor_key,
            "chunk_id": r.chunk_id,
            "rationale": r.rationale,
        }
        for r in rows
    ]


def build_teacher_narrative_explanation(
    pkg: EvidencePackage,
    gen_ctx: GenerationContext,
    *,
    student_name: str | None = None,
    course_name: str | None = None,
) -> str:
    subject = student_name or course_name or "el curso"
    parts = [
        f"La propuesta ancla la clase al material indexado («{pkg.curricular.unit_name}») "
        f"y al perfil pedagógico de {subject}.",
    ]
    synthesis = pkg.evidence_chain.get("profile_synthesis")
    if synthesis and student_name:
        strength_labels = [s["label"] for s in synthesis.get("strengths", [])]
        support_labels = [s["label"] for s in synthesis.get("supports", [])]
        if strength_labels:
            parts.append(f"Fortalezas del perfil: {', '.join(strength_labels)}.")
        if support_labels:
            parts.append(f"Apoyos prioritarios: {', '.join(support_labels)}.")
    parts.append(
        "El detalle trazable (descriptor → justificación → decisión, OA y fragmentos del PDF) "
        "se muestra en la cadena de evidencia siguiente."
    )
    return "\n\n".join(parts)


def _math_decision_for_descriptor(d: dict, curricular: CurricularAnchor) -> str:
    key = _descriptor_key(d)
    value = float(d["value"])
    progression = _math_progression_for_descriptor(key, value, curricular)
    if value >= HIGH_STRENGTH_THRESHOLD:
        return f"Potenciar: {progression}"
    if value >= MODERATE_THRESHOLD:
        return f"Apoyo moderado: {progression}"
    return f"Apoyo intensivo: {progression}"


def _student_math_adaptation_lines(descriptors: list, curricular: CurricularAnchor) -> list[str]:
    lines: list[str] = []
    ranked = sorted(_normalize_descriptors(descriptors), key=lambda d: d["value"])
    for d in ranked[:4]:
        if float(d["value"]) < HIGH_STRENGTH_THRESHOLD:
            lines.append(_math_decision_for_descriptor(d, curricular))
    strengths = sorted(_normalize_descriptors(descriptors), key=lambda d: d["value"], reverse=True)
    for d in strengths[:2]:
        if float(d["value"]) >= HIGH_STRENGTH_THRESHOLD:
            line = _math_decision_for_descriptor(d, curricular)
            if line not in lines:
                lines.append(line)
    if not lines:
        lines.append(
            f"Trabajar el OA de «{curricular.unit_name}» con despeje, representación visual y verificación."
        )
    return lines[:4]


@dataclass
class CurricularAnchor:
    oa: str
    unit_name: str
    concepts: list[str]
    main_activity: str
    chunk_id: int | None = None


@dataclass
class EvidenceRow:
    evidence: str
    decision: str
    descriptor_key: str | None = None
    chunk_id: int | None = None
    rationale: str | None = None


@dataclass
class EvidencePackage:
    curricular: CurricularAnchor
    rows: list[EvidenceRow]
    tier_a: list[str]
    tier_b: list[str]
    tier_c: list[str]
    student_adaptations: list[dict]
    evidence_chain: dict
    explanation_table: str
    citations: list[str] = field(default_factory=list)


def _descriptor_key(d: dict) -> str:
    if d.get("key"):
        return str(d["key"])
    label = d.get("label", "")
    for key, lbl in DESCRIPTOR_LABELS.items():
        if lbl.lower() == label.lower():
            return key
    return label.lower().replace(" ", "_")


def extract_curricular_anchor(chunks: list[RetrievedChunk], planning_topic: str) -> CurricularAnchor:
    topic = planning_topic.strip()
    if not chunks:
        return CurricularAnchor(
            oa=f"Abordar «{topic}» según el plan curricular del curso",
            unit_name=topic,
            concepts=["conceptos clave del tema", "verificación de resultados"],
            main_activity=(
                f"Actividad principal: trabajar «{topic}» con representación visual, "
                "procedimiento paso a paso y verificación de la solución."
            ),
        )

    top = chunks[0]
    text = top.content
    oa_match = re.search(
        r"Objetivo de aprendizaje\s*\(OA\)\s*:\s*([^.\n]+)",
        text,
        re.IGNORECASE,
    )
    oa = oa_match.group(1).strip() if oa_match else f"Resolver y aplicar contenidos de «{top.unit_name}»"

    concepts: list[str] = []
    for pattern, label in [
        (r"ecuaci[oó]n", "ecuaciones e incógnita"),
        (r"recta num[eé]rica", "representación en recta numérica"),
        (r"despej", "despeje de la incógnita"),
        (r"verific", "verificación de la solución"),
        (r"glosario", "vocabulario clave del glosario"),
    ]:
        if re.search(pattern, text, re.IGNORECASE):
            concepts.append(label)
    if not concepts:
        concepts = [f"núcleo de {top.unit_name}", "aplicación en contexto"]

    main_activity = (
        f"Resolver ecuaciones de «{top.unit_name}» según el OA ({oa}): "
        f"despeje, {', '.join(concepts[:3])} y verificación sustituyendo la solución."
    )

    return CurricularAnchor(
        oa=oa,
        unit_name=top.unit_name,
        concepts=concepts[:4],
        main_activity=main_activity,
        chunk_id=top.id,
    )


def _students_needing_support(
    profiles: list[StudentProfileSnapshot],
    descriptor_key: str,
) -> list[str]:
    names: list[str] = []
    for snap in profiles:
        for d in _normalize_descriptors(snap.descriptors):
            if _descriptor_key(d) == descriptor_key and float(d["value"]) < SUPPORT_THRESHOLD:
                names.append(snap.student_name)
                break
    return names


def _students_with_strength(
    profiles: list[StudentProfileSnapshot],
    descriptor_key: str,
) -> list[str]:
    names: list[str] = []
    for snap in profiles:
        for d in _normalize_descriptors(snap.descriptors):
            if _descriptor_key(d) == descriptor_key and float(d["value"]) >= STRENGTH_THRESHOLD:
                names.append(snap.student_name)
                break
    return names


def assign_tiers(profiles: list[StudentProfileSnapshot]) -> tuple[list[str], list[str], list[str]]:
    tier_a: list[str] = []
    tier_b: list[str] = []
    tier_c: list[str] = []
    for snap in profiles:
        supports = _support_descriptors(snap.descriptors)
        strengths = _strength_descriptors(snap.descriptors)
        low_values = [d for d in _normalize_descriptors(snap.descriptors) if d["value"] < 0.38]
        if len(supports) >= 2 or len(low_values) >= 2:
            tier_a.append(snap.student_name)
        elif len(strengths) >= 2 and not supports:
            tier_c.append(snap.student_name)
        else:
            tier_b.append(snap.student_name)
    return tier_a, tier_b, tier_c


def _student_adaptation_lines(snap: StudentProfileSnapshot) -> list[str]:
    lines: list[str] = []
    supports = _support_descriptors(snap.descriptors)[:2]
    for d in supports:
        key = _descriptor_key(d)
        action = PEDAGOGICAL_ACTIONS.get(key, f"Apoyo en {d['label'].lower()}")
        lines.append(action)
    if not lines:
        strengths = _strength_descriptors(snap.descriptors) or _top_descriptors(snap.descriptors, 1)
        if strengths:
            key = _descriptor_key(strengths[0])
            action = PEDAGOGICAL_ACTIONS.get(key, "Extensión con consigna de mayor autonomía")
            lines.append(f"Potenciar {strengths[0]['label'].lower()}: {action}")
    return lines


def _format_evidence_table(rows: list[EvidenceRow]) -> str:
    if not rows:
        return ""
    lines = [
        "Cadena de evidencia (perfil + curricular → decisión):",
        "",
        "| Evidencia encontrada | Decisión pedagógica |",
        "| --- | --- |",
    ]
    for row in rows:
        ev = row.evidence.replace("|", "/")
        dec = row.decision.replace("|", "/")
        lines.append(f"| {ev} | {dec} |")
    return "\n".join(lines)


def build_course_evidence_package(
    *,
    planning_topic: str,
    course_name: str,
    student_profiles: list[StudentProfileSnapshot],
    chunks: list[RetrievedChunk],
) -> EvidencePackage:
    gen_ctx = resolve_generation_context(planning_topic, chunks)
    curricular = extract_curricular_anchor(chunks, gen_ctx.canonical_topic)
    tier_a, tier_b, tier_c = assign_tiers(student_profiles)
    citations = _format_citations(chunks)
    rows: list[EvidenceRow] = []

    rows.append(
        EvidenceRow(
            evidence=f"OA / unidad «{curricular.unit_name}» (fragmento RAG principal)",
            decision=curricular.main_activity,
            chunk_id=curricular.chunk_id,
            rationale=_curricular_rationale(curricular, gen_ctx),
        )
    )

    for key in DESCRIPTOR_KEYS:
        needing = _students_needing_support(student_profiles, key)
        if not needing:
            continue
        label = DESCRIPTOR_LABELS.get(key, key)
        count = len(needing)
        action = PEDAGOGICAL_ACTIONS.get(key, f"Apoyos en {label.lower()}")
        rows.append(
            EvidenceRow(
                evidence=f"{count} estudiante(s) con apoyo en {label.lower()}",
                decision=action,
                descriptor_key=key,
                rationale=_course_descriptor_rationale(key, label, count, curricular),
            )
        )

    strong_readers = _students_with_strength(student_profiles, "comprension_lectora")
    if len(strong_readers) >= 3:
        rows.append(
            EvidenceRow(
                evidence=f"{len(strong_readers)} estudiantes con fortaleza en comprensión lectora",
                decision="Problemas contextualizados y lectura autónoma de consignas breves",
                descriptor_key="comprension_lectora",
                rationale=(
                    f"{len(strong_readers)} estudiantes superan el umbral de fortaleza "
                    f"(≥{HIGH_STRENGTH_THRESHOLD:.2f}) en comprensión lectora; se incorporan "
                    "problemas contextualizados con lectura autónoma."
                ),
            )
        )

    student_adaptations: list[dict] = []
    for snap in student_profiles:
        actions = _student_math_adaptation_lines(snap.descriptors, curricular)
        student_adaptations.append(
            {
                "student_id": snap.student_id,
                "student_name": snap.student_name,
                "adaptations": actions,
            }
        )

    chain_steps = [
        {
            "order": 1,
            "stage": "curricular",
            "label": "Fragmento recuperado (RAG)",
            "detail": f"Unidad «{curricular.unit_name}» — {curricular.oa[:120]}",
            "chunk_id": curricular.chunk_id,
        },
        {
            "order": 2,
            "stage": "profile",
            "label": "Perfiles del curso",
            "detail": f"{len(student_profiles)} estudiantes con diagnóstico y descriptor(es) considerados",
        },
        {
            "order": 3,
            "stage": "generation",
            "label": "Reglas de adaptación",
            "detail": "Relación descriptor → estrategia pedagógica (tabla de evidencia)",
        },
        {
            "order": 4,
            "stage": "recommendation",
            "label": "Planificación propuesta",
            "detail": f"Planificación grupal para {course_name} — «{gen_ctx.canonical_topic}»",
        },
        {
            "order": 5,
            "stage": "mitl",
            "label": "Validación docente",
            "detail": "Pendiente: aceptar, editar o rechazar (Human-in-the-Loop)",
        },
    ]

    evidence_chain = {
        "steps": chain_steps,
        "evidence_rows": _evidence_rows_payload(rows),
        "curricular_anchor": {
            "oa": curricular.oa,
            "unit_name": curricular.unit_name,
            "concepts": curricular.concepts,
            "main_activity": curricular.main_activity,
            "chunk_id": curricular.chunk_id,
        },
        "tier_assignment": {"A": tier_a, "B": tier_b, "C": tier_c},
        "student_adaptations": student_adaptations,
        "citations": citations,
    }
    if gen_ctx.alignment_note:
        evidence_chain["topic_alignment"] = {
            "planning_topic": gen_ctx.planning_topic,
            "canonical_topic": gen_ctx.canonical_topic,
            "aligned": gen_ctx.topic_aligned,
            "note": gen_ctx.alignment_note,
        }

    return EvidencePackage(
        curricular=curricular,
        rows=rows,
        tier_a=tier_a,
        tier_b=tier_b,
        tier_c=tier_c,
        student_adaptations=student_adaptations,
        evidence_chain=evidence_chain,
        explanation_table=_format_evidence_table(rows),
        citations=citations,
    )


def build_student_evidence_package(
    *,
    planning_topic: str,
    student_name: str,
    student_id: int,
    descriptors: list,
    chunks: list[RetrievedChunk],
) -> EvidencePackage:
    gen_ctx = resolve_generation_context(planning_topic, chunks)
    curricular = extract_curricular_anchor(chunks, gen_ctx.canonical_topic)
    citations = _format_citations(chunks)
    rows: list[EvidenceRow] = [
        EvidenceRow(
            evidence=f"OA / unidad «{curricular.unit_name}» (fragmento RAG [1])",
            decision=curricular.main_activity,
            chunk_id=curricular.chunk_id,
            rationale=_curricular_rationale(curricular, gen_ctx),
        ),
    ]

    for d in _normalize_descriptors(descriptors):
        rows.append(
            EvidenceRow(
                evidence=_descriptor_evidence_label(d),
                decision=_math_decision_for_descriptor(d, curricular),
                descriptor_key=_descriptor_key(d),
                rationale=_descriptor_rationale(d, curricular),
            )
        )

    adaptations = _student_math_adaptation_lines(descriptors, curricular)
    student_adaptations = [
        {
            "student_id": student_id,
            "student_name": student_name,
            "adaptations": adaptations,
        }
    ]

    chain_steps = [
        {
            "order": 1,
            "stage": "curricular",
            "label": "Fragmento recuperado (RAG)",
            "detail": f"Unidad «{curricular.unit_name}» — {curricular.oa[:140]}",
            "chunk_id": curricular.chunk_id,
        },
        {
            "order": 2,
            "stage": "profile",
            "label": f"Perfil de {student_name}",
            "detail": "Descriptores del diagnóstico con puntaje continuo (0–1)",
        },
        {
            "order": 3,
            "stage": "generation",
            "label": "Reglas descriptor → decisión",
            "detail": "≥0,85 fortaleza · 0,60–0,85 apoyo moderado · <0,60 apoyo intensivo",
        },
        {
            "order": 4,
            "stage": "recommendation",
            "label": "Planificación individual",
            "detail": f"«{gen_ctx.canonical_topic}» para {student_name}",
        },
        {
            "order": 5,
            "stage": "mitl",
            "label": "Validación docente",
            "detail": "Pendiente: aceptar, editar o rechazar (Human-in-the-Loop)",
        },
    ]

    evidence_chain = {
        "steps": chain_steps,
        "evidence_rows": _evidence_rows_payload(rows),
        "curricular_anchor": {
            "oa": curricular.oa,
            "unit_name": curricular.unit_name,
            "concepts": curricular.concepts,
            "main_activity": curricular.main_activity,
            "chunk_id": curricular.chunk_id,
        },
        "descriptor_scores": [
            {
                "key": _descriptor_key(d),
                "label": d["label"],
                "value": round(float(d["value"]), 3),
                "tier": _support_tier_label(float(d["value"])),
            }
            for d in _normalize_descriptors(descriptors)
        ],
        "profile_synthesis": _profile_synthesis(descriptors),
        "student_adaptations": student_adaptations,
        "tier_assignment": {"A": [], "B": [student_name], "C": []},
        "citations": citations,
    }
    if gen_ctx.alignment_note:
        evidence_chain["topic_alignment"] = {
            "planning_topic": gen_ctx.planning_topic,
            "canonical_topic": gen_ctx.canonical_topic,
            "aligned": gen_ctx.topic_aligned,
            "note": gen_ctx.alignment_note,
        }

    return EvidencePackage(
        curricular=curricular,
        rows=rows,
        tier_a=[],
        tier_b=[student_name],
        tier_c=[],
        student_adaptations=student_adaptations,
        evidence_chain=evidence_chain,
        explanation_table=_format_evidence_table(rows),
        citations=citations,
    )


def body_conflicts_with_curricular(body: str, curricular: CurricularAnchor) -> bool:
    """Detecta contenido matemático incompatible con la unidad RAG."""
    unit = curricular.unit_name.lower()
    oa = curricular.oa.lower()
    text = body.lower()
    if "lineal" in unit or "lineal" in oa:
        return any(
            term in text
            for term in (
                "cuadrática",
                "cuadratica",
                "cuadráticas",
                "x²",
                "x^2",
                "trinomio",
                "factorización de trinomios",
                "fórmula general",
            )
        )
    return False


def apply_topic_alignment_to_body(
    body: str,
    gen_ctx: GenerationContext,
    curricular: CurricularAnchor,
) -> str:
    if gen_ctx.alignment_note:
        note = f"**Alineación curricular:** {gen_ctx.alignment_note}\n\n"
        if note.strip() not in body:
            body = note + body
    if gen_ctx.planning_topic != gen_ctx.canonical_topic:
        body = body.replace(gen_ctx.planning_topic, gen_ctx.canonical_topic)
    return body


def format_tier_block(tier_a: list[str], tier_b: list[str], tier_c: list[str]) -> str:
    def names(lst: list[str]) -> str:
        return ", ".join(lst) if lst else "—"

    return (
        f"**Asignación por niveles (trazable desde perfil)**\n"
        f"- **Nivel A** (apoyo máximo): {names(tier_a)}\n"
        f"- **Nivel B** (apoyo moderado): {names(tier_b)}\n"
        f"- **Nivel C** (extensión): {names(tier_c)}"
    )


def format_named_adaptations(adaptations: list[dict], limit: int = 15) -> str:
    lines = ["**Adaptaciones concretas por estudiante**"]
    for item in adaptations[:limit]:
        acts = "; ".join(item["adaptations"]) if item["adaptations"] else "Apoyos universales TEA"
        lines.append(f"- **{item['student_name']}**: {acts}")
    return "\n".join(lines)

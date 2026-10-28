"""Limpieza de contenido pedagógico para la vista docente."""

import re


_TECHNICAL_FOOTER_PATTERNS = [
    r"\n*\(Modo degradado:.*?\)\s*",
    r"\n*\(Nota: se usó la plantilla pedagógica de respaldo.*?\)\s*",
]


def compact_teacher_explanation_for_chain(explanation: str) -> str:
    """Quita tablas y citas duplicadas cuando la cadena de evidencia ya las muestra."""
    if not explanation:
        return explanation
    text = explanation.strip()
    text = re.sub(r"^¿Por qué se sugiere\?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^¿Por qué esta sugerencia\?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"Cadena de evidencia \(perfil \+ curricular → decisión\):[\s\S]*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\| Evidencia encontrada \| Decisión pedagógica \|[\s\S]*",
        "",
        text,
    )
    text = re.sub(r"Fragmentos curriculares citados:[\s\S]*", "", text, flags=re.IGNORECASE)
    return text.strip()


def sanitize_teacher_explanation(explanation: str, *, has_evidence_chain: bool = False) -> str:
    """Oculta pies técnicos internos; el estado degraded_mode se muestra aparte."""
    if not explanation:
        return explanation
    text = explanation
    for pattern in _TECHNICAL_FOOTER_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)
    text = text.strip()
    if has_evidence_chain:
        text = compact_teacher_explanation_for_chain(text)
    return text

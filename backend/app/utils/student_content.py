"""Transformaciones de contenido pedagógico para la vista estudiante."""

import re


def grade_level_prompt_line(grade_level: str | None) -> str:
    if grade_level and grade_level.strip():
        return (
            f"Nivel curricular del curso: {grade_level.strip()}. "
            "Adapta vocabulario, longitud de oraciones y abstracción a ese nivel."
        )
    return (
        "Nivel curricular: educación básica chilena. "
        "Usa lenguaje claro, oraciones cortas y ejemplos concretos."
    )


def simplify_explanation_for_student(explanation: str) -> str:
    """Versión accesible de la explicación XAI (sin jerga técnica ni citas RAG)."""
    if not explanation or not explanation.strip():
        return (
            "Tu docente eligió esta actividad porque encaja con tu forma de aprender "
            "y con el material de tu curso."
        )

    lines: list[str] = []
    for raw in explanation.splitlines():
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if "modo degradado" in lower or "openai_api_key" in lower:
            break
        if lower.startswith("fragmentos curriculares"):
            break
        if re.match(r"^\[\d+\]", line):
            continue
        if line.startswith("- ") and "%" in line and any(c.isdigit() for c in line):
            label = line[2:].split(":")[0].strip()
            if label:
                lines.append(f"• Se consideró tu {label.lower()}.")
            continue
        if line.startswith("¿Por qué"):
            lines.append("Tu docente y el sistema consideraron lo siguiente:")
            continue
        if "perfil pedagógico" in lower and "destaca" in lower:
            lines.append("Se tuvo en cuenta tu perfil de apoyo pedagógico.")
            continue
        if len(line) > 220:
            line = line[:217].rstrip() + "…"
        lines.append(line)

    if not lines:
        return (
            "Tu docente aprobó esta actividad para ayudarte con el tema, "
            "usando apoyos visuales y pasos claros."
        )

    unique: list[str] = []
    seen: set[str] = set()
    for line in lines[:6]:
        if line not in seen:
            seen.add(line)
            unique.append(line)
    return "\n".join(unique)

"""Prueba generate_recommendation con variables Railway."""

import time

from rag.generate import generate_recommendation
from rag.retrieve import RetrievedChunk

chunks = [
    RetrievedChunk(
        id=1,
        unit_name="Ecuaciones Lineales",
        content="Ecuaciones lineales ax+b=c despeje verificacion recta numerica",
        score=0.9,
    )
]
desc = [{"key": "razonamiento_logico", "label": "Razonamiento lógico", "value": 0.45}]

t0 = time.time()
result = generate_recommendation(
    planning_topic="Ecuaciones lineales",
    descriptors=desc,
    chunks=chunks,
    student_name="Estudiante",
    grade_level="8°",
    student_id=1,
)
print("elapsed", round(time.time() - t0, 1))
print("degraded_mode", result.degraded_mode)
print("body_len", len(result.body))
print("title", result.title[:80])

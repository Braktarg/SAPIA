"""Preguntas del test diagnóstico inicial (12 ítems)."""

DIAGNOSTIC_QUESTIONS = [
    {
        "sort_order": 1,
        "feature_key": "q_instrucciones_escritas",
        "question_text": "¿Prefieres instrucciones escritas paso a paso o un ejemplo visual primero?",
        "options": [
            {"value": 0, "label": "Solo escritas"},
            {"value": 1, "label": "Ejemplo primero"},
            {"value": 2, "label": "Ambas por igual"},
        ],
    },
    {
        "sort_order": 2,
        "feature_key": "q_tiempo_procesamiento",
        "question_text": "¿Cuánto tiempo necesitas para entender una consigna nueva?",
        "options": [
            {"value": 0, "label": "Mucho tiempo"},
            {"value": 1, "label": "Tiempo moderado"},
            {"value": 2, "label": "Poco tiempo"},
        ],
    },
    {
        "sort_order": 3,
        "feature_key": "q_apoyo_visual",
        "question_text": "¿Los pictogramas o esquemas te ayudan a comprender mejor?",
        "options": [
            {"value": 0, "label": "No ayudan"},
            {"value": 1, "label": "A veces"},
            {"value": 2, "label": "Mucho"},
        ],
    },
    {
        "sort_order": 4,
        "feature_key": "q_trabajo_grupal",
        "question_text": "¿Te sientes cómodo trabajando en grupo?",
        "options": [
            {"value": 0, "label": "Incómodo"},
            {"value": 1, "label": "Neutral"},
            {"value": 2, "label": "Cómodo"},
        ],
    },
    {
        "sort_order": 5,
        "feature_key": "q_autonomia_tarea",
        "question_text": "¿Puedes iniciar una tarea sin apoyo inmediato del docente?",
        "options": [
            {"value": 0, "label": "Casi nunca"},
            {"value": 1, "label": "A veces"},
            {"value": 2, "label": "Casi siempre"},
        ],
    },
    {
        "sort_order": 6,
        "feature_key": "q_atencion_sostenida",
        "question_text": "¿Mantienes la atención más de 15 minutos en una activida?",
        "options": [
            {"value": 0, "label": "Difícil"},
            {"value": 1, "label": "A veces"},
            {"value": 2, "label": "Frecuente"},
        ],
    },
    {
        "sort_order": 7,
        "feature_key": "q_comprension_lectora",
        "question_text": "¿Comprendes textos cortos sin releer varias veces?",
        "options": [
            {"value": 0, "label": "Difícil"},
            {"value": 1, "label": "A veces"},
            {"value": 2, "label": "Frecuente"},
        ],
    },
    {
        "sort_order": 8,
        "feature_key": "q_razonamiento_logico",
        "question_text": "¿Resuelves problemas matemáticos simples con estrategia propia?",
        "options": [
            {"value": 0, "label": "Difícil"},
            {"value": 1, "label": "A veces"},
            {"value": 2, "label": "Frecuente"},
        ],
    },
    {
        "sort_order": 9,
        "feature_key": "q_regulacion_emocional",
        "question_text": "¿Puedes calmarte cuando algo no sale como esperabas?",
        "options": [
            {"value": 0, "label": "Difícil"},
            {"value": 1, "label": "A veces"},
            {"value": 2, "label": "Frecuente"},
        ],
    },
    {
        "sort_order": 10,
        "feature_key": "q_rutina_estructura",
        "question_text": "¿Las rutinas visuales (agenda, pasos) te ayudan?",
        "options": [
            {"value": 0, "label": "Poco"},
            {"value": 1, "label": "Moderado"},
            {"value": 2, "label": "Mucho"},
        ],
    },
    {
        "sort_order": 11,
        "feature_key": "q_comunicacion_expresiva",
        "question_text": "¿Expresas lo que necesitas cuando no entiendes algo?",
        "options": [
            {"value": 0, "label": "Difícil"},
            {"value": 1, "label": "A veces"},
            {"value": 2, "label": "Frecuente"},
        ],
    },
    {
        "sort_order": 12,
        "feature_key": "q_interes_tematico",
        "question_text": "¿Mantienes interés cuando el tema conecta con tus aficiones?",
        "options": [
            {"value": 0, "label": "Poco"},
            {"value": 1, "label": "Moderado"},
            {"value": 2, "label": "Mucho"},
        ],
    },
]

DESCRIPTOR_KEYS = [
    "comprension_lectora",
    "razonamiento_logico",
    "autonomia",
    "preferencia_visual",
    "atencion_sostenida",
    "regulacion_emocional",
]

MODEL_VERSION = "rf_v1"

"""Genera PDF curricular: Ecuaciones lineales — 8° básico (para biblioteca SAPIA)."""

from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "curriculares" / "Ecuaciones_Lineales_8vo_Basico.pdf"

MARGIN = 50
PAGE_W, PAGE_H = fitz.paper_size("a4")
LINE = 16
TITLE_SIZE = 18
HEADING_SIZE = 13
BODY_SIZE = 11


def new_page(doc: fitz.Document) -> tuple[fitz.Page, float]:
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    return page, MARGIN + 20


def write_lines(page: fitz.Page, y: float, lines: list[str], size: int = BODY_SIZE, bold: bool = False) -> float:
    font = "helv" if not bold else "hebo"
    for line in lines:
        if y > PAGE_H - MARGIN:
            return y
        page.insert_text((MARGIN, y), line, fontsize=size, fontname=font)
        y += LINE if size <= BODY_SIZE else LINE + 4
    return y


def add_page_break(doc: fitz.Document, y: float) -> tuple[fitz.Page, float]:
    if y > PAGE_H - MARGIN - 40:
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        return page, MARGIN + 20
    return doc[-1], y


def build_pdf() -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = MARGIN

    # Portada
    page.insert_text((MARGIN, y + 30), "MATEMÁTICA — 8° BÁSICO", fontsize=14, fontname="hebo")
    y += 55
    page.insert_text((MARGIN, y), "Unidad: Ecuaciones lineales", fontsize=TITLE_SIZE, fontname="hebo")
    y += 35
    y = write_lines(
        page,
        y,
        [
            "Colegio Demo SAPIA — Plan de estudio curricular",
            "Objetivo de aprendizaje (OA): Resolver ecuaciones lineales de la forma ax + b = c,",
            "interpretar su solución y aplicarlas a situaciones cotidianas.",
            "",
            "Duración sugerida: 6 horas pedagógicas",
        ],
    )
    y += 20

    sections = [
        (
            "1. ¿Qué es una ecuación lineal?",
            [
                "Una ecuación lineal es una igualdad que contiene una incógnita (por lo general x).",
                "«Lineal» significa que la incógnita aparece elevada solo a la potencia 1.",
                "",
                "Ejemplos:",
                "  • 2x + 5 = 13        (ecuación lineal)",
                "  • x − 7 = 0          (ecuación lineal)",
                "  • 3x = 15            (ecuación lineal)",
                "",
                "No son lineales: x² + 1 = 5  ni  1/x = 2",
            ],
        ),
        (
            "2. Elementos de una ecuación",
            [
                "• Incógnita: letra que representa el valor desconocido (x).",
                "• Coeficiente: número que multiplica a la incógnita (en 3x, el coeficiente es 3).",
                "• Término independiente: número sin incógnita (en 2x + 7, el término independiente es 7).",
                "• Solución: valor de x que hace verdadera la igualdad.",
                "",
                "Ejemplo: en 2x + 5 = 13, la solución es x = 4 porque 2·4 + 5 = 13.",
            ],
        ),
        (
            "3. Propiedades de igualdad",
            [
                "Para resolver ecuaciones usamos propiedades que mantienen la igualdad:",
                "",
                "1) Si sumamos o restamos el mismo número a ambos lados, la igualdad se conserva.",
                "2) Si multiplicamos o dividimos ambos lados por el mismo número (≠ 0), se conserva.",
                "",
                "Estrategia general: despejar x dejándola sola en un lado de la ecuación.",
            ],
        ),
        (
            "4. Resolución paso a paso",
            [
                "Ejemplo 1: 2x + 5 = 13",
                "  Paso 1: Restar 5 en ambos lados → 2x = 8",
                "  Paso 2: Dividir por 2 en ambos lados → x = 4",
                "  Verificación: 2(4) + 5 = 8 + 5 = 13 ✓",
                "",
                "Ejemplo 2: 3x − 7 = 2x + 5",
                "  Paso 1: Restar 2x → x − 7 = 5",
                "  Paso 2: Sumar 7 → x = 12",
                "",
                "Ejemplo 3: 4(x + 1) = 20",
                "  Paso 1: Dividir por 4 → x + 1 = 5",
                "  Paso 2: Restar 1 → x = 4",
            ],
        ),
        (
            "5. Representación gráfica",
            [
                "Toda ecuación lineal con dos variables (y = mx + b) se representa como una recta.",
                "En 8° básico trabajamos principalmente ecuaciones con una incógnita.",
                "",
                "La solución x = 4 puede visualizarse en una recta numérica:",
                "  Marca el punto 4. Valores menores quedan a la izquierda; mayores, a la derecha.",
                "",
                "Conexión curricular: esta unidad prepara el estudio de funciones lineales en medios.",
            ],
        ),
        (
            "6. Problemas de la vida cotidiana",
            [
                "Problema 1 — Tarjeta de transporte:",
                "  Una tarjeta tiene $1.500 y cada viaje cuesta $750. Si después de n viajes",
                "  quedan $0, la ecuación es: 1.500 − 750n = 0 → n = 2 viajes.",
                "",
                "Problema 2 — Edades:",
                "  Juan tiene el doble de la edad de Ana. Si suman 36 años:",
                "  x + 2x = 36 → 3x = 36 → x = 12. Ana tiene 12 y Juan 24.",
                "",
                "Problema 3 — Compras:",
                "  3 cuadernos y 2 lápices cuestan $5.400. Si cada cuaderno cuesta $1.500:",
                "  3(1.500) + 2x = 5.400 → 4.500 + 2x = 5.400 → x = 450 (cada lápiz).",
            ],
        ),
        (
            "7. Estrategias de apoyo pedagógico (PIE/TEA)",
            [
                "• Usar balanza algebraica o material concreto para modelar igualdades.",
                "• Presentar pasos con pictogramas y colores (operación → ambos lados).",
                "• Fraccionar problemas en consignas cortas numeradas.",
                "• Ofrecer plantilla de verificación: «Reemplazo x = __ en la ecuación original».",
                "• Rutina visual: leer → identificar incógnita → plantear ecuación → resolver → verificar.",
            ],
        ),
        (
            "8. Actividades de práctica",
            [
                "Nivel 1 — Resolver:",
                "  a) x + 8 = 20    b) 5x = 35    c) 2x − 3 = 11    d) x/4 = 6",
                "",
                "Nivel 2 — Plantear y resolver:",
                "  e) Un número aumentado en 12 es 30.    f) El triple de un número es 27.",
                "",
                "Nivel 3 — Desafío:",
                "  g) 2(x + 3) = 18    h) 5x + 2 = 2x + 14",
                "",
                "Respuestas: a)12 b)7 c)7 d)24 e)x=18 f)x=9 g)x=6 h)x=4",
            ],
        ),
        (
            "9. Criterios de evaluación formativa",
            [
                "El estudiante demuestra aprendizaje cuando:",
                "• Identifica la incógnita en un problema verbal.",
                "• Aplica correctamente propiedades de igualdad.",
                "• Verifica su solución reemplazando en la ecuación original.",
                "• Explica con sus palabras el significado de la solución en contexto.",
            ],
        ),
        (
            "10. Glosario",
            [
                "Ecuación: igualdad con una o más incógnitas.",
                "Incógnita: valor desconocido, habitualmente x.",
                "Solución: valor que satisface la ecuación.",
                "Despejar: aislar la incógnita en un lado de la igualdad.",
                "Verificar: comprobar que la solución es correcta.",
            ],
        ),
    ]

    page = doc[-1]
    for title, body in sections:
        if y > PAGE_H - MARGIN - 60:
            page = doc.new_page(width=PAGE_W, height=PAGE_H)
            y = MARGIN + 10
        page.insert_text((MARGIN, y), title, fontsize=HEADING_SIZE, fontname="hebo")
        y += LINE + 6
        for line in body:
            if y > PAGE_H - MARGIN:
                page = doc.new_page(width=PAGE_W, height=PAGE_H)
                y = MARGIN + 10
            page.insert_text((MARGIN, y), line, fontsize=BODY_SIZE, fontname="helv")
            y += LINE
        y += 10

    # Pie de documento
    if y > PAGE_H - MARGIN - 30:
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        y = MARGIN
    y += 15
    write_lines(
        page,
        y,
        [
            "—",
            "Documento curricular para SAPIA — Unidad: Ecuaciones lineales",
            "Matemática 8° básico — Material de apoyo docente",
        ],
        size=9,
    )

    doc.save(OUTPUT)
    doc.close()
    return OUTPUT


if __name__ == "__main__":
    path = build_pdf()
    print(f"PDF generado: {path}")
    print(f"Tamaño: {path.stat().st_size / 1024:.1f} KB")

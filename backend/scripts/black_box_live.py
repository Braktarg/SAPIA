#!/usr/bin/env python3
"""Pruebas de caja negra — API HTTP contra servidor en ejecución (sin importar app)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8000"
DOCENTE = ("docente@demo.sapia.cl", "Sapia2026!")
ESTUDIANTE = ("antonia.vega@8vo.demo.sapia.cl", "Sapia2026!")


def req(method: str, path: str, token: str | None = None, body: dict | None = None) -> tuple[int, dict | str]:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def login(email: str, password: str) -> str:
    code, data = req("POST", "/api/v1/auth/login", body={"email": email, "password": password})
    assert code == 200, f"login {email}: {code} {data}"
    return data["access_token"]


def run() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" - {detail}" if detail else ""))

    print("=== Caja negra API (HTTP, staging localhost:8000) ===\n")

    code, _ = req("GET", "/health")
    check("BB-API-001 Health público", code == 200, f"HTTP {code}")

    code, _ = req("GET", "/api/v1/auth/me")
    check("BB-API-002 /me sin token -> 401/403", code in (401, 403), f"HTTP {code}")

    teacher_token = login(*DOCENTE)
    code, me = req("GET", "/api/v1/auth/me", token=teacher_token)
    check("BB-API-003 Login docente + /me", code == 200 and me.get("role") == "teacher")

    student_token = login(*ESTUDIANTE)
    code, _ = req("GET", "/api/v1/recommendations/inbox", token=student_token)
    check("BB-API-004 RBAC estudiante no inbox docente", code == 403, f"HTTP {code}")

    code, items = req("GET", "/api/v1/diagnostic/items", token=student_token)
    check("BB-API-005 Test diagnóstico 12 ítems", code == 200 and len(items) == 12, f"n={len(items) if isinstance(items, list) else '?'}")

    code, inbox = req("GET", "/api/v1/recommendations/inbox", token=teacher_token)
    check("BB-API-006 Bandeja MitL docente", code == 200 and isinstance(inbox, list))

    code, _ = req("GET", "/api/v1/student/recommendations", token=student_token)
    check("BB-API-007 Vista estudiante recomendaciones", code == 200)

    code, _ = req("GET", "/openapi.json")
    check("BB-API-008 Contrato OpenAPI accesible", code == 200, f"HTTP {code}")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\nResumen caja negra API: {passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(run())

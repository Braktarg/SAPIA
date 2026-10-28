#!/usr/bin/env python3
"""Prueba de caja negra UI — Playwright contra frontend en ejecución."""

from __future__ import annotations

import sys
import time
import urllib.request

import httpx
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:3000"
API_URL = "http://localhost:8000"
DOCENTE = ("docente@demo.sapia.cl", "Sapia2026!")


def wait_for_app() -> None:
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{BASE_URL}/login", timeout=2)
            urllib.request.urlopen(f"{API_URL}/health", timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Frontend o API no responden")


def run() -> int:
    print("=== Caja negra UI (Playwright, localhost:3000) ===\n")
    wait_for_app()

    results: list[tuple[str, bool]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # BB-UI-001: página login renderiza
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        ok = "/login" in page.url and page.locator('input.input[type="email"]').count() > 0
        results.append(("BB-UI-001 Login visible", ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] BB-UI-001 Login visible")

        # BB-UI-002: login formulario (caja negra — sin cookies previas)
        page.locator('input.input[type="email"]').fill(DOCENTE[0])
        page.locator('input.input[type="password"]').fill(DOCENTE[1])
        page.locator("button.btn-login").click()
        page.wait_for_url("**/docente**", timeout=15000)
        ok = "/docente" in page.url
        results.append(("BB-UI-002 Login docente redirige", ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] BB-UI-002 Login docente -> /docente ({page.url})")

        # BB-UI-003: home docente carga
        page.goto(f"{BASE_URL}/docente/recomendaciones", wait_until="networkidle")
        ok = "/login" not in page.url
        results.append(("BB-UI-003 Bandeja MitL accesible", ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] BB-UI-003 Bandeja MitL ({page.url})")

        # BB-UI-004: estudiante bloqueado en ruta docente (nueva sesión)
        ctx2 = browser.new_context()
        page2 = ctx2.new_page()
        resp = httpx.post(
            f"{API_URL}/api/v1/auth/login",
            json={"email": "antonia.vega@8vo.demo.sapia.cl", "password": "Sapia2026!"},
            timeout=15,
        )
        token = resp.json()["access_token"]
        role = httpx.get(
            f"{API_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        ).json()["role"]
        ctx2.add_cookies([
            {"name": "sapia_token", "value": token, "domain": "localhost", "path": "/"},
            {"name": "sapia_role", "value": role, "domain": "localhost", "path": "/"},
        ])
        page2.goto(f"{BASE_URL}/docente", wait_until="networkidle")
        ok = "/estudiante" in page2.url or "/login" in page2.url
        results.append(("BB-UI-004 RBAC estudiante no /docente", ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] BB-UI-004 RBAC estudiante ({page2.url})")

        browser.close()

    passed = sum(1 for _, ok in results if ok)
    print(f"\nResumen caja negra UI: {passed}/{len(results)} PASS")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(run())

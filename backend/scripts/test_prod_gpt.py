"""Prueba generación GPT en producción."""

import time

import httpx

BASE = "https://api-production-7d048.up.railway.app/api/v1"


def main() -> None:
    with httpx.Client(timeout=180) as client:
        token = client.post(
            f"{BASE}/auth/login",
            json={"email": "docente@demo.sapia.cl", "password": "Sapia2026!"},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        students = client.get(f"{BASE}/students", headers=headers).json()
        student = next(
            (s for s in students if "Benjam" in s.get("full_name", "")),
            next(s for s in students if s["has_profile"]),
        )
        t0 = time.time()
        resp = client.post(
            f"{BASE}/recommendations/generate",
            headers=headers,
            json={
                "student_id": student["id"],
                "course_id": 1,
                "planning_topic": "Ecuaciones lineales",
                "ai_consent_accepted": True,
            },
        )
        elapsed = round(time.time() - t0, 1)
        print("HTTP", resp.status_code, "elapsed", elapsed, "s")
        if resp.status_code != 201:
            print(resp.text[:500])
            return
        rec = resp.json()
        print("student", student["full_name"])
        print("degraded_mode", rec.get("degraded_mode"))
        print("title", rec.get("title"))
        body = rec.get("body") or ""
        print("body_len", len(body))
        print("body_start", body[:200].replace("\n", " "))
        print("has_template_marker", "Propuesta de clase para" in body and "Anclaje curricular (RAG)" in body)


if __name__ == "__main__":
    main()

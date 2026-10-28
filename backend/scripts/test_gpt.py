"""Prueba rápida de generación GPT en SAPIA."""

import httpx

BASE = "http://localhost:8000/api/v1"


def main() -> None:
    with httpx.Client(timeout=180) as client:
        token = client.post(
            f"{BASE}/auth/login",
            json={"email": "docente@demo.sapia.cl", "password": "Sapia2026!"},
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        students = client.get(f"{BASE}/students", headers=headers).json()
        student = next(s for s in students if s["has_profile"])
        resp = client.post(
            f"{BASE}/recommendations/generate",
            headers=headers,
            json={
                "student_id": student["id"],
                "course_id": 1,
                "planning_topic": "Ecuaciones lineales",
            },
        )
        print("HTTP", resp.status_code)
        if resp.status_code != 201:
            print(resp.text)
            return
        rec = resp.json()
        print("Estudiante:", student["full_name"])
        print("Modo degradado:", rec.get("degraded_mode"))
        print("Titulo:", rec.get("title"))
        print("Cuerpo (inicio):", (rec.get("body") or "")[:350])
        print("Explicacion (inicio):", (rec.get("explanation") or "")[:250])


if __name__ == "__main__":
    main()

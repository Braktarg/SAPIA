#!/usr/bin/env python3
"""Prueba de carga / estrés — HTTP concurrente contra API en ejecución."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "http://localhost:8000"


def fetch(url: str, headers: dict | None = None) -> tuple[bool, float]:
    start = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers=headers or {}, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status == 200
    except (urllib.error.URLError, TimeoutError):
        ok = False
    return ok, (time.perf_counter() - start) * 1000


def get_token(base: str, email: str, password: str) -> str | None:
    body = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{base}/api/v1/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())["access_token"]
    except (urllib.error.URLError, TimeoutError, KeyError):
        return None


def run_load(
    *,
    base: str,
    users: int,
    duration_sec: int,
    mix_auth: bool,
    email: str,
    password: str,
) -> dict:
    token = get_token(base, email, password) if mix_auth else None
    auth_headers = {"Authorization": f"Bearer {token}"} if token else None

    latencies: list[float] = []
    ok_count = 0
    fail_count = 0
    deadline = time.time() + duration_sec

    def worker() -> tuple[bool, float]:
        if mix_auth and auth_headers and (ok_count + fail_count) % 3 == 0:
            return fetch(f"{base}/api/v1/auth/me", auth_headers)
        return fetch(f"{base}/health")

    with concurrent.futures.ThreadPoolExecutor(max_workers=users) as pool:
        pending: set[concurrent.futures.Future] = set()
        while time.time() < deadline or pending:
            while len(pending) < users and time.time() < deadline:
                pending.add(pool.submit(worker))
            if not pending:
                break
            done, pending = concurrent.futures.wait(
                pending, timeout=0.5, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for fut in done:
                ok, ms = fut.result()
                latencies.append(ms)
                if ok:
                    ok_count += 1
                else:
                    fail_count += 1

    total = ok_count + fail_count
    p95 = sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0
    return {
        "endpoint_mix": "70% /health + 30% /auth/me" if mix_auth else "/health",
        "users": users,
        "duration_sec": duration_sec,
        "requests": total,
        "ok": ok_count,
        "fail": fail_count,
        "success_rate_pct": round(100 * ok_count / total, 2) if total else 0,
        "rps": round(total / duration_sec, 1),
        "p50_ms": round(statistics.median(latencies), 1) if latencies else 0,
        "p95_ms": round(p95, 1),
        "p99_ms": round(sorted(latencies)[max(0, int(len(latencies) * 0.99) - 1)], 1) if latencies else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Load test SAPIA API")
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--mix-auth", action="store_true", help="Mezclar /health y /auth/me")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--email", default="docente@demo.sapia.cl")
    parser.add_argument("--password", default="Sapia2026!")
    args = parser.parse_args()

    print(f"=== Prueba de carga ({args.users} usuarios, {args.duration}s) ===")
    result = run_load(
        base=args.base.rstrip("/"),
        users=args.users,
        duration_sec=args.duration,
        mix_auth=args.mix_auth,
        email=args.email,
        password=args.password,
    )
    for k, v in result.items():
        print(f"  {k}: {v}")

    ok = result["fail"] == 0 and result["success_rate_pct"] >= 99.0
    print(f"\nResultado: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

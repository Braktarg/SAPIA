#!/usr/bin/env python3
"""Ejecuta suite QA Release 1 con cobertura de módulos críticos (S8)."""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

CRITICAL_COV = [
    "app.core.security",
    "app.services.auth_service",
    "ml.predictor",
    "rag.generate",
    "rag.chunking",
    "rag.embeddings",
    "rag.retrieve",
    "app.services.recommendation_service",
    "app.services.audit_service",
]

MIN_COVERAGE = 70


def main() -> int:
    cov_args = []
    for mod in CRITICAL_COV:
        cov_args.extend(["--cov", mod])

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-q",
        "--cov-report=term-missing:skip-covered",
        f"--cov-fail-under={MIN_COVERAGE}",
        *cov_args,
    ]
    print("SAPIA QA Release 1")
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=BACKEND)
    if result.returncode == 0:
        print(f"\nOK - cobertura modulos criticos >= {MIN_COVERAGE}%")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

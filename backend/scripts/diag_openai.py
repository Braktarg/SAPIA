"""Diagnóstico OpenAI en Railway (ejecutar: railway run python scripts/diag_openai.py)."""

from app.core.config import settings
from openai import OpenAI


def main() -> None:
    print("key_len", len(settings.openai_api_key))
    print("model", settings.openai_chat_model)
    client = OpenAI(api_key=settings.openai_api_key, timeout=60)
    try:
        r = client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[{"role": "user", "content": "Responde solo: OK"}],
            max_tokens=5,
        )
        print("chat_ok", (r.choices[0].message.content or "").strip())
    except Exception as exc:
        print("chat_fail", type(exc).__name__, str(exc)[:400])


if __name__ == "__main__":
    main()

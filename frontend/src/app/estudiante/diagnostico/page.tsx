"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { DiagnosticItem, CONSENT_VERSION, getDiagnosticItems, submitDiagnostic } from "@/lib/api";

export default function DiagnosticoPage() {
  const router = useRouter();
  const [items, setItems] = useState<DiagnosticItem[]>([]);
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<number, { value: number; ms: number }>>({});
  const [stepStarted, setStepStarted] = useState(Date.now());
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [consentAccepted, setConsentAccepted] = useState(false);

  useEffect(() => {
    getDiagnosticItems()
      .then(setItems)
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  const current = items[step];

  function selectOption(value: number) {
    if (!current) return;
    const ms = Date.now() - stepStarted;
    setAnswers((prev) => ({ ...prev, [current.id]: { value, ms } }));
    if (step < items.length - 1) {
      setStep(step + 1);
      setStepStarted(Date.now());
    }
  }

  async function finish() {
    if (!consentAccepted) {
      setError("Debe aceptar el consentimiento informado para continuar.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const payload = items.map((it) => {
        const a = answers[it.id];
        return {
          item_id: it.id,
          answer_value: a?.value ?? 0,
          response_ms: a?.ms ?? 0,
          skipped: a === undefined,
        };
      });
      await submitDiagnostic(payload, {
        consent_accepted: true,
        consent_version: CONSENT_VERSION,
      });
      router.push("/estudiante/recomendaciones");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <AppShell variant="student" title="Test diagnóstico" subtitle="Cargando…">
        <div className="loading-page">Cargando test…</div>
      </AppShell>
    );
  }
  if (!current) return null;

  const allAnswered = items.every((it) => answers[it.id] !== undefined);
  const progressPct = ((step + 1) / items.length) * 100;

  return (
    <AppShell
      variant="student"
      title="Test de perfil inicial"
      subtitle={`Pregunta ${step + 1} de ${items.length}`}
    >
      <div style={{ maxWidth: 560 }}>
        <div className="diagnostic-progress">
          <div className="diagnostic-progress-fill" style={{ width: `${progressPct}%` }} />
        </div>

        <div className="card">
          <p style={{ fontSize: "1.1rem", marginBottom: "1.25rem" }}>{current.question_text}</p>
          {current.options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => selectOption(opt.value)}
              className={`option-btn ${answers[current.id]?.value === opt.value ? "selected" : ""}`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="btn-group" style={{ marginTop: "1rem" }}>
          <button type="button" className="btn btn-secondary" disabled={step === 0} onClick={() => setStep(step - 1)}>
            Anterior
          </button>
          {step < items.length - 1 ? (
            <button
              type="button"
              className="btn btn-primary"
              disabled={!answers[current.id]}
              onClick={() => setStep(step + 1)}
            >
              Siguiente
            </button>
          ) : (
            <>
              <label className="field checkbox-field" style={{ flex: "1 1 100%", marginBottom: "0.5rem" }}>
                <input
                  type="checkbox"
                  checked={consentAccepted}
                  onChange={(e) => setConsentAccepted(e.target.checked)}
                />
                <span>
                  Acepto el tratamiento de mis respuestas para generar mi perfil pedagógico (Ley 19.628 / 21.719,
                  versión TyC {CONSENT_VERSION}).
                </span>
              </label>
              <button
                type="button"
                className="btn btn-primary"
                disabled={!allAnswered || submitting || !consentAccepted}
                onClick={finish}
              >
                {submitting ? "Generando perfil…" : "Finalizar y generar perfil"}
              </button>
            </>
          )}
        </div>
        {error && <div className="alert alert-error" style={{ marginTop: "1rem" }}>{error}</div>}
      </div>
    </AppShell>
  );
}

"use client";

import { useState } from "react";
import { submitStudentDifficultyFeedback } from "@/lib/api";

const LABELS: Record<number, string> = {
  1: "Muy fácil",
  2: "Fácil",
  3: "Regular",
  4: "Difícil",
  5: "Muy difícil",
};

type Props = {
  recommendationId: number;
  initialRating: number | null;
  onSaved: (rating: number) => void;
};

export function DifficultyFeedback({ recommendationId, initialRating, onSaved }: Props) {
  const [rating, setRating] = useState<number | null>(initialRating);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(initialRating != null);

  async function save(value: number) {
    setBusy(true);
    setError("");
    try {
      await submitStudentDifficultyFeedback(recommendationId, value);
      setRating(value);
      setSaved(true);
      onSaved(value);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="difficulty-feedback card-inset">
      <h4>¿Qué tan difícil te resultó esta actividad?</h4>
      <p className="text-muted">Tu respuesta ayuda a tu docente a ajustar los apoyos (escala 1 a 5).</p>
      <div className="difficulty-scale" role="group" aria-label="Dificultad percibida">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            className={`difficulty-btn ${rating === n ? "selected" : ""}`}
            disabled={busy}
            onClick={() => save(n)}
            aria-pressed={rating === n}
            title={LABELS[n]}
          >
            <span className="difficulty-num">{n}</span>
            <span className="difficulty-label">{LABELS[n]}</span>
          </button>
        ))}
      </div>
      {saved && rating != null && (
        <p className="alert alert-success" style={{ marginTop: "0.75rem" }}>
          Gracias. Registramos: {LABELS[rating]} ({rating}/5).
        </p>
      )}
      {error && <p className="alert alert-error">{error}</p>}
    </div>
  );
}

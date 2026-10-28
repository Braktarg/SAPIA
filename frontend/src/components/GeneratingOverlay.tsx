"use client";

import { useEffect, useState } from "react";

const STUDENT_STEPS = [
  "Recuperando material curricular (RAG)…",
  "Analizando perfil pedagógico del estudiante…",
  "Generando propuesta personalizada con IA…",
  "Preparando explicación pedagógica (XAI)…",
];

const COURSE_STEPS = [
  "Recuperando material curricular (RAG)…",
  "Analizando perfiles del curso…",
  "Generando planificación grupal con IA…",
  "Preparando explicación pedagógica (XAI)…",
];

const BATCH_EXTRA = "Generando recomendaciones individuales en paralelo…";

type Props = {
  active: boolean;
  mode?: "student" | "course";
  studentName?: string;
  topic?: string;
  batchStudentCount?: number;
  includePerStudent?: boolean;
};

function estimateHint(mode: "student" | "course", batchStudentCount: number, includePerStudent: boolean): string {
  if (mode === "student") {
    return "Esto puede tomar 15–45 segundos con GPT.";
  }
  if (includePerStudent && batchStudentCount > 0) {
    const mins = Math.max(1, Math.ceil(batchStudentCount / 4));
    return `Plan grupal + ${batchStudentCount} estudiantes: puede tomar ${mins}–${mins + 2} minutos con GPT. No cierres esta ventana.`;
  }
  return "Planificación grupal: puede tomar 30–90 segundos con GPT.";
}

export function GeneratingOverlay({
  active,
  mode = "student",
  studentName,
  topic,
  batchStudentCount = 0,
  includePerStudent = false,
}: Props) {
  const steps = mode === "course" ? COURSE_STEPS : STUDENT_STEPS;
  const [stepIndex, setStepIndex] = useState(0);
  const showBatchExtra = mode === "course" && includePerStudent && batchStudentCount > 0;

  useEffect(() => {
    if (!active) {
      setStepIndex(0);
      return;
    }
    const intervalMs = mode === "course" && includePerStudent ? 4500 : 2200;
    const id = setInterval(() => {
      setStepIndex((i) => {
        const max = showBatchExtra ? steps.length : steps.length - 1;
        return i < max ? i + 1 : i;
      });
    }, intervalMs);
    return () => clearInterval(id);
  }, [active, mode, includePerStudent, showBatchExtra, steps.length]);

  if (!active) return null;

  const allSteps = showBatchExtra ? [...steps, BATCH_EXTRA] : steps;

  return (
    <div className="generating-overlay" role="status" aria-live="polite">
      <div className="generating-card">
        <div className="generating-spinner" />
        <h3>Generando recomendación</h3>
        {studentName && topic && (
          <p className="text-muted">
            {studentName} · <em>{topic}</em>
          </p>
        )}
        <ul className="generating-steps">
          {allSteps.map((label, i) => (
            <li key={label} className={i <= stepIndex ? "active" : ""}>
              {label}
            </li>
          ))}
        </ul>
        <p className="generating-hint">
          {estimateHint(mode, batchStudentCount, includePerStudent)}
        </p>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import type { TeacherSetupStatus } from "@/lib/api";

type Props = {
  status: TeacherSetupStatus | null;
  onDismiss?: () => void;
};

const STEPS = [
  {
    key: "docs",
    label: "Subir material curricular (PDF)",
    href: "/docente/biblioteca",
    done: (s: TeacherSetupStatus) => s.has_indexed_documents,
    detail: (s: TeacherSetupStatus) => `${s.indexed_documents_count} documento(s) indexado(s)`,
  },
  {
    key: "profiles",
    label: "Revisar perfiles de estudiantes",
    href: "/docente/estudiantes",
    done: (s: TeacherSetupStatus) => s.students_with_profile > 0,
    detail: (s: TeacherSetupStatus) =>
      `${s.students_with_profile}/${s.students_total} con perfil diagnóstico`,
  },
  {
    key: "generate",
    label: "Generar recomendación con IA",
    href: "/docente/recomendaciones",
    done: (s: TeacherSetupStatus) => s.has_generated_recommendation,
    detail: (s: TeacherSetupStatus) => `${s.recommendations_total} propuesta(s) generada(s)`,
  },
  {
    key: "mitl",
    label: "Validar y publicar al estudiante (MitL)",
    href: "/docente/recomendaciones",
    done: (s: TeacherSetupStatus) => s.has_published_recommendation,
    detail: (s: TeacherSetupStatus) => `${s.recommendations_published} publicada(s)`,
  },
  {
    key: "audit",
    label: "Revisar trazabilidad y exportar CSV",
    href: "/docente/panel",
    done: (s: TeacherSetupStatus) => s.has_published_recommendation,
    detail: () => "Panel de seguimiento PIE",
  },
];

export function TeacherOnboarding({ status, onDismiss }: Props) {
  if (!status) return null;

  const completed = STEPS.filter((step) => step.done(status)).length;
  const allDone = completed === STEPS.length;
  const pct = Math.round((completed / STEPS.length) * 100);

  if (allDone && onDismiss) {
    return (
      <div className="onboarding-card onboarding-done">
        <div>
          <strong>Demo lista para presentación</strong>
          <p className="text-muted">Completaste el recorrido docente de SAPIA.</p>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={onDismiss}>
          Ocultar
        </button>
      </div>
    );
  }

  return (
    <div className="onboarding-card">
      <div className="onboarding-header">
        <div>
          <h2 className="card-title" style={{ marginBottom: "0.25rem" }}>
            Guía demo — {status.course_name ?? "tu curso"}
          </h2>
          <p className="text-muted">
            Recorrido sugerido para defensa de tesis · {completed}/{STEPS.length} pasos
          </p>
        </div>
        <div className="onboarding-pct">{pct}%</div>
      </div>
      <div className="onboarding-progress">
        <div className="onboarding-progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <ol className="onboarding-steps">
        {STEPS.map((step, i) => {
          const done = step.done(status);
          return (
            <li key={step.key} className={`onboarding-step ${done ? "done" : ""}`}>
              <span className="onboarding-step-num">{done ? "✓" : i + 1}</span>
              <div className="onboarding-step-body">
                <Link href={step.href} className="onboarding-step-link">
                  {step.label}
                </Link>
                <span className="list-item-meta">{step.detail(status)}</span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

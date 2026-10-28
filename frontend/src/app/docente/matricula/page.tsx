"use client";

import { AppShell } from "@/components/AppShell";
import { EnrollmentPanel } from "@/components/EnrollmentPanel";

export default function MatriculaDocentePage() {
  return (
    <AppShell
      variant="teacher"
      title="Matrícula del curso"
      subtitle="Asociar estudiantes a secciones — requerimiento RF-04"
    >
      <EnrollmentPanel />
      <p className="institutional-footer">
        Los estudiantes matriculados aparecerán en Fichas, Recomendaciones y el panel PIE del mismo curso.
      </p>
    </AppShell>
  );
}

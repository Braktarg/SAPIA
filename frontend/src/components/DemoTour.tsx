"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const STEPS = [
  {
    title: "Bienvenida PIE",
    body: "SAPIA apoya la planificación diferenciada para estudiantes neurodivergentes en aula regular. La IA propone; usted dispone (MitL).",
    href: "/docente",
  },
  {
    title: "Biblioteca curricular",
    body: "Suba el PDF de su unidad. El sistema lo fragmenta e indexa para que la IA cite solo su material oficial.",
    href: "/docente/biblioteca",
    selector: '[data-tour="nav-biblioteca"]',
  },
  {
    title: "Perfiles de estudiantes",
    body: "Revise el radar de perfil pedagógico generado por el test diagnóstico (Random Forest).",
    href: "/docente/estudiantes",
    selector: '[data-tour="nav-estudiantes"]',
  },
  {
    title: "Recomendación con IA",
    body: "Genere una propuesta personalizada cruzando perfil + RAG. Valide, edite o rechace antes de publicar.",
    href: "/docente/recomendaciones",
    selector: '[data-tour="nav-recomendaciones"]',
  },
  {
    title: "Panel y trazabilidad",
    body: "Exporte CSV/PDF y revise el ciclo RAG → IA → docente → estudiante para reuniones PIE.",
    href: "/docente/panel",
    selector: '[data-tour="nav-panel"]',
  },
];

type Props = {
  role: "teacher" | "student";
};

export function DemoTour({ role }: Props) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (role !== "teacher") return;
    const done = localStorage.getItem("sapia_demo_tour_done") === "1";
    if (!done) setOpen(true);
  }, [role]);

  if (role !== "teacher" || !open) return null;

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  function close(save = true) {
    if (save) localStorage.setItem("sapia_demo_tour_done", "1");
    setOpen(false);
  }

  function next() {
    if (isLast) close();
    else setStep((s) => s + 1);
  }

  return (
    <div className="demo-tour-overlay" role="dialog" aria-modal="true">
      <div className="demo-tour-card">
        <p className="demo-tour-step">
          Paso {step + 1} de {STEPS.length}
        </p>
        <h3>{current.title}</h3>
        <p>{current.body}</p>
        <div className="btn-group">
          {step > 0 && (
            <button type="button" className="btn btn-secondary" onClick={() => setStep((s) => s - 1)}>
              Anterior
            </button>
          )}
          <Link href={current.href} className="btn btn-secondary" onClick={() => setStep(step)}>
            Ir a pantalla
          </Link>
          <button type="button" className="btn btn-primary" onClick={next}>
            {isLast ? "Finalizar tour" : "Siguiente"}
          </button>
        </div>
        <button type="button" className="demo-tour-skip" onClick={() => close()}>
          Omitir tour
        </button>
      </div>
    </div>
  );
}

export function resetDemoTour() {
  localStorage.removeItem("sapia_demo_tour_done");
}

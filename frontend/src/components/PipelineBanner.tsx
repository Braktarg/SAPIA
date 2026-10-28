const STEPS = [
  { label: "Perfil RF", desc: "Test diagnóstico" },
  { label: "RAG", desc: "PDF curricular" },
  { label: "IA + XAI", desc: "Recomendación" },
  { label: "MitL", desc: "Validación docente" },
  { label: "Estudiante", desc: "Recurso publicado" },
];

export function PipelineBanner() {
  return (
    <div className="pipeline-banner">
      <p className="pipeline-banner-label">Flujo crítico Release 1</p>
      <div className="pipeline-steps">
        {STEPS.map((step, i) => (
          <div key={step.label} className="pipeline-step-wrap">
            <div className="pipeline-step">
              <span className="pipeline-step-num">{i + 1}</span>
              <strong>{step.label}</strong>
              <small>{step.desc}</small>
            </div>
            {i < STEPS.length - 1 && <span className="pipeline-arrow" aria-hidden>→</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

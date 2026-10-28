"use client";

import { CitationCard } from "@/components/CitationCard";

export type EvidenceChainStep = {
  order: number;
  stage: string;
  label: string;
  detail: string;
  chunk_id?: number | null;
};

export type EvidenceRow = {
  evidence: string;
  decision: string;
  descriptor_key?: string | null;
  chunk_id?: number | null;
  rationale?: string | null;
};

export type EvidenceChain = {
  steps: EvidenceChainStep[];
  evidence_rows: EvidenceRow[];
  curricular_anchor?: {
    oa: string;
    unit_name: string;
    concepts: string[];
    main_activity: string;
    chunk_id?: number | null;
  };
  tier_assignment?: { A: string[]; B: string[]; C: string[] };
  descriptor_scores?: {
    key: string;
    label: string;
    value: number;
    tier: string;
  }[];
  topic_alignment?: {
    planning_topic: string;
    canonical_topic: string;
    aligned: boolean;
    note: string;
  };
  profile_synthesis?: {
    strengths: { key: string; label: string; value: number }[];
    supports: { key: string; label: string; value: number }[];
  };
  citations?: string[];
};

export type SourceChunkRef = {
  id: number;
  unit_name: string;
  snippet: string;
  score: number;
};

type Props = {
  chain: EvidenceChain;
  sourceChunks?: SourceChunkRef[];
};

const STAGE_LABELS: Record<string, string> = {
  curricular: "Curricular",
  profile: "Perfil",
  generation: "Generación",
  recommendation: "Recomendación",
  mitl: "MitL",
};

export function EvidenceChainPanel({ chain, sourceChunks = [] }: Props) {
  const rows = chain.evidence_rows ?? [];
  const steps = [...(chain.steps ?? [])].sort((a, b) => a.order - b.order);
  const synthesis = chain.profile_synthesis;
  const showSourceChunks = sourceChunks.length > 0;
  const showCitationStrings = !showSourceChunks && (chain.citations?.length ?? 0) > 0;

  return (
    <div className="evidence-chain-panel card-inset">
      <h4>Cadena de evidencia</h4>
      <p className="text-muted" style={{ marginBottom: "0.75rem" }}>
        Trazabilidad: PDF → perfil → decisión pedagógica → validación docente.
      </p>

      {chain.topic_alignment && !chain.topic_alignment.aligned && (
        <div className="alert alert-info" style={{ marginBottom: "0.75rem" }}>
          {chain.topic_alignment.note}
        </div>
      )}

      {chain.curricular_anchor && (
        <div className="evidence-anchor">
          <strong>Anclaje curricular:</strong> {chain.curricular_anchor.oa}
          <span className="text-muted"> — Unidad «{chain.curricular_anchor.unit_name}»</span>
        </div>
      )}

      <ol className="evidence-steps">
        {steps.map((step) => (
          <li key={step.order} className={`evidence-step stage-${step.stage}`}>
            <span className="evidence-step-badge">{STAGE_LABELS[step.stage] ?? step.stage}</span>
            <div>
              <strong>{step.label}</strong>
              <p className="text-muted">{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>

      {synthesis && (synthesis.strengths.length > 0 || synthesis.supports.length > 0) && (
        <div className="evidence-profile-synthesis">
          <strong>Síntesis del perfil</strong>
          <div className="evidence-synthesis-grid">
            {synthesis.strengths.length > 0 && (
              <div>
                <span className="evidence-synthesis-label">Fortalezas</span>
                <ul>
                  {synthesis.strengths.map((d) => (
                    <li key={d.key}>
                      {d.label} <span className="text-muted">({d.value.toFixed(2)})</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {synthesis.supports.length > 0 && (
              <div>
                <span className="evidence-synthesis-label">Apoyos prioritarios</span>
                <ul>
                  {synthesis.supports.map((d) => (
                    <li key={d.key}>
                      {d.label} <span className="text-muted">({d.value.toFixed(2)})</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {chain.descriptor_scores && chain.descriptor_scores.length > 0 && (
        <div className="evidence-descriptors">
          <strong>Puntajes del diagnóstico</strong>
          <p className="text-muted" style={{ margin: "0.25rem 0 0.5rem" }}>
            ≥0,85 fortaleza · 0,60–0,85 apoyo moderado · &lt;0,60 apoyo intensivo
          </p>
          <ul>
            {chain.descriptor_scores.map((d) => (
              <li key={d.key}>
                {d.label}: <strong>{d.value.toFixed(2)}</strong> ({d.tier})
              </li>
            ))}
          </ul>
        </div>
      )}

      {rows.length > 0 && (
        <div className="evidence-table-wrap">
          <table className="evidence-table">
            <thead>
              <tr>
                <th>Evidencia encontrada</th>
                <th>Decisión pedagógica</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  <td>{row.evidence}</td>
                  <td>
                    <div>{row.decision}</div>
                    {row.rationale && (
                      <p className="evidence-rationale text-muted">{row.rationale}</p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {chain.tier_assignment && (chain.tier_assignment.A?.length || chain.tier_assignment.C?.length) && (
        <div className="evidence-tiers">
          <strong>Asignación por niveles</strong>
          <ul>
            <li>
              <strong>Nivel A:</strong>{" "}
              {chain.tier_assignment.A?.length ? chain.tier_assignment.A.join(", ") : "—"}
            </li>
            <li>
              <strong>Nivel B:</strong>{" "}
              {chain.tier_assignment.B?.length ? chain.tier_assignment.B.join(", ") : "—"}
            </li>
            <li>
              <strong>Nivel C:</strong>{" "}
              {chain.tier_assignment.C?.length ? chain.tier_assignment.C.join(", ") : "—"}
            </li>
          </ul>
        </div>
      )}

      {showSourceChunks && (
        <div className="evidence-sources">
          <strong>Fuentes curriculares (RAG)</strong>
          <ul className="citation-list">
            {sourceChunks.map((c) => (
              <CitationCard
                key={c.id}
                unitName={c.unit_name}
                snippet={c.snippet}
                score={c.score}
              />
            ))}
          </ul>
        </div>
      )}

      {showCitationStrings && (
        <div className="evidence-sources">
          <strong>Fragmentos curriculares citados</strong>
          <ul>
            {chain.citations!.map((c, i) => (
              <li key={i} className="text-muted">
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

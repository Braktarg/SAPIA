type MitlInfo = {
  action: string;
  reason: string | null;
  original_body: string | null;
  validated_at: string | null;
};

type Props = {
  status: string;
  currentBody: string;
  mitl: MitlInfo | null;
};

export function MitLCompare({ status, currentBody, mitl }: Props) {
  if (status === "accepted") {
    return (
      <div className="mitl-compare mitl-accepted">
        <h4>Validación docente</h4>
        <p className="text-muted">
          El docente <strong>aceptó</strong> la propuesta de la IA sin modificaciones.
        </p>
      </div>
    );
  }

  if (status === "edited" && mitl?.original_body) {
    return (
      <div className="mitl-compare">
        <h4>Comparación MitL — IA vs. versión publicada</h4>
        {mitl.reason && (
          <p className="text-muted">
            <strong>Motivo:</strong> {mitl.reason}
          </p>
        )}
        <div className="compare-grid">
          <div className="compare-col">
            <span className="compare-tag">Propuesta original (IA)</span>
            <div className="compare-body">{mitl.original_body}</div>
          </div>
          <div className="compare-col compare-col-published">
            <span className="compare-tag">Versión publicada (docente)</span>
            <div className="compare-body">{currentBody}</div>
          </div>
        </div>
      </div>
    );
  }

  if (status === "rejected" && mitl) {
    return (
      <div className="mitl-compare mitl-rejected">
        <h4>Recomendación rechazada</h4>
        <p className="text-muted">{mitl.reason}</p>
      </div>
    );
  }

  return null;
}

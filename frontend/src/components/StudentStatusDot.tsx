export type AttentionLevel = "ok" | "no_profile" | "pending" | "alert" | "monitor";

const CONFIG: Record<AttentionLevel, { color: string; label: string }> = {
  ok: { color: "#059669", label: "En seguimiento" },
  monitor: { color: "#6366f1", label: "Sin recomendaciones" },
  pending: { color: "#d97706", label: "MitL pendiente" },
  no_profile: { color: "#94a3b8", label: "Sin test diagnóstico" },
  alert: { color: "#dc2626", label: "Requiere atención PIE" },
};

type Props = {
  level: AttentionLevel;
  showLabel?: boolean;
};

export function StudentStatusDot({ level, showLabel }: Props) {
  const cfg = CONFIG[level] ?? CONFIG.monitor;
  return (
    <span className="status-dot-wrap" title={cfg.label}>
      <span className="status-dot" style={{ background: cfg.color }} />
      {showLabel && <span className="status-dot-label">{cfg.label}</span>}
    </span>
  );
}

export function attentionLabel(level: AttentionLevel): string {
  return CONFIG[level]?.label ?? level;
}

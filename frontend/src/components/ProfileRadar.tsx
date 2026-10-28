type Descriptor = { label: string; value: number };

type Props = {
  descriptors: Descriptor[];
  size?: number;
};

export function ProfileRadar({ descriptors, size = 200 }: Props) {
  if (descriptors.length === 0) return null;

  const cx = size / 2;
  const cy = size / 2;
  const radius = size * 0.36;
  const n = descriptors.length;
  const angleStep = (Math.PI * 2) / n;

  function point(i: number, scale: number) {
    const angle = -Math.PI / 2 + i * angleStep;
    return {
      x: cx + Math.cos(angle) * radius * scale,
      y: cy + Math.sin(angle) * radius * scale,
    };
  }

  const gridLevels = [0.25, 0.5, 0.75, 1];
  const dataPoints = descriptors.map((d, i) => point(i, Math.min(d.value, 1)));
  const polygon = dataPoints.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <div className="profile-radar-wrap">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Radar de perfil pedagógico">
        {gridLevels.map((level) => (
          <polygon
            key={level}
            points={descriptors.map((_, i) => {
              const p = point(i, level);
              return `${p.x},${p.y}`;
            }).join(" ")}
            fill="none"
            stroke="var(--border)"
            strokeWidth="1"
          />
        ))}
        {descriptors.map((d, i) => {
          const outer = point(i, 1);
          const inner = point(i, 0);
          return (
            <line
              key={d.label}
              x1={inner.x}
              y1={inner.y}
              x2={outer.x}
              y2={outer.y}
              stroke="var(--border)"
              strokeWidth="1"
            />
          );
        })}
        <polygon points={polygon} fill="rgba(37, 99, 235, 0.25)" stroke="var(--primary)" strokeWidth="2" />
        {descriptors.map((d, i) => {
          const labelPt = point(i, 1.22);
          return (
            <text
              key={`lbl-${d.label}`}
              x={labelPt.x}
              y={labelPt.y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="radar-label"
            >
              {d.label.split(" ")[0]}
            </text>
          );
        })}
      </svg>
      <ul className="radar-legend">
        {descriptors.map((d) => (
          <li key={d.label}>
            <span>{d.label}</span>
            <strong>{Math.round(d.value * 100)}%</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

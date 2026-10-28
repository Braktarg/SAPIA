type BarItem = { label: string; value: number; color?: string };

type Props = {
  title: string;
  items: BarItem[];
  max?: number;
};

export function SimpleBarChart({ title, items, max }: Props) {
  const peak = max ?? Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="chart-card">
      <h3 className="chart-title">{title}</h3>
      <ul className="chart-bars">
        {items.map((item) => (
          <li key={item.label} className="chart-row">
            <span className="chart-label">{item.label}</span>
            <div className="chart-track">
              <div
                className="chart-fill"
                style={{
                  width: `${(item.value / peak) * 100}%`,
                  background: item.color ?? "var(--primary)",
                }}
              />
            </div>
            <span className="chart-value">{item.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

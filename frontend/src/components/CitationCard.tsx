type Props = {
  unitName: string;
  snippet: string;
  score: number;
};

export function CitationCard({ unitName, snippet, score }: Props) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
  const level = pct >= 75 ? "high" : pct >= 50 ? "mid" : "low";

  return (
    <li className={`citation-card citation-${level}`}>
      <div className="citation-card-head">
        <strong>{unitName}</strong>
        <span className="citation-score">Relevancia {pct}%</span>
      </div>
      <div className="citation-track" aria-hidden>
        <div className="citation-fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="citation-snippet">{snippet}</p>
    </li>
  );
}

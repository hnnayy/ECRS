export default function ScoreBar({ value }: { value: number | null }) {
  if (value === null) return <span className="muted">n/a</span>;
  const tone = value >= 0.5 ? "critical" : value >= 0.3 ? "warning" : "good";
  return (
    <div className="scorebar" title={value.toFixed(2)}>
      <div className={`fill bg-${tone}`} style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  );
}

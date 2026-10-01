import type { Series } from "../types";

const W = 420, H = 150, PX = 36, PT = 12, PB = 24;

function scale(values: number[], pad = 0.08) {
  const lo = Math.min(...values), hi = Math.max(...values);
  const span = hi - lo || Math.abs(hi) || 1;
  return { lo: lo - span * pad, hi: hi + span * pad };
}

function Frame({ ticks, labels, y, children }: {
  ticks: number[]; labels: string[]; y: (v: number) => number; children: React.ReactNode;
}) {
  const x = (i: number) => PX + (i * (W - PX - 8)) / Math.max(labels.length - 1, 1);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={PX} x2={W - 8} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
          <text x={PX - 4} y={y(t) + 3} fontSize="9" textAnchor="end" fill="var(--muted)">{Math.round(t * 10) / 10}</text>
        </g>
      ))}
      {labels.map((l, i) => (i % 2 === 0 || labels.length < 7) && (
        <text key={l} x={x(i)} y={H - 8} fontSize="9" textAnchor="middle" fill="var(--muted)">{l.slice(2)}</text>
      ))}
      {children}
    </svg>
  );
}

const xAt = (i: number, n: number) => PX + (i * (W - PX - 8)) / Math.max(n - 1, 1);
const path = (pts: [number, number][]) => pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

export function HeadcountChart({ data }: { data: Series["A"] }) {
  const { lo, hi } = scale(data.map((d) => d.headcount));
  const y = (v: number) => PT + ((hi - v) / (hi - lo)) * (H - PT - PB);
  const pts = data.map((d, i) => [xAt(i, data.length), y(d.headcount)] as [number, number]);
  const maxR = Math.max(...data.map((d) => d.resign), 1);
  return (
    <Frame ticks={[lo + (hi - lo) * 0.1, (lo + hi) / 2, hi - (hi - lo) * 0.1]} labels={data.map((d) => d.periode)} y={y}>
      {data.map((d, i) => d.resign > 0 && (
        <rect key={d.periode} x={xAt(i, data.length) - 5} width="10" rx="2" fill="var(--warning)" opacity=".55"
          y={H - PB - (d.resign / maxR) * 22} height={(d.resign / maxR) * 22}><title>{`${d.resign} resign`}</title></rect>
      ))}
      <path d={path(pts)} fill="none" stroke="var(--accent)" strokeWidth="2" />
      {pts.map(([px, py], i) => <circle key={i} cx={px} cy={py} r="3" fill="var(--accent)"><title>{`${data[i].periode}: ${data[i].headcount}`}</title></circle>)}
    </Frame>
  );
}

export function PeerWageChart({ data }: { data: Series["B"] }) {
  const vals = data.flatMap((d) => [d.own, d.q1, d.q3].filter((v): v is number => v !== null));
  const { lo, hi } = scale(vals);
  const y = (v: number) => PT + ((hi - v) / (hi - lo)) * (H - PT - PB);
  const n = data.length;
  const band = data.filter((d) => d.q1 !== null && d.q3 !== null);
  const upper = band.map((d) => [xAt(data.indexOf(d), n), y(d.q3!)] as [number, number]);
  const lower = band.map((d) => [xAt(data.indexOf(d), n), y(d.q1!)] as [number, number]).reverse();
  const med = data.filter((d) => d.median !== null).map((d) => [xAt(data.indexOf(d), n), y(d.median!)] as [number, number]);
  const own = data.map((d, i) => [xAt(i, n), y(d.own)] as [number, number]);
  return (
    <Frame ticks={[lo + (hi - lo) * 0.1, (lo + hi) / 2, hi - (hi - lo) * 0.1]} labels={data.map((d) => d.periode)} y={y}>
      {band.length > 0 && <path d={`${path(upper)} L${path(lower).slice(1)} Z`} fill="var(--muted)" opacity=".2" />}
      {med.length > 0 && <path d={path(med)} fill="none" stroke="var(--muted)" strokeDasharray="4 3" />}
      <path d={path(own)} fill="none" stroke="var(--accent)" strokeWidth="2" />
    </Frame>
  );
}

export function RemittanceChart({ data }: { data: Series["C"] }) {
  const { hi } = scale(data.flatMap((d) => [d.expected, d.actual, 0]), 0.05);
  const y = (v: number) => PT + ((hi - v) / hi) * (H - PT - PB);
  const gw = (W - PX - 8) / data.length, bw = Math.max(gw / 2 - 2, 2);
  return (
    <Frame ticks={[hi * 0.25, hi * 0.5, hi * 0.75]} labels={data.map((d) => d.periode)} y={y}>
      {data.map((d, i) => {
        const gx = PX + i * gw + 1;
        return (
          <g key={d.periode}>
            <rect x={gx} y={y(d.expected)} width={bw} height={H - PB - y(d.expected)} fill="var(--accent)"><title>{`seharusnya ${d.expected}`}</title></rect>
            <rect x={gx + bw + 1} y={y(d.actual)} width={bw} height={H - PB - y(d.actual)}
              fill={d.actual < d.expected * 0.95 ? "var(--critical)" : "var(--warning)"}><title>{`aktual ${d.actual}`}</title></rect>
          </g>
        );
      })}
    </Frame>
  );
}

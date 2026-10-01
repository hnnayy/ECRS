/** Logo ECRS: radar dengan sapuan berputar dan titik risiko yang berdenyut. Animasi dimatikan jika pengguna memilih "kurangi gerakan". */
export default function Logo({ size = 38 }: { size?: number }) {
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 48 48" role="img" aria-label="ECRS Risk Radar">
      <defs>
        <linearGradient id="logo-bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3b8cf0" /><stop offset="1" stopColor="#4b3fd6" /></linearGradient>
        <linearGradient id="logo-sweep" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stopColor="#fff" stopOpacity="0" /><stop offset="1" stopColor="#fff" stopOpacity=".75" /></linearGradient>
      </defs>
      <rect width="48" height="48" rx="12" fill="url(#logo-bg)" />
      <g fill="none" stroke="#fff" strokeOpacity=".38" strokeWidth="1.3">
        <circle cx="24" cy="24" r="16" /><circle cx="24" cy="24" r="10" /><circle cx="24" cy="24" r="4" />
        <path d="M24 6v36M6 24h36" strokeOpacity=".18" />
      </g>
      <g className="logo-sweep">
        <path d="M24 24 L24 8 A16 16 0 0 1 37.86 16 Z" fill="url(#logo-sweep)" />
        <path d="M24 24 L37.86 16" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
      </g>
      <circle className="logo-pulse" cx="33" cy="30" r="3.4" fill="#ff5a4d" opacity=".55" />
      <circle cx="33" cy="30" r="3.4" fill="#ff5a4d" stroke="#fff" strokeWidth="1.4" />
      <circle cx="17" cy="17.5" r="2" fill="#ffc94d" />
    </svg>
  );
}

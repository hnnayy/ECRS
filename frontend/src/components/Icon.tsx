const PATHS: Record<string, string> = {
  radar: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 5a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z",
  input: "M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5ZM12 11v6M9 14h6",
  log: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4v5l3 2",
  building: "M5 21V4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v17M9 8h2M13 8h2M9 12h2M13 12h2M10 21v-4h4v4",
  map: "M3 7l6-2 6 2 6-2v14l-6 2-6-2-6 2V7Zm6-2v14m6-12v14",
};
export default function Icon({ name }: { name: keyof typeof PATHS | string }) {
  return (
    <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={PATHS[name]} />
    </svg>
  );
}

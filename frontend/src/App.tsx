import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useSearchParams } from "react-router-dom";
import Icon from "./components/Icon";
import Logo from "./components/Logo";
import DetailDrawer from "./components/DetailDrawer";
import Dashboard from "./pages/Dashboard";
import InputData from "./pages/InputData";
import Decisions from "./pages/Decisions";
import MasterEmployers from "./pages/MasterEmployers";
import MasterReference from "./pages/MasterReference";

const NAV: { group: string; items: { path: string; label: string; icon: string }[] }[] = [
  { group: "Deteksi & Investigasi", items: [
    { path: "/dashboard", label: "Dashboard & Radar Risiko", icon: "radar" },
    { path: "/input-data", label: "Input Data Payroll & Setoran", icon: "input" },
    { path: "/riwayat-keputusan", label: "Riwayat Keputusan", icon: "log" },
  ] },
  { group: "Data Referensi", items: [
    { path: "/master/badan-usaha", label: "Master Data Badan Usaha", icon: "building" },
    { path: "/master/referensi", label: "Master Referensi UMR & Sektor", icon: "map" },
  ] },
];

function useSidebarState(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem("ecrs.sidebar") === "collapsed"; } catch { return false; }
  });
  useEffect(() => {
    try { localStorage.setItem("ecrs.sidebar", collapsed ? "collapsed" : "open"); } catch { /* penyimpanan diblokir: abaikan */ }
  }, [collapsed]);
  return [collapsed, () => setCollapsed((c) => !c)];
}

export default function App() {
  const [collapsed, toggleSidebar] = useSidebarState();
  // Employer yang dibuka disimpan di URL (?employer=EMP-0492) agar bisa di-bookmark/dibagikan & tombol Back menutupnya
  const [params, setParams] = useSearchParams();
  const selected = params.get("employer");
  const setSelected = (id: string | null) => {
    const next = new URLSearchParams(params);
    if (id) next.set("employer", id); else next.delete("employer");
    setParams(next);
  };

  return (
    <>
      <header className="appbar">
        <button className="menu-toggle" onClick={toggleSidebar} aria-label={collapsed ? "Buka menu" : "Tutup menu"}
          aria-expanded={!collapsed} aria-controls="sidebar" title={collapsed ? "Buka menu" : "Tutup menu"}>
          <svg className="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden><path d="M4 6h16M4 12h16M4 18h16" /></svg>
        </button>
        <Logo />
        <div><h1>ECRS Risk Radar</h1><span>Employer Contribution Risk Score</span></div>
        <span className="proto-badge">Data Simulasi</span>
      </header>
      <div className="shell">
        <nav id="sidebar" className={`sidebar ${collapsed ? "collapsed" : ""}`} aria-label="Menu utama">
          {NAV.map((g) => (
            <div key={g.group}>
              <div className="side-label">{g.group}</div>
              {g.items.map((i) => (
                <NavLink key={i.path} to={i.path} title={i.label} className={({ isActive }) => `side-item ${isActive ? "active" : ""}`}>
                  <Icon name={i.icon} /><span className="side-text">{i.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <main className={selected ? "with-drawer" : ""}>
          <div className="page">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard onSelect={setSelected} />} />
            <Route path="/input-data" element={<InputData onSelect={setSelected} />} />
            <Route path="/riwayat-keputusan" element={<Decisions onSelect={setSelected} />} />
            <Route path="/master/badan-usaha" element={<MasterEmployers onSelect={setSelected} />} />
            <Route path="/master/referensi" element={<MasterReference />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
          </div>
        </main>
      </div>
      {selected && <DetailDrawer id={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

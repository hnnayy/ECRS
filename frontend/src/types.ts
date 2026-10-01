export type Band = "Tinggi" | "Sedang" | "Rendah" | "Belum bisa dinilai";
export type Scores = { A: number | null; B: number | null; C: number | null };

export interface CompanyRow {
  id: string; rank: number | null; sektor: string; wilayah: string; skala: string;
  composite_score: number | null; band: Band; coverage: number; modules_flagged: string[];
  scores: Scores; recommendation: string; summary: string; learned_score: number | null;
}
export interface CompanyList { total: number; limit: number; offset: number; items: CompanyRow[]; model_active: boolean }

export interface Driver {
  module: "A" | "B" | "C"; label: string; status: string; flagged: boolean;
  score: number | null; contribution_pct: number | null; text: string;
}
export interface Learned { score: number; version: number; contributions: { feature: string; label: string; value: number; contribution: number }[] }
export interface PatternSignal { score: number; flagged: boolean; reasons: { feature: string; label: string; text: string }[] }
export interface CompanyDetail extends Omit<CompanyRow, "summary" | "learned_score"> {
  learned: Learned | null;
  extra_signals?: { isolation_forest?: PatternSignal; remittance_early_warning?: { flagged: boolean; last_gap: number; text: string } };
  status: Record<string, string>;
  explanation: { summary: string; drivers: Driver[] };
}
export interface Summary { total: number; by_band: Record<string, number>; by_module_flagged: Record<string, number> }
export interface Filters { sektor: string[]; wilayah: string[]; skala: string[]; band: string[] }

export interface Series {
  A: { periode: string; headcount: number; resign: number }[];
  B: { periode: string; own: number; q1: number | null; median: number | null; q3: number | null }[];
  C: { periode: string; expected: number; actual: number }[];
}

export interface Decision { id: number; company_id: string; decision: "investigasi" | "tutup" | "terbukti" | "tidak_terbukti"; note: string; officer: string; created_at: string; source: string }
export interface Employer { employer_id: string; nama: string; sektor: string; wilayah: string; skala: string; status: "Aktif" | "Non-aktif"; tanggal_registrasi: string; scored: boolean }
export type EmployerInput = Omit<Employer, "employer_id" | "scored">;
export interface Reference {
  wilayah: { nama: string; employer: number; umr_rp: number | null }[];
  sektor: { nama: string; employer: number }[];
  skala: string[];
}


export interface PeriodRow { periode: string; jumlah_peserta_aktif: number; jumlah_keluar: number; rata2_DPI: number | null; expected_contribution: number | null; actual_remittance: number | null }
export type PeriodInput = { employer_id: string; periode: string; jumlah_peserta_aktif: number; jumlah_keluar: number; rata2_DPI: number; expected_contribution: number; actual_remittance: number };
export interface SystemStatus {
  now: string;
  scoring: { pending: boolean; running: boolean; last_run: string | null; last_error: string | null; debounce_s: number };
  model: { running: boolean; last_check: string | null; last_action: string | null; waiting_for: string | null; last_error: string | null;
           check_every_s: number; retrain_every_labels: number; min_labels: number; min_per_class: number; includes_simulated: boolean };
}

export interface CaseSummary { text: string; source: "templat" | "llm"; model: string | null; fallback_reason: string | null; llm_configured: boolean }

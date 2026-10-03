import type { CompanyDetail, CompanyList, Decision, Employer, EmployerInput, Filters, PeriodInput, PeriodRow, SystemStatus,  Reference, Series, CaseSummary, Summary } from "./types";

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method, headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const d = (await res.json()).detail;
      detail = typeof d === "string" ? d : Array.isArray(d) ? d.map((x: { loc: string[]; msg: string }) => `${x.loc[x.loc.length - 1]}: ${x.msg}`).join("; ") : detail;
    } catch { /* body kosong */ }
    throw new Error(detail);
  }
  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>);
}
const get = <T,>(path: string) => req<T>("GET", path);

const post = <T,>(path: string, body: unknown) => req<T>("POST", path, body);

export const api = {
  decisions: (companyId?: string) => get<Decision[]>(`/api/decisions?limit=1000${companyId ? `&company_id=${encodeURIComponent(companyId)}` : ""}`),
  addDecision: (d: { company_id: string; decision: string; note: string }) => post<Decision>("/api/decisions", d),
  employers: (q: string, offset: number, limit: number) => get<{ total: number; items: Employer[] }>(`/api/employers?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`),
  createEmployer: (e: EmployerInput) => post<Employer>("/api/employers", e),
  updateEmployer: (id: string, e: EmployerInput) => req<Employer>("PUT", `/api/employers/${id}`, e),
  deleteEmployer: (id: string) => req<void>("DELETE", `/api/employers/${id}`),
  createRef: (kind: "wilayah" | "sektor", b: { nama: string; umr_rp?: number | null }) => post<unknown>(`/api/${kind}`, b),
  updateRef: (kind: "wilayah" | "sektor", old: string, b: { nama: string; umr_rp?: number | null }) =>
    req<unknown>("PUT", `/api/${kind}/${encodeURIComponent(old)}`, b),
  deleteRef: (kind: "wilayah" | "sektor", nama: string) => req<void>("DELETE", `/api/${kind}/${encodeURIComponent(nama)}`),
  timeseries: (id: string) => get<PeriodRow[]>(`/api/timeseries/${encodeURIComponent(id)}?limit=60`),
  savePeriod: (d: PeriodInput) => post<PeriodInput>("/api/timeseries", d),
  status: () => get<SystemStatus>("/api/system/status"),
  reference: () => get<Reference>("/api/reference"),
  summary: () => get<Summary>("/api/summary"),
  filters: () => get<Filters>("/api/filters"),
  companies: (params: Record<string, string | number>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== "" && qs.set(k, String(v)));
    return get<CompanyList>(`/api/companies?${qs}`);
  },
  series: (id: string) => get<Series>(`/api/companies/${encodeURIComponent(id)}/series`),
  caseSummary: (id: string, llm: boolean) => get<CaseSummary>(`/api/companies/${encodeURIComponent(id)}/case-summary?llm=${llm}`),
  company: (id: string) => get<CompanyDetail>(`/api/companies/${encodeURIComponent(id)}`),
};

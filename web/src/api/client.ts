import type { CaseRowV4, EscalationSummary, ScenarioInfo, ScenariosResponse, TraceResponse } from "../types";

const BASE = "/api";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text.slice(0, 300)}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => req<any>("/health"),
  dashboard: () => req<any>("/dashboard"),
  cases: (qs = "") => req<any>(`/cases${qs}`),
  caseDetail: (id: string) => req<any>(`/cases/${id}`),
  caseAudit: (id: string) => req<any>(`/cases/${id}/audit`),
  caseIntegrity: (id: string) => req<any>(`/cases/${id}/integrity`),
  caseBundle: (id: string) => req<any>(`/cases/${id}/bundle`),
  scenarios: () => req<any>("/scenarios"),
  startRun: (scenario_id: string, configuration: string) =>
    req<any>("/runs", { method: "POST", body: JSON.stringify({ scenario_id, configuration }) }),
  stepRun: (runId: string) => req<any>(`/runs/${runId}/step`, { method: "POST" }),
  playRun: (runId: string) => req<any>(`/runs/${runId}/play`, { method: "POST" }),
  getRun: (runId: string) => req<any>(`/runs/${runId}`),
  auditBundle: (runId: string) => req<any>(`/runs/${runId}/audit`),
  trace: (runId: string) => req<any>(`/runs/${runId}/trace`),
  listTraces: () => req<any[]>("/runs"),
  channels: (runId: string) => req<any>(`/channels?run_id=${runId}`),
  sources: () => req<any>("/kb/sources"),
  search: (q: string, opts: { jurisdiction?: string; scope?: string; claim?: string } = {}) => {
    const p = new URLSearchParams({ q });
    if (opts.jurisdiction) p.set("jurisdiction", opts.jurisdiction);
    if (opts.scope) p.set("scope", opts.scope);
    if (opts.claim) p.set("claim", opts.claim);
    return req<any>(`/kb/search?${p.toString()}`);
  },
  chunk: (id: string) => req<any>(`/kb/chunks/${id}`),
  gaps: () => req<any>("/gaps"),
  mappings: (name: string) => req<any>(`/mappings/${name}`),
  stateMachine: () => req<any>("/meta/state-machine"),
  evaluate: () => req<any>("/evaluation/run", { method: "POST", body: JSON.stringify({}) }),
  latestEvaluation: () => req<any>("/evaluation/latest"),

  /* v4 typed helpers (same endpoints; the untyped ones above keep working) */
  scenariosTyped: () => req<ScenariosResponse>("/scenarios"),
  casesTyped: (qs = "") => req<{ cases: CaseRowV4[]; count: number }>(`/cases${qs}`),
  traceTyped: (runId: string) => req<TraceResponse>(`/runs/${runId}/trace`),
  injectEvent: (runId: string, body: Record<string, unknown>) =>
    req<any>(`/runs/${runId}/events`, { method: "POST", body: JSON.stringify(body) }),
};

/** The current owner of a case: the newest escalation that is still open or in review. */
export function currentOwner(escalations: EscalationSummary[] | undefined | null): EscalationSummary | null {
  const live = (escalations ?? []).filter((e) => e.status === "OPEN" || e.status === "IN_REVIEW");
  return live.length ? live[live.length - 1] : null;
}

let scenarioCache: Promise<ScenariosResponse> | null = null;
/** Cached GET /scenarios (scenarios are static files; one fetch per page load). */
export function loadScenarios(): Promise<ScenariosResponse> {
  if (!scenarioCache) scenarioCache = api.scenariosTyped().catch((e) => { scenarioCache = null; throw e; });
  return scenarioCache;
}
export type { ScenarioInfo };

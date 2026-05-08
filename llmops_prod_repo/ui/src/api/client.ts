import type { AgentRequest, AgentResponse, HealthResponse, MetricsSnapshot, ConfigResponse } from "@/types";

const BASE = "/api";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }

  return res.json() as Promise<T>;
}

export const api = {
  runAgent: (payload: AgentRequest): Promise<AgentResponse> =>
    request<AgentResponse>("/run_agent", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  health: (): Promise<HealthResponse> =>
    request<HealthResponse>("/health"),

  metrics: (): Promise<MetricsSnapshot> =>
    request<MetricsSnapshot>("/metrics"),

  config: (): Promise<ConfigResponse> =>
    request<ConfigResponse>("/config"),
};

// ── Domain types ──────────────────────────────────────────────────────────────

export type Role = "PRODUCT_OWNER" | "DEVELOPER";

export interface User {
  email: string;
  role: Role;
  sessionId: string;
}

export interface AgentRequest {
  input: string;
  user: string;
  role: Role;
  session_id: string;
}

export interface AgentResponse {
  output: string;
  correlation_id: string;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
}

export interface MetricsSnapshot {
  [key: string]: number;
}

export interface ConfigResponse {
  jira_url: string;
}

// ── Chat message ──────────────────────────────────────────────────────────────

export type MessageRole = "user" | "assistant" | "error";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  correlationId?: string;
  latencyMs?: number;
}

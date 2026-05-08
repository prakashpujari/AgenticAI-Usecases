import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  CreateTicketRequest,
  ReviewTicketRequest,
  TicketResponse,
  RecentTicketsResponse,
} from '../types';

// Empty string = same origin → Vite dev-server proxy forwards /ai and /health
// to http://localhost:8000.  Set VITE_API_URL to override in production.
const BASE_URL = import.meta.env.VITE_API_URL ?? '';

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  // 120 s: the full pipeline (embedding + Pinecone + 3-5 LLM calls + Jira)
  // can take 20-40 s in practice; 120 s leaves headroom under load.
  timeout: 120_000,
});

// ── Response interceptor: normalise errors ────────────────────────────────
api.interceptors.response.use(
  (res) => res,
  // Unwrap FastAPI's { detail: "..." } error shape into a plain Error so
  // React Query's mutation.error.message always contains a readable string.
  (err: AxiosError<{ detail: string }>) => {
    const message =
      err.response?.data?.detail ?? err.message ?? 'Unknown error';
    return Promise.reject(new Error(message));
  },
);

// ── API helpers ────────────────────────────────────────────────────────────

export async function createTicket(
  payload: CreateTicketRequest,
): Promise<TicketResponse> {
  const { data } = await api.post<TicketResponse>('/ai/create-ticket', payload);
  return data;
}

export async function reviewTicket(
  payload: ReviewTicketRequest,
): Promise<TicketResponse> {
  const { data } = await api.post<TicketResponse>('/ai/review-ticket', payload);
  return data;
}

export async function healthCheck(): Promise<{ status: string; services: Record<string, string> }> {
  const { data } = await api.get('/health');
  return data;
}

export async function getRecentTickets(
  projects: string[],
  limit = 5,
): Promise<RecentTicketsResponse> {
  const { data } = await api.get<RecentTicketsResponse>('/ai/recent-tickets', {
    params: { projects: projects.join(','), limit },
  });
  return data;
}

export default api;

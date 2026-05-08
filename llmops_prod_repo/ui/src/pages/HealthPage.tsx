import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, RefreshCw, Server, Database, Brain, Cpu } from "lucide-react";
import clsx from "clsx";
import { api } from "@/api/client";

interface ServiceCardProps {
  name: string;
  description: string;
  status: "ok" | "degraded" | "unknown";
  icon: React.ElementType;
  detail?: string;
}

function ServiceCard({ name, description, status, icon: Icon, detail }: ServiceCardProps) {
  const colors = {
    ok:       { bg: "bg-emerald-900/20", border: "border-emerald-800/40", dot: "bg-emerald-400", text: "text-emerald-400", label: "Healthy" },
    degraded: { bg: "bg-red-900/20",     border: "border-red-800/40",     dot: "bg-red-400",     text: "text-red-400",     label: "Degraded" },
    unknown:  { bg: "bg-gray-800/20",    border: "border-gray-700",       dot: "bg-gray-500",    text: "text-gray-400",    label: "Unknown" },
  };
  const c = colors[status];

  return (
    <div className={clsx("rounded-xl border p-5 flex items-start gap-4 transition-all", c.bg, c.border)}>
      <div className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center flex-shrink-0">
        <Icon size={20} className="text-gray-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-white">{name}</p>
          <div className={clsx("flex items-center gap-1.5 text-xs font-medium", c.text)}>
            <div className={clsx("w-2 h-2 rounded-full", c.dot, status === "ok" && "animate-pulse-soft")} />
            {c.label}
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-0.5">{description}</p>
        {detail && <p className="text-xs text-gray-400 mt-2 font-mono truncate">{detail}</p>}
      </div>
    </div>
  );
}

export default function HealthPage() {
  const { data, isFetching, refetch, dataUpdatedAt, isError } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
  });

  const apiOk = !isError && data?.status === "ok";

  const services: ServiceCardProps[] = [
    {
      name: "FastAPI Backend",
      description: "Main LLMOps Agent REST API",
      icon: Server,
      status: isError ? "degraded" : data ? "ok" : "unknown",
      detail: "http://localhost:8000/health",
    },
    {
      name: "Jira Integration",
      description: "Atlassian Jira ticket management — project MC",
      icon: Database,
      status: apiOk ? "ok" : "unknown",
      detail: "https://mailtopprakash01.atlassian.net/",
    },
    {
      name: "OpenAI (Planner)",
      description: "GPT-4o-mini for intent classification",
      icon: Brain,
      status: apiOk ? "ok" : "unknown",
      detail: "Model: gpt-4o-mini",
    },
    {
      name: "Pinecone (Memory)",
      description: "Vector store for RAG context retrieval",
      icon: Cpu,
      status: apiOk ? "ok" : "unknown",
      detail: "Index: mortgageindex",
    },
    {
      name: "Redis (Session Memory)",
      description: "Conversation history store",
      icon: Database,
      status: "unknown",
      detail: "localhost:6379 — not running locally",
    },
  ];

  return (
    <div className="p-6 space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-white font-semibold">System Health</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {dataUpdatedAt
              ? `Last checked ${new Date(dataUpdatedAt).toLocaleTimeString()}`
              : "Checking…"}
          </p>
        </div>
        <button onClick={() => refetch()} disabled={isFetching} className="btn-ghost text-gray-400">
          <RefreshCw size={14} className={clsx(isFetching && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Overall status banner */}
      <div className={clsx(
        "flex items-center gap-4 rounded-xl border p-5",
        isError
          ? "bg-red-900/20 border-red-800/40"
          : apiOk
          ? "bg-emerald-900/20 border-emerald-800/40"
          : "bg-gray-800/30 border-gray-700"
      )}>
        {isError
          ? <XCircle size={28} className="text-red-400 flex-shrink-0" />
          : apiOk
          ? <CheckCircle2 size={28} className="text-emerald-400 flex-shrink-0" />
          : <RefreshCw size={28} className="text-gray-400 animate-spin flex-shrink-0" />
        }
        <div>
          <p className="font-semibold text-white">
            {isError ? "API Unreachable" : apiOk ? "All Systems Operational" : "Connecting…"}
          </p>
          <p className="text-xs text-gray-400 mt-0.5">
            {isError
              ? "Cannot reach the backend. Ensure uvicorn is running on port 8000."
              : apiOk
              ? "Backend API is healthy and responding."
              : "Polling the health endpoint…"}
          </p>
        </div>
      </div>

      {/* Service grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {services.map((s) => (
          <ServiceCard key={s.name} {...s} />
        ))}
      </div>

      {/* How to start */}
      {isError && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">Start the backend</h3>
          <pre className="bg-gray-950 rounded-lg p-4 text-xs text-emerald-400 font-mono overflow-x-auto">
{`cd llmops_prod_repo
.venv\\Scripts\\Activate.ps1
uvicorn app:app --reload --port 8000`}
          </pre>
        </div>
      )}
    </div>
  );
}

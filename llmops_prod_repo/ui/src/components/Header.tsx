import { useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, AlertTriangle, Wifi } from "lucide-react";
import { api } from "@/api/client";

const TITLES: Record<string, string> = {
  "/agent":   "Agent Chat",
  "/metrics": "Metrics Dashboard",
  "/health":  "System Health",
};

export default function Header() {
  const { pathname } = useLocation();
  const title = TITLES[pathname] ?? "Dashboard";

  const { data } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
  });

  const isOk = data?.status === "ok";

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-gray-800 bg-gray-950/50 backdrop-blur sticky top-0 z-10">
      <div>
        <h1 className="text-lg font-semibold text-white">{title}</h1>
        <p className="text-xs text-gray-500 mt-0.5">LLMOps Production Agent</p>
      </div>

      <div className="flex items-center gap-4">
        {/* API status pill */}
        <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border ${
          data == null
            ? "bg-gray-800 border-gray-700 text-gray-400"
            : isOk
            ? "bg-emerald-900/30 border-emerald-700/40 text-emerald-400"
            : "bg-red-900/30 border-red-700/40 text-red-400"
        }`}>
          {data == null ? (
            <Wifi size={12} className="animate-pulse" />
          ) : isOk ? (
            <CheckCircle2 size={12} />
          ) : (
            <AlertTriangle size={12} />
          )}
          {data == null ? "Connecting…" : isOk ? "API Online" : "API Degraded"}
        </div>
      </div>
    </header>
  );
}

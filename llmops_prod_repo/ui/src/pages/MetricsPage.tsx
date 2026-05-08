import { useQuery } from "@tanstack/react-query";
import { RefreshCw, TrendingUp, Zap, ShieldAlert, CheckCircle2 } from "lucide-react";
import clsx from "clsx";
import { api } from "@/api/client";

interface MetricCardProps {
  label: string;
  value: number | undefined;
  unit?: string;
  icon: React.ElementType;
  color: string;
  description?: string;
}

function MetricCard({ label, value, unit = "", icon: Icon, color, description }: MetricCardProps) {
  return (
    <div className="card flex flex-col gap-4 hover:border-gray-700 transition-colors">
      <div className="flex items-start justify-between">
        <div className={clsx("w-10 h-10 rounded-lg flex items-center justify-center", color)}>
          <Icon size={20} className="text-white" />
        </div>
        <span className="text-xs text-gray-500 font-mono">{label}</span>
      </div>
      <div>
        <p className="text-3xl font-bold text-white tabular-nums">
          {value == null ? "—" : value.toLocaleString()}
          {unit && <span className="text-lg text-gray-400 ml-1 font-normal">{unit}</span>}
        </p>
        {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
      </div>
    </div>
  );
}

interface MetricRowProps {
  label: string;
  value: number;
  max: number;
}

function MetricRow({ label, value, max }: MetricRowProps) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const color =
    pct > 80 ? "bg-red-500" :
    pct > 50 ? "bg-amber-500" :
               "bg-emerald-500";

  return (
    <div className="flex items-center gap-4 py-3 border-b border-gray-800 last:border-0">
      <span className="text-sm text-gray-400 w-56 flex-shrink-0 font-mono">{label}</span>
      <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
        <div className={clsx("h-full rounded-full transition-all duration-500", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-medium text-gray-200 w-20 text-right tabular-nums">
        {value.toLocaleString()}
      </span>
    </div>
  );
}

const CATEGORY_ICONS: Record<string, { icon: React.ElementType; color: string }> = {
  "api.run_agent.requests": { icon: Zap, color: "bg-brand-600" },
  "api.run_agent.success":  { icon: CheckCircle2, color: "bg-emerald-600" },
  "api.run_agent.errors":   { icon: ShieldAlert, color: "bg-red-600" },
  "tool.create.success":    { icon: TrendingUp, color: "bg-violet-600" },
};

export default function MetricsPage() {
  const { data, isFetching, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["metrics"],
    queryFn: api.metrics,
    refetchInterval: 15_000,
  });

  const entries = data ? Object.entries(data) : [];
  const latencyKeys = entries.filter(([k]) => k.includes("latency"));
  const counterKeys = entries.filter(([k]) => !k.includes("latency"));
  const maxCounter = Math.max(...counterKeys.map(([, v]) => v), 1);

  const highlighted = [
    "api.run_agent.requests",
    "api.run_agent.success",
    "api.run_agent.errors",
    "tool.create.success",
  ];

  return (
    <div className="p-6 space-y-8 animate-fade-in">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-white font-semibold">Live Metrics</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {dataUpdatedAt ? `Last updated ${new Date(dataUpdatedAt).toLocaleTimeString()}` : "Loading…"}
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="btn-ghost text-gray-400"
        >
          <RefreshCw size={14} className={clsx(isFetching && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {highlighted.map((key) => {
          const meta = CATEGORY_ICONS[key];
          return (
            <MetricCard
              key={key}
              label={key}
              value={data?.[key]}
              icon={meta?.icon ?? TrendingUp}
              color={meta?.color ?? "bg-gray-600"}
              description={key.replace(/\./g, " › ")}
            />
          );
        })}
      </div>

      {/* Latency */}
      {latencyKeys.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
            <Zap size={14} className="text-amber-400" /> Latency (ms)
          </h3>
          <div className="space-y-0">
            {latencyKeys.map(([key, val]) => (
              <MetricRow key={key} label={key} value={val} max={Math.max(...latencyKeys.map(([, v]) => v), 1)} />
            ))}
          </div>
        </div>
      )}

      {/* All counters */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
          <TrendingUp size={14} className="text-brand-400" /> All Counters
        </h3>
        {counterKeys.length === 0 ? (
          <p className="text-sm text-gray-500">No data yet. Send some agent requests to see metrics.</p>
        ) : (
          <div className="space-y-0">
            {counterKeys.map(([key, val]) => (
              <MetricRow key={key} label={key} value={val} max={maxCounter} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

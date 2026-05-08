import { NavLink, useNavigate } from "react-router-dom";
import {
  MessageSquare,
  BarChart3,
  Activity,
  LogOut,
  Bot,
  ChevronRight,
} from "lucide-react";
import clsx from "clsx";
import { useAuth } from "@/context/AuthContext";

const NAV = [
  { to: "/agent",   label: "Agent Chat",  icon: MessageSquare },
  { to: "/metrics", label: "Metrics",     icon: BarChart3 },
  { to: "/health",  label: "System Health", icon: Activity },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <aside className="flex flex-col w-64 min-h-screen bg-gray-900 border-r border-gray-800">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-gray-800">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-brand-600">
          <Bot size={20} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-white leading-none">LLMOps Agent</p>
          <p className="text-xs text-gray-500 mt-0.5">Product Portal</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                "group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-brand-600/20 text-brand-400 border border-brand-600/30"
                  : "text-gray-400 hover:text-gray-100 hover:bg-white/5"
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={16} className={isActive ? "text-brand-400" : "text-gray-500 group-hover:text-gray-300"} />
                <span className="flex-1">{label}</span>
                {isActive && <ChevronRight size={14} className="text-brand-400" />}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="px-3 py-4 border-t border-gray-800">
        <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-gray-800/50 mb-2">
          <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-xs font-bold text-white">
            {user?.email[0]?.toUpperCase() ?? "U"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-gray-200 truncate">{user?.email}</p>
            <p className="text-xs text-brand-400">{user?.role}</p>
          </div>
        </div>
        <button onClick={handleLogout} className="btn-ghost w-full justify-start text-gray-500 hover:text-red-400 hover:bg-red-900/10">
          <LogOut size={15} />
          Sign out
        </button>
      </div>
    </aside>
  );
}

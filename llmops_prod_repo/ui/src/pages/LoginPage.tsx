import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bot, LogIn } from "lucide-react";
import clsx from "clsx";
import { v4 as uuidv4 } from "uuid";
import { useAuth } from "@/context/AuthContext";
import type { Role } from "@/types";

const ROLES: { value: Role; label: string; description: string }[] = [
  { value: "PRODUCT_OWNER", label: "Product Owner",  description: "Can create & view Jira tickets" },
  { value: "DEVELOPER",     label: "Developer",       description: "Read-only access to tickets" },
];

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("PRODUCT_OWNER");
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setError("Enter a valid email address.");
      return;
    }
    login({ email: trimmed, role, sessionId: uuidv4() });
    navigate("/agent");
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      {/* Glow orb */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-brand-600/10 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md animate-slide-up">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-brand-600 flex items-center justify-center shadow-lg shadow-brand-600/30 mb-4">
            <Bot size={34} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">LLMOps Agent</h1>
          <p className="text-gray-400 text-sm mt-1">Product Owner Portal</p>
        </div>

        {/* Card */}
        <div className="glass rounded-2xl p-8 space-y-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Email */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-400 uppercase tracking-wide">Email address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setError(""); }}
                placeholder="you@company.com"
                className="input"
                autoFocus
              />
            </div>

            {/* Role */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-400 uppercase tracking-wide">Role</label>
              <div className="grid grid-cols-2 gap-3">
                {ROLES.map(({ value, label, description }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setRole(value)}
                    className={clsx(
                      "flex flex-col items-start px-4 py-3 rounded-xl border text-left transition-all",
                      role === value
                        ? "bg-brand-600/20 border-brand-500 text-brand-300"
                        : "bg-gray-800/50 border-gray-700 text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                    )}
                  >
                    <span className="text-sm font-semibold">{label}</span>
                    <span className="text-xs mt-0.5 opacity-75">{description}</span>
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <p className="text-xs text-red-400 bg-red-900/20 border border-red-800/40 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button type="submit" className="btn-primary w-full justify-center">
              <LogIn size={16} />
              Enter Portal
            </button>
          </form>

          <p className="text-xs text-center text-gray-600">
            Session IDs are generated automatically per login
          </p>
        </div>
      </div>
    </div>
  );
}

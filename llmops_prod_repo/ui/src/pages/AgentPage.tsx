import { useState, useRef, useEffect, useCallback } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Send, Bot, User, TicketCheck, Eye, Loader2,
  AlertCircle, Copy, Check, Sparkles, Clock, ExternalLink
} from "lucide-react";
import { format } from "date-fns";
import clsx from "clsx";
import { api } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import type { ChatMessage } from "@/types";

function MessageBubble({ msg, jiraUrl }: { msg: ChatMessage; jiraUrl: string }) {
  const [copied, setCopied] = useState(false);
  const isUser = msg.role === "user";
  const isError = msg.role === "error";

  const copy = async () => {
    await navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={clsx("flex gap-3 animate-slide-up", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div className={clsx(
        "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
        isUser ? "bg-brand-600" : isError ? "bg-red-600" : "bg-gray-700"
      )}>
        {isUser ? <User size={15} className="text-white" /> : isError ? <AlertCircle size={15} className="text-white" /> : <Bot size={15} className="text-gray-300" />}
      </div>

      {/* Bubble */}
      <div className={clsx("flex-1 max-w-[80%]", isUser && "flex flex-col items-end")}>
        <div className={clsx(
          "rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser  ? "bg-brand-600 text-white rounded-tr-sm" :
          isError ? "bg-red-900/40 border border-red-800 text-red-300 rounded-tl-sm" :
                    "bg-gray-800 text-gray-100 rounded-tl-sm"
        )}>
          {/* Parse output format: "Plan: X | Tool: Y | ..." */}
          {!isUser && !isError && msg.content.includes("|") ? (
            <ParsedOutput raw={msg.content} jiraUrl={jiraUrl} />
          ) : (
            <p className="whitespace-pre-wrap">{msg.content}</p>
          )}
        </div>

        {/* Meta */}
        <div className={clsx("flex items-center gap-2 mt-1 px-1", isUser && "flex-row-reverse")}>
          <span className="text-xs text-gray-600">{format(msg.timestamp, "HH:mm:ss")}</span>
          {msg.latencyMs != null && (
            <span className="flex items-center gap-0.5 text-xs text-gray-600">
              <Clock size={10} />{msg.latencyMs.toFixed(0)}ms
            </span>
          )}
          {!isUser && (
            <button onClick={copy} className="text-gray-600 hover:text-gray-400 transition-colors">
              {copied ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ParsedOutput({ raw, jiraUrl }: { raw: string; jiraUrl: string }) {
  const parts = raw.split("|").map((p) => p.trim());

  return (
    <div className="space-y-3">
      {parts.map((part, i) => {
        const colonIdx = part.indexOf(":");
        if (colonIdx === -1) return null;
        const label = part.slice(0, colonIdx).trim();
        const value = part.slice(colonIdx + 1).trim();

        // ── Ticket list table ────────────────────────────────────────────────
        if (label.toLowerCase() === "tool" && value.startsWith("Recent tickets:")) {
          const ticketsPart = value.replace(/^Recent tickets:\s*/, "");
          const entries = ticketsPart.split(/,\s*(?=[A-Z]+-\d+:)/);
          const tickets = entries
            .map((e) => {
              const m = e.match(/^([A-Z]+-\d+):\s*(.+)$/);
              return m ? { key: m[1], summary: m[2].trim() } : null;
            })
            .filter(Boolean) as { key: string; summary: string }[];

          return (
            <div key={i}>
              <span className="text-xs text-gray-500 font-medium uppercase tracking-wide">
                Recent Tickets
              </span>
              <div className="mt-2 overflow-x-auto rounded-lg border border-gray-700">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-gray-700/50">
                      <th className="text-left px-3 py-2 text-xs text-gray-400 font-medium w-28 border-b border-gray-700">
                        Key
                      </th>
                      <th className="text-left px-3 py-2 text-xs text-gray-400 font-medium border-b border-gray-700">
                        Summary
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {tickets.map((t, ti) => (
                      <tr
                        key={t.key}
                        className={clsx(
                          "transition-colors hover:bg-gray-700/40",
                          ti < tickets.length - 1 && "border-b border-gray-700/50"
                        )}
                      >
                        <td className="px-3 py-2">
                          <a
                            href={`${jiraUrl}/browse/${t.key}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-brand-300 font-mono font-medium hover:text-brand-200 hover:underline"
                          >
                            <TicketCheck size={12} className="text-emerald-400 flex-shrink-0" />
                            {t.key}
                            <ExternalLink size={10} className="text-gray-500" />
                          </a>
                        </td>
                        <td className="px-3 py-2 text-gray-200">{t.summary}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        }

        // ── Created ticket link ──────────────────────────────────────────────
        const createdMatch = value.match(/Ticket ([A-Z]+-\d+) created/);
        if (label.toLowerCase() === "tool" && createdMatch) {
          const key = createdMatch[1];
          return (
            <div key={i} className="flex items-start gap-2">
              <span className="text-xs text-gray-500 font-medium uppercase tracking-wide mt-0.5 w-16 flex-shrink-0">
                {label}
              </span>
              <span className="text-sm text-emerald-400 flex items-center gap-1.5">
                <TicketCheck size={14} />
                Ticket{" "}
                <a
                  href={`${jiraUrl}/browse/${key}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand-300 font-mono font-medium hover:underline inline-flex items-center gap-0.5"
                >
                  {key}
                  <ExternalLink size={10} className="text-gray-500" />
                </a>
                {" "}created
              </span>
            </div>
          );
        }

        // ── Default row ──────────────────────────────────────────────────────
        return (
          <div key={i} className="flex items-start gap-2">
            <span className="text-xs text-gray-500 font-medium uppercase tracking-wide mt-0.5 w-16 flex-shrink-0">
              {label}
            </span>
            <span className="text-sm text-gray-300">{value || "—"}</span>
          </div>
        );
      })}
    </div>
  );
}

const SUGGESTIONS = [
  { icon: TicketCheck, label: "Create ticket",    text: "Create a ticket: " },
  { icon: Eye,         label: "View tickets",     text: "Show me the latest 5 tickets" },
  { icon: Sparkles,    label: "Bug report",       text: "Create a ticket: Bug — " },
];

export default function AgentPage() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: `Hello! I'm your LLMOps agent. I can create and manage Jira tickets in the **${user?.role === "PRODUCT_OWNER" ? "MC" : "TEST"}** project. How can I help?`,
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data: configData } = useQuery({
    queryKey: ["config"],
    queryFn: api.config,
    staleTime: Infinity,
  });
  const jiraUrl = configData?.jira_url ?? "";

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const mutation = useMutation({
    mutationFn: api.runAgent,
    onSuccess: (data, _vars, ctx) => {
      const start = (ctx as number);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.output,
          timestamp: new Date(),
          correlationId: data.correlation_id,
          latencyMs: performance.now() - start,
        },
      ]);
    },
    onError: (err: Error) => {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "error",
          content: err.message,
          timestamp: new Date(),
        },
      ]);
    },
  });

  const sendMessage = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed || !user) return;

    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: trimmed, timestamp: new Date() },
    ]);
    setInput("");

    mutation.mutate(
      { input: trimmed, user: user.email, role: user.role, session_id: user.sessionId },
      { context: performance.now() }
    );
  }, [user, mutation]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} jiraUrl={jiraUrl} />
        ))}

        {/* Typing indicator */}
        {mutation.isPending && (
          <div className="flex gap-3 animate-fade-in">
            <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center flex-shrink-0">
              <Bot size={15} className="text-gray-300" />
            </div>
            <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce [animation-delay:0ms]" />
                <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce [animation-delay:150ms]" />
                <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick suggestions (shown when chat is empty-ish) */}
      {messages.length <= 1 && (
        <div className="px-6 pb-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map(({ icon: Icon, label, text }) => (
            <button
              key={label}
              onClick={() => { setInput(text); textareaRef.current?.focus(); }}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700
                         text-sm text-gray-300 hover:bg-gray-700 hover:text-white transition-all duration-150"
            >
              <Icon size={14} className="text-brand-400" />
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div className="px-6 pb-6 pt-2 border-t border-gray-800 bg-gray-950/80 backdrop-blur">
        <div className="flex items-end gap-3 bg-gray-800 border border-gray-700 rounded-xl p-3
                        focus-within:border-brand-500 focus-within:ring-1 focus-within:ring-brand-500 transition-all">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask the agent… (⏎ to send, Shift+⏎ for newline)"
            className="flex-1 resize-none bg-transparent text-sm text-gray-100 placeholder-gray-500
                       focus:outline-none max-h-32 overflow-y-auto leading-relaxed"
            style={{ minHeight: "24px" }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || mutation.isPending}
            className="flex-shrink-0 w-9 h-9 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-40
                       disabled:cursor-not-allowed flex items-center justify-center transition-all"
          >
            {mutation.isPending
              ? <Loader2 size={16} className="text-white animate-spin" />
              : <Send size={16} className="text-white" />
            }
          </button>
        </div>
        <p className="text-xs text-gray-600 mt-2 text-center">
          Logged in as <span className="text-brand-400">{user?.email}</span> · Role: <span className="text-brand-400">{user?.role}</span>
        </p>
      </div>
    </div>
  );
}

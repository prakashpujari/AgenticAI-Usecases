import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRecentTickets } from '../api/client';
import type { RecentTicket } from '../types';

// ── Badge helpers (reuse same colour scale as CreateTicketPage) ───────────────
const PRIORITY_BADGE: Record<string, string> = {
  P0: 'bg-red-100 text-red-700 border border-red-200',
  P1: 'bg-orange-100 text-orange-700 border border-orange-200',
  P2: 'bg-yellow-100 text-yellow-700 border border-yellow-200',
  P3: 'bg-green-100 text-green-700 border border-green-200',
};

const TYPE_BADGE: Record<string, string> = {
  Epic: 'bg-purple-100 text-purple-700',
  Story: 'bg-blue-100 text-blue-700',
  Bug: 'bg-red-100 text-red-700',
  Task: 'bg-gray-100 text-gray-700',
  'Sub-task': 'bg-gray-100 text-gray-500',
};

const STATUS_BADGE: Record<string, string> = {
  'To Do': 'bg-gray-100 text-gray-600',
  'In Progress': 'bg-blue-100 text-blue-700',
  Done: 'bg-green-100 text-green-700',
  Open: 'bg-yellow-100 text-yellow-700',
  Closed: 'bg-gray-100 text-gray-500',
  Resolved: 'bg-green-100 text-green-600',
};

// Format ISO timestamp to "May 7, 2026" or "2 hours ago" style
function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    const now = Date.now();
    const diffMs = now - d.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);
    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${Math.floor(diffHours)}h ago`;
    if (diffHours < 48) return 'Yesterday';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return iso;
  }
}

// ── Single ticket row ─────────────────────────────────────────────────────────
const TicketRow: React.FC<{ ticket: RecentTicket }> = ({ ticket }) => (
  <a
    href={ticket.url}
    target="_blank"
    rel="noopener noreferrer"
    className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 transition-colors group rounded-lg"
  >
    {/* Type badge */}
    <span
      className={`shrink-0 mt-0.5 text-xs font-medium px-2 py-0.5 rounded ${
        TYPE_BADGE[ticket.issue_type] ?? 'bg-gray-100 text-gray-600'
      }`}
    >
      {ticket.issue_type}
    </span>

    {/* Main content */}
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-mono text-xs text-indigo-600 font-semibold shrink-0">
          {ticket.jira_key}
        </span>
        <span className="text-sm text-gray-800 font-medium truncate group-hover:text-indigo-600 transition-colors">
          {ticket.title}
        </span>
      </div>
      <div className="flex items-center gap-2 mt-1 flex-wrap">
        {/* Status */}
        <span
          className={`text-xs px-1.5 py-0.5 rounded ${
            STATUS_BADGE[ticket.status] ?? 'bg-gray-100 text-gray-600'
          }`}
        >
          {ticket.status}
        </span>
        {/* Priority */}
        <span
          className={`text-xs font-mono px-1.5 py-0.5 rounded ${
            PRIORITY_BADGE[ticket.priority] ?? 'bg-gray-100 text-gray-600'
          }`}
        >
          {ticket.priority}
        </span>
        {/* Assignee */}
        {ticket.assignee && (
          <span className="text-xs text-gray-500 truncate">
            {ticket.assignee}
          </span>
        )}
        {/* Labels */}
        {ticket.labels.slice(0, 3).map((l) => (
          <span
            key={l}
            className="text-xs px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-600"
          >
            {l}
          </span>
        ))}
        {ticket.labels.length > 3 && (
          <span className="text-xs text-gray-400">+{ticket.labels.length - 3}</span>
        )}
      </div>
    </div>

    {/* Created timestamp */}
    <span className="shrink-0 text-xs text-gray-400 mt-0.5 whitespace-nowrap">
      {formatDate(ticket.created)}
    </span>
  </a>
);

// ── Panel ─────────────────────────────────────────────────────────────────────
interface RecentTicketsPanelProps {
  projects: string[];
  limit?: number;
}

const RecentTicketsPanel: React.FC<RecentTicketsPanelProps> = ({
  projects,
  limit = 5,
}) => {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['recent-tickets', projects.join(','), limit],
    queryFn: () => getRecentTickets(projects, limit),
    // Refresh every 60 s so the panel stays current without manual reload
    refetchInterval: 60_000,
    // Keep previous data visible while refreshing in the background
    placeholderData: (prev) => prev,
  });

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <span className="text-base font-semibold text-gray-800">Recent Tickets</span>
          {data && (
            <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">
              {data.tickets.length}
            </span>
          )}
          <span className="text-xs text-gray-400">
            [{projects.join(', ')}]
          </span>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          title="Refresh"
          className="text-gray-400 hover:text-indigo-600 transition-colors text-sm"
        >
          ↻
        </button>
      </div>

      {/* Body */}
      {isLoading && (
        <div className="px-4 py-6 text-center text-sm text-gray-400 animate-pulse">
          Loading tickets…
        </div>
      )}

      {isError && (
        <div className="px-4 py-4 text-sm text-red-600 text-center">
          Could not load recent tickets.{' '}
          <button
            type="button"
            onClick={() => refetch()}
            className="underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {data && data.tickets.length === 0 && (
        <div className="px-4 py-6 text-center text-sm text-gray-400">
          No tickets found in {projects.join(', ')}.
        </div>
      )}

      {data && data.tickets.length > 0 && (
        <div className="divide-y divide-gray-50">
          {data.tickets.map((ticket) => (
            <TicketRow key={ticket.jira_key} ticket={ticket} />
          ))}
        </div>
      )}

      {/* Footer */}
      {data && data.tickets.length > 0 && (
        <div className="px-4 py-2 border-t border-gray-100 text-right">
          <a
            href={`https://mailtopprakash01.atlassian.net/jira/software/projects/${projects[0]}/boards`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-indigo-500 hover:text-indigo-700 hover:underline"
          >
            View all in Jira →
          </a>
        </div>
      )}
    </div>
  );
};

export default RecentTicketsPanel;

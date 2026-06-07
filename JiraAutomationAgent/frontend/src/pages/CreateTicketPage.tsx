import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { createTicket } from '../api/client';
import type { CreateTicketRequest, TicketDraft, TicketResponse } from '../types';
import TicketForm from '../components/TicketForm';
import AIReviewPanel from '../components/AIReviewPanel';
import ExplainerPanel from '../components/ExplainerPanel';
import DedupeMatchesPanel from '../components/DedupeMatchesPanel';
import AcceptanceCriteriaEditor from '../components/AcceptanceCriteriaEditor';
import RecentTicketsPanel from '../components/RecentTicketsPanel';

// Priority → Tailwind CSS classes. P0 (Critical) is red; severity decreases
// through orange → yellow → green, giving an intuitive traffic-light signal.
const PRIORITY_BADGE: Record<string, string> = {
  P0: 'bg-red-100 text-red-700 border-red-200',
  P1: 'bg-orange-100 text-orange-700 border-orange-200',
  P2: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  P3: 'bg-green-100 text-green-700 border-green-200',
};

// Issue type → Tailwind CSS classes. Colours match common Jira conventions
// so users familiar with Jira recognise the types instantly.
const TYPE_BADGE: Record<string, string> = {
  Epic: 'bg-purple-100 text-purple-700',
  Story: 'bg-blue-100 text-blue-700',
  Bug: 'bg-red-100 text-red-700',
  Task: 'bg-gray-100 text-gray-700',
  'Sub-task': 'bg-gray-100 text-gray-500',
};

// TicketCard renders a single ticket draft with expand/collapse.
// The first ticket (index 0) starts expanded so users see content immediately;
// subsequent tickets start collapsed to reduce visual noise.
const TicketCard: React.FC<{ ticket: TicketDraft; index: number }> = ({
  ticket,
  index,
}) => {
  const [expanded, setExpanded] = useState(index === 0);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-50 text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded ${
              TYPE_BADGE[ticket.issue_type] ?? 'bg-gray-100 text-gray-600'
            }`}
          >
            {ticket.issue_type}
          </span>
          <span
            className={`shrink-0 text-xs font-mono px-1.5 py-0.5 rounded border ${
              PRIORITY_BADGE[ticket.priority] ?? ''
            }`}
          >
            {ticket.priority}
          </span>
          <span className="text-sm font-medium text-gray-800 truncate">
            {ticket.title}
          </span>
        </div>
        <span className="text-gray-400 text-sm ml-2">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="px-4 py-4 border-t border-gray-100 space-y-4 bg-white">
          {/* Summary */}
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
              Summary
            </h4>
            <p className="text-sm text-gray-700">{ticket.summary}</p>
          </div>

          {/* Description */}
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
              Description
            </h4>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">
              {ticket.description}
            </p>
          </div>

          {/* Priority reasoning */}
          {ticket.priority_reasoning && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
                Priority Reasoning
              </h4>
              <p className="text-sm text-gray-600 italic">
                {ticket.priority_reasoning}
              </p>
            </div>
          )}

          {/* AC */}
          {ticket.acceptance_criteria.length > 0 && (
            <AcceptanceCriteriaEditor
              criteria={ticket.acceptance_criteria}
              onChange={() => {}}
              readOnly
            />
          )}

          {/* Labels */}
          {ticket.labels.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
                Labels
              </h4>
              <div className="flex flex-wrap gap-1">
                {ticket.labels.map((l) => (
                  <span
                    key={l}
                    className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-xs"
                  >
                    {l}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Assumptions / Open questions */}
          {ticket.assumptions.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
                Assumptions
              </h4>
              <ul className="list-disc list-inside space-y-0.5">
                {ticket.assumptions.map((a, i) => (
                  <li key={i} className="text-sm text-gray-600">
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {ticket.open_questions.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">
                Open Questions
              </h4>
              <ul className="list-disc list-inside space-y-0.5">
                {ticket.open_questions.map((q, i) => (
                  <li key={i} className="text-sm text-gray-600">
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ── Page ─────────────────────────────────────────────────────────────────────

const CreateTicketPage: React.FC = () => {
  const [result, setResult] = useState<TicketResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: CreateTicketRequest) => createTicket(payload),
    onSuccess: (data) => setResult(data),
  });

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Create Jira Ticket</h1>
        <p className="text-sm text-gray-500 mt-1">
          Paste raw input and let AI generate production-quality Jira tickets.
        </p>
      </div>

      {/* Recent Tickets — shown above the form so users see context while composing */}
      <RecentTicketsPanel projects={['MC']} limit={5} />

      <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
        <TicketForm
          onSubmit={mutation.mutate}
          isLoading={mutation.isPending}
        />
      </div>

      {mutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          Error: {mutation.error instanceof Error ? mutation.error.message : String(mutation.error)}
        </div>
      )}

      {result && (
        <div className="space-y-6">
          {/* Dedupe warnings */}
          <DedupeMatchesPanel matches={result.dedupe_matches} />

          {/* AI review */}
          <AIReviewPanel review={result.ai_review} />

          {/* Ticket drafts */}
          {result.ticket_drafts.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-base font-semibold text-gray-800">
                Generated Ticket{result.ticket_drafts.length > 1 ? 's' : ''} (
                {result.ticket_drafts.length})
              </h2>
              {result.ticket_drafts.map((t, i) => (
                <TicketCard key={i} ticket={t as TicketDraft} index={i} />
              ))}
            </div>
          )}

          {/* Created issues — split by outcome */}
          {(() => {
            const blocked = result.created_issues.find(i => i.status === 'DUPLICATE_BLOCKED');
            const created = result.created_issues.filter(i => i.jira_key && i.url);
            const failed  = result.created_issues.filter(i => !i.jira_key && i.status !== 'DUPLICATE_BLOCKED');

            return (
              <>
                {/* Hard duplicate block — shown prominently with inline matches */}
                {blocked && (
                  <div className="bg-red-50 border border-red-300 rounded-lg overflow-hidden">
                    <div className="px-4 py-3 border-b border-red-200">
                      <h3 className="font-semibold text-sm text-red-800 flex items-center gap-2">
                        🚫 Creation Blocked — Duplicate Detected
                      </h3>
                      <p className="text-sm text-red-700 mt-1">{blocked.error}</p>
                    </div>
                    {result.dedupe_matches && result.dedupe_matches.length > 0 && (
                      <div className="divide-y divide-red-100">
                        <p className="px-4 py-2 text-xs font-semibold text-red-600 uppercase bg-red-100">
                          Matching ticket{result.dedupe_matches.length > 1 ? 's' : ''} already in Jira
                        </p>
                        {result.dedupe_matches.map((m) => (
                          <div key={m.jira_key} className="px-4 py-3 bg-white flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-0.5">
                                <a
                                  href={m.url || `#`}
                                  target={m.url ? "_blank" : undefined}
                                  rel="noopener noreferrer"
                                  className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded text-indigo-600 hover:underline"
                                >
                                  {m.jira_key}
                                </a>
                                {m.issue_type && <span className="text-xs text-gray-500">{m.issue_type}</span>}
                                {m.priority && <span className="text-xs text-gray-500">{m.priority}</span>}
                              </div>
                              <p className="text-sm font-medium text-gray-800">{m.title}</p>
                              {m.summary && <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{m.summary}</p>}
                            </div>
                            <div className="shrink-0 text-right">
                              <span className={`text-sm font-semibold ${m.similarity_score >= 0.95 ? 'text-red-600' : 'text-orange-500'}`}>
                                {(m.similarity_score * 100).toFixed(1)}%
                              </span>
                              <p className="text-xs text-gray-400">similar</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Successfully created */}
                {created.length > 0 && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <h3 className="font-semibold text-sm text-green-800 mb-2">
                      ✅ Issues Created in Jira
                    </h3>
                    <ul className="space-y-1">
                      {created.map((issue, i) => (
                        <li key={i} className="text-sm">
                          <a
                            href={issue.url!}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-mono text-indigo-600 hover:underline"
                          >
                            {issue.jira_key}
                          </a>{' '}
                          — {issue.title}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Partial failures */}
                {failed.length > 0 && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <h3 className="font-semibold text-sm text-yellow-800 mb-2">
                      ⚠️ Some Issues Failed to Create
                    </h3>
                    <ul className="space-y-1">
                      {failed.map((issue, i) => (
                        <li key={i} className="text-sm text-red-600">
                          Failed: {issue.error ?? 'Unknown error'}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            );
          })()}

          {/* Explainer */}
          <ExplainerPanel explainer={result.how_to_create_explainer} />

          {/* Trace ID */}
          {result.trace_id && (
            <p className="text-xs text-gray-400">
              Trace ID: <span className="font-mono">{result.trace_id}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default CreateTicketPage;

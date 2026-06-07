import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { reviewTicket } from '../api/client';
import type { ReviewTicketRequest, TicketResponse } from '../types';
import AIReviewPanel from '../components/AIReviewPanel';
import ExplainerPanel from '../components/ExplainerPanel';
import DedupeMatchesPanel from '../components/DedupeMatchesPanel';

const DEFAULT_PROJECTS = ['MC', 'PROJ', 'INFRA', 'PLATFORM'];

const ReviewTicketPage: React.FC = () => {
  const [mode, setMode] = useState<'key' | 'content'>('key');
  const [jiraKey, setJiraKey] = useState('');
  const [ticketContent, setTicketContent] = useState('');
  const [userId, setUserId] = useState('po-user-1');
  const [userRole, setUserRole] = useState('product_owner');
  const [selectedProjects, setSelectedProjects] = useState<string[]>(['MC']);
  const [result, setResult] = useState<TicketResponse | null>(null);

  const toggleProject = (proj: string) =>
    setSelectedProjects((prev) =>
      prev.includes(proj) ? prev.filter((p) => p !== proj) : [...prev, proj],
    );

  const mutation = useMutation({
    mutationFn: (payload: ReviewTicketRequest) => reviewTicket(payload),
    onSuccess: (data) => setResult(data),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: ReviewTicketRequest = {
      user_id: userId,
      user_role: userRole,
      allowed_projects: selectedProjects,
      ...(mode === 'key'
        ? { jira_key: jiraKey.trim() }
        : { ticket_content: ticketContent.trim() }),
    };
    mutation.mutate(payload);
  };

  const canSubmit =
    !mutation.isPending &&
    selectedProjects.length > 0 &&
    (mode === 'key' ? jiraKey.trim() !== '' : ticketContent.trim().length > 10);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Review Jira Ticket</h1>
        <p className="text-sm text-gray-500 mt-1">
          Enter a Jira key or paste ticket content for an AI quality review.
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Mode switcher */}
          <div className="flex gap-3">
            {(['key', 'content'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`px-4 py-1.5 rounded-full text-sm border transition-colors ${
                  mode === m
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:border-indigo-400'
                }`}
              >
                {m === 'key' ? 'By Jira Key' : 'Paste Content'}
              </button>
            ))}
          </div>

          {mode === 'key' ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Jira Issue Key *
              </label>
              <input
                type="text"
                value={jiraKey}
                onChange={(e) => setJiraKey(e.target.value.toUpperCase())}
                placeholder="PROJ-123"
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Ticket Content *
              </label>
              <textarea
                value={ticketContent}
                onChange={(e) => setTicketContent(e.target.value)}
                rows={7}
                required
                placeholder="Paste the full ticket content (title, description, ACs, etc.)"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
              />
            </div>
          )}

          {/* Allowed projects */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Allowed Projects *
            </label>
            <div className="flex flex-wrap gap-2">
              {DEFAULT_PROJECTS.map((proj) => (
                <button
                  key={proj}
                  type="button"
                  onClick={() => toggleProject(proj)}
                  className={`px-3 py-1 rounded-full text-xs font-mono border transition-colors ${
                    selectedProjects.includes(proj)
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-indigo-400'
                  }`}
                >
                  {proj}
                </button>
              ))}
            </div>
          </div>

          {/* User / role */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                User ID
              </label>
              <input
                type="text"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Role
              </label>
              <select
                value={userRole}
                onChange={(e) => setUserRole(e.target.value)}
                className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              >
                <option value="product_owner">Product Owner</option>
                <option value="engineer">Engineer</option>
                <option value="qa">QA</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {mutation.isPending ? 'Reviewing…' : 'Review Ticket'}
          </button>
        </form>
      </div>

      {mutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          Error: {mutation.error instanceof Error ? mutation.error.message : String(mutation.error)}
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <DedupeMatchesPanel matches={result.dedupe_matches} />
          <AIReviewPanel review={result.ai_review} />
          <ExplainerPanel explainer={result.how_to_create_explainer} />

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

export default ReviewTicketPage;

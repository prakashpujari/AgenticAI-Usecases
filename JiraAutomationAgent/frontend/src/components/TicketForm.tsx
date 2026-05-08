import React, { useState } from 'react';
import type { CreateTicketRequest } from '../types';

interface Props {
  onSubmit: (payload: CreateTicketRequest) => void;
  isLoading: boolean;
}

const DEFAULT_PROJECTS = ['MC', 'PROJ', 'INFRA', 'PLATFORM'];

const TicketForm: React.FC<Props> = ({ onSubmit, isLoading }) => {
  const [rawInput, setRawInput] = useState('');
  const [userId, setUserId] = useState('po-user-1');
  const [userRole, setUserRole] = useState('product_owner');
  const [selectedProjects, setSelectedProjects] = useState<string[]>(['MC']);
  const [customProject, setCustomProject] = useState('');
  const [contextHints, setContextHints] = useState('');
  const [createInJira, setCreateInJira] = useState(false);

  const toggleProject = (proj: string) => {
    setSelectedProjects((prev) =>
      prev.includes(proj) ? prev.filter((p) => p !== proj) : [...prev, proj],
    );
  };

  const addCustomProject = () => {
    const key = customProject.toUpperCase().trim();
    if (key && !selectedProjects.includes(key)) {
      setSelectedProjects((prev) => [...prev, key]);
    }
    setCustomProject('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawInput.trim() || selectedProjects.length === 0) return;
    onSubmit({
      raw_input: rawInput.trim(),
      user_id: userId,
      user_role: userRole,
      allowed_projects: selectedProjects,
      allowed_components: [],
      context_hints: contextHints || undefined,
      create_in_jira: createInJira,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Raw input */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Input *{' '}
          <span className="text-gray-400 font-normal">
            (complaint, support ticket, log, note…)
          </span>
        </label>
        <textarea
          value={rawInput}
          onChange={(e) => setRawInput(e.target.value)}
          rows={6}
          required
          placeholder="Paste your raw input here — the AI will infer the correct ticket type, title, description, priority, and acceptance criteria."
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
        />
      </div>

      {/* Allowed projects */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Allowed Projects *
        </label>
        <div className="flex flex-wrap gap-2 mb-2">
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
          {selectedProjects
            .filter((p) => !DEFAULT_PROJECTS.includes(p))
            .map((proj) => (
              <button
                key={proj}
                type="button"
                onClick={() => toggleProject(proj)}
                className="px-3 py-1 rounded-full text-xs font-mono border bg-indigo-600 text-white border-indigo-600"
              >
                {proj} ×
              </button>
            ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={customProject}
            onChange={(e) => setCustomProject(e.target.value.toUpperCase())}
            placeholder="Custom key…"
            maxLength={10}
            className="border border-gray-300 rounded px-2 py-1 text-xs w-32 focus:outline-none focus:ring-1 focus:ring-indigo-400"
          />
          <button
            type="button"
            onClick={addCustomProject}
            className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200 text-gray-700"
          >
            Add
          </button>
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

      {/* Optional context hints */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Context Hints{' '}
          <span className="text-gray-400 font-normal">(optional)</span>
        </label>
        <input
          type="text"
          value={contextHints}
          onChange={(e) => setContextHints(e.target.value)}
          placeholder="e.g. mobile app, iOS 17, payment module"
          className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
        />
      </div>

      {/* Create in Jira toggle */}
      <label className="flex items-center gap-2 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={createInJira}
          onChange={(e) => setCreateInJira(e.target.checked)}
          className="w-4 h-4 accent-indigo-600"
        />
        <span className="text-sm text-gray-700">
          Create approved ticket(s) in Jira
        </span>
      </label>

      <button
        type="submit"
        disabled={isLoading || !rawInput.trim() || selectedProjects.length === 0}
        className="w-full py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? 'Generating…' : 'Generate Ticket(s)'}
      </button>
    </form>
  );
};

export default TicketForm;

import React from 'react';
import type { DedupeMatch } from '../types';

interface Props {
  matches: DedupeMatch[];
}

const SIMILARITY_COLOR = (score: number): string => {
  if (score >= 0.95) return 'text-red-600 font-semibold';
  if (score >= 0.90) return 'text-orange-500 font-semibold';
  return 'text-yellow-600';
};

const DedupeMatchesPanel: React.FC<Props> = ({ matches }) => {
  if (!matches || matches.length === 0) return null;

  return (
    <div className="border border-orange-200 rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 bg-orange-50 border-b border-orange-200">
        <span className="text-lg">🔁</span>
        <h3 className="font-semibold text-sm text-orange-800">
          Potential Duplicates Found ({matches.length})
        </h3>
      </div>

      <div className="divide-y divide-gray-100">
        {matches.map((m) => (
          <div key={m.jira_key} className="px-4 py-3 bg-white hover:bg-orange-50">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  {m.url ? (
                    <a
                      href={m.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded text-indigo-600 hover:underline"
                    >
                      {m.jira_key}
                    </a>
                  ) : (
                    <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded text-gray-700">
                      {m.jira_key}
                    </span>
                  )}
                  {m.issue_type && (
                    <span className="text-xs text-gray-500">{m.issue_type}</span>
                  )}
                  {m.priority && (
                    <span className="text-xs text-gray-500">{m.priority}</span>
                  )}
                </div>
                <p className="text-sm font-medium text-gray-800 truncate">{m.title}</p>
                <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{m.summary}</p>
              </div>
              <div className="shrink-0 text-right">
                <span className={`text-sm ${SIMILARITY_COLOR(m.similarity_score)}`}>
                  {(m.similarity_score * 100).toFixed(1)}%
                </span>
                <p className="text-xs text-gray-400">similar</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default DedupeMatchesPanel;

import React, { useState } from 'react';
import type { ExplainerOutput } from '../types';

interface Props {
  explainer: ExplainerOutput | null;
}

const ExplainerPanel: React.FC<Props> = ({ explainer }) => {
  const [open, setOpen] = useState(false);

  if (!explainer || !explainer.principles) return null;

  return (
    <div className="border border-indigo-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-indigo-50 hover:bg-indigo-100 text-left"
      >
        <span className="font-semibold text-sm text-indigo-800">
          💡 PO Coaching — How to Create Good Tickets
        </span>
        <span className="text-indigo-500 text-sm">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-4 py-3 bg-white space-y-4">
          {/* General principles */}
          {explainer.principles.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                General Principles
              </h4>
              <ol className="list-decimal list-inside space-y-1">
                {explainer.principles.map((p, i) => (
                  <li key={i} className="text-sm text-gray-700">
                    {p}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Applied to this ticket */}
          {explainer.applied_to_this_ticket.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Applied to This Ticket
              </h4>
              <ul className="space-y-1">
                {explainer.applied_to_this_ticket.map((obs, i) => (
                  <li key={i} className="text-sm text-gray-700 flex gap-2">
                    <span className="text-indigo-400 mt-0.5">›</span>
                    <span>{obs}</span>
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

export default ExplainerPanel;

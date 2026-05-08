import React from 'react';
import type { AcceptanceCriteria } from '../types';

interface Props {
  criteria: AcceptanceCriteria[];
  onChange: (updated: AcceptanceCriteria[]) => void;
  readOnly?: boolean;
}

const empty = (): AcceptanceCriteria => ({
  scenario: '',
  given: '',
  when: '',
  then: '',
});

const AcceptanceCriteriaEditor: React.FC<Props> = ({
  criteria,
  onChange,
  readOnly = false,
}) => {
  const update = (
    index: number,
    field: keyof AcceptanceCriteria,
    value: string,
  ) => {
    const updated = criteria.map((ac, i) =>
      i === index ? { ...ac, [field]: value } : ac,
    );
    onChange(updated);
  };

  const addCriteria = () => onChange([...criteria, empty()]);
  const removeCriteria = (index: number) =>
    onChange(criteria.filter((_, i) => i !== index));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">
          Acceptance Criteria (Gherkin)
        </h3>
        {!readOnly && (
          <button
            type="button"
            onClick={addCriteria}
            className="text-xs px-2 py-1 bg-indigo-50 text-indigo-700 rounded hover:bg-indigo-100"
          >
            + Add Scenario
          </button>
        )}
      </div>

      {criteria.length === 0 && (
        <p className="text-sm text-gray-400 italic">No acceptance criteria yet.</p>
      )}

      {criteria.map((ac, i) => (
        <div
          key={i}
          className="border border-gray-200 rounded-lg p-3 bg-gray-50 space-y-2"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-500">
              Scenario {i + 1}
            </span>
            {!readOnly && (
              <button
                type="button"
                onClick={() => removeCriteria(i)}
                className="text-xs text-red-400 hover:text-red-600"
              >
                Remove
              </button>
            )}
          </div>

          {(
            [
              { label: 'Scenario', field: 'scenario' },
              { label: 'Given', field: 'given' },
              { label: 'When', field: 'when' },
              { label: 'Then', field: 'then' },
            ] as { label: string; field: keyof AcceptanceCriteria }[]
          ).map(({ label, field }) => (
            <div key={field} className="flex items-start gap-2">
              <span className="w-16 text-xs font-mono text-indigo-600 pt-1">
                {label}
              </span>
              <input
                type="text"
                value={ac[field]}
                readOnly={readOnly}
                onChange={(e) => update(i, field, e.target.value)}
                placeholder={`${label}…`}
                className={`flex-1 text-sm border rounded px-2 py-1 ${
                  readOnly
                    ? 'bg-white border-gray-200 text-gray-700 cursor-default'
                    : 'border-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-300'
                }`}
              />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};

export default AcceptanceCriteriaEditor;

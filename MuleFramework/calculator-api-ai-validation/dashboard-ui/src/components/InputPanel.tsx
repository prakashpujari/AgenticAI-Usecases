import type { PipelineRequest } from '../types';

interface Props {
  request: PipelineRequest;
  onChange: (r: PipelineRequest) => void;
  onRun: () => void;
  loading: boolean;
}

const fields: { key: keyof PipelineRequest; label: string; placeholder: string; icon: string; mono?: boolean; hint?: string }[] = [
  {
    key: 'munit_reports_dir',
    label: 'MUnit Reports Directory',
    placeholder: '/path/to/sample_reports',
    icon: '📁',
    mono: true,
    hint: 'Directory containing MUnit XML test report files',
  },
  {
    key: 'raml_path',
    label: 'RAML Spec Path',
    placeholder: '/path/to/api.raml',
    icon: '📄',
    mono: true,
    hint: 'Full path to your RAML API specification file',
  },
  {
    key: 'mule_xml_dir',
    label: 'Mule XML Directory',
    placeholder: '/path/to/mule',
    icon: '⚙️',
    mono: true,
    hint: 'Directory containing Mule flow XML configuration files',
  },
  {
    key: 'application',
    label: 'Application Name',
    placeholder: 'calculator-api',
    icon: '🏷️',
    hint: 'Name of your MuleSoft application',
  },
  {
    key: 'runtime',
    label: 'Runtime Version',
    placeholder: '4.9',
    icon: '🔢',
    hint: 'Mule runtime version (e.g. 4.9)',
  },
];

export function InputPanel({ request, onChange, onRun, loading }: Props) {
  const set = (key: keyof PipelineRequest, value: string) =>
    onChange({ ...request, [key]: value });

  return (
    <div style={{
      background: 'linear-gradient(135deg, #161b2e 0%, #12172a 100%)',
      border: '1px solid rgba(139,92,246,0.2)',
      borderRadius: '20px',
      padding: '2rem',
      boxShadow: '0 4px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04)',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Background glow orb */}
      <div style={{
        position: 'absolute', top: '-60px', right: '-60px',
        width: '200px', height: '200px', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(124,58,237,0.08) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem', marginBottom: '1.75rem' }}>
        <div style={{
          width: '36px', height: '36px', borderRadius: '10px',
          background: 'linear-gradient(135deg, rgba(124,58,237,0.3), rgba(79,70,229,0.2))',
          border: '1px solid rgba(124,58,237,0.35)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1rem',
        }}>
          ⚙️
        </div>
        <div>
          <h2 style={{ color: '#f1f5f9', fontSize: '1rem', fontWeight: 700, margin: 0, letterSpacing: '-0.01em' }}>
            Pipeline Configuration
          </h2>
          <p style={{ color: '#475569', fontSize: '0.72rem', margin: 0, marginTop: '0.15rem' }}>
            Configure paths and settings for your validation run
          </p>
        </div>
      </div>

      {/* Fields grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1.125rem', marginBottom: '1.75rem' }}>
        {fields.map(({ key, label, placeholder, icon, mono, hint }) => (
          <FieldInput
            key={key}
            label={label}
            icon={icon}
            hint={hint}
            value={request[key]}
            placeholder={placeholder}
            mono={mono}
            onChange={v => set(key, v)}
          />
        ))}
      </div>

      {/* Run button */}
      <div style={{ display: 'flex', justifyContent: 'stretch' }}>
        <button
          onClick={onRun}
          disabled={loading}
          style={{
            width: '100%',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.625rem',
            padding: '0.9rem 2rem', borderRadius: '12px', fontWeight: 700,
            fontSize: '1rem', cursor: loading ? 'not-allowed' : 'pointer',
            background: loading
              ? 'rgba(55,65,81,0.5)'
              : 'linear-gradient(135deg, #7c3aed 0%, #4f46e5 50%, #0891b2 100%)',
            color: loading ? '#6b7280' : 'white', border: 'none',
            boxShadow: loading ? 'none' : '0 4px 24px rgba(124,58,237,0.45), 0 0 0 1px rgba(124,58,237,0.3)',
            transition: 'all 0.25s ease',
            letterSpacing: '0.01em',
            fontFamily: 'Inter, system-ui, sans-serif',
          }}
        >
          {loading ? (
            <>
              <Spinner />
              Running Pipeline…
            </>
          ) : (
            <>
              <PlayIcon />
              Run Validation
            </>
          )}
        </button>
      </div>

      <style>{`
        @keyframes spinBtn { to { transform: rotate(360deg); } }
        .field-input:focus {
          border-color: #7c3aed !important;
          box-shadow: 0 0 0 3px rgba(124,58,237,0.18) !important;
        }
      `}</style>
    </div>
  );
}

function FieldInput({
  label, icon, hint, value, placeholder, mono, onChange,
}: {
  label: string; icon: string; hint?: string; value: string;
  placeholder: string; mono?: boolean; onChange: (v: string) => void;
}) {
  return (
    <div>
      <label style={{
        display: 'flex', alignItems: 'center', gap: '0.4rem',
        fontSize: '0.72rem', fontWeight: 600, color: '#94a3b8',
        marginBottom: '0.45rem', letterSpacing: '0.06em',
      }}>
        <span style={{ fontSize: '0.85rem' }}>{icon}</span>
        {label.toUpperCase()}
      </label>
      <input
        type="text"
        className="field-input"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width: '100%', padding: '0.65rem 0.875rem',
          background: 'rgba(15,17,23,0.8)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: '10px', color: '#e2e8f0', outline: 'none',
          fontFamily: mono ? 'ui-monospace, Consolas, "Courier New", monospace' : 'Inter, system-ui, sans-serif',
          fontSize: '0.8rem',
          transition: 'border-color 0.2s, box-shadow 0.2s',
          boxSizing: 'border-box',
        }}
      />
      {hint && (
        <p style={{ fontSize: '0.67rem', color: '#374151', marginTop: '0.3rem', marginLeft: '0.1rem' }}>
          {hint}
        </p>
      )}
    </div>
  );
}

function PlayIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function Spinner() {
  return (
    <div style={{
      width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.25)',
      borderTopColor: 'rgba(255,255,255,0.7)', borderRadius: '50%',
      animation: 'spinBtn 0.75s linear infinite', flexShrink: 0,
    }} />
  );
}

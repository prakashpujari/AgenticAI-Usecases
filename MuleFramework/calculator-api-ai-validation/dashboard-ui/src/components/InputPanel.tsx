import { useState } from 'react';
import type { PipelineRequest } from '../types';

interface Props {
  request: PipelineRequest;
  onChange: (r: PipelineRequest) => void;
  onRun: () => void;
  loading: boolean;
}

type InputMode = 'path' | 'url';

type FieldDef = {
  key: keyof PipelineRequest;
  label: string;
  placeholder: string;
  icon: string;
  mono?: boolean;
  hint?: string;
};

const PATH_SOURCE_FIELDS: FieldDef[] = [
  {
    key: 'munit_reports_dir',
    label: 'MUnit Reports Directory',
    placeholder: 'leave blank to use bundled demo data',
    icon: '📁',
    mono: true,
    hint: 'Directory containing MUnit XML test report files (blank = demo data)',
  },
  {
    key: 'raml_path',
    label: 'RAML Spec Path',
    placeholder: 'leave blank to use bundled demo data',
    icon: '📄',
    mono: true,
    hint: 'Full path to your RAML API specification file (blank = demo data)',
  },
  {
    key: 'mule_xml_dir',
    label: 'Mule XML Directory',
    placeholder: 'leave blank to use bundled demo data',
    icon: '⚙️',
    mono: true,
    hint: 'Directory containing Mule flow XML configuration files (blank = demo data)',
  },
];

const URL_SOURCE_FIELDS: FieldDef[] = [
  {
    key: 'munit_reports_dir',
    label: 'MUnit Reports URL',
    placeholder: 'https://github.com/org/repo/tree/main/path/to/sample_reports',
    icon: '🔗',
    mono: true,
    hint: 'GitHub tree URL — accepts surefire TEST-*.xml reports or src/test/munit/ definition files',
  },
  {
    key: 'raml_path',
    label: 'RAML Spec URL',
    placeholder: 'https://github.com/org/repo/blob/main/path/to/api.raml',
    icon: '🔗',
    mono: true,
    hint: 'GitHub blob URL (or raw URL) of your RAML 1.0 spec file — auto-converted to raw',
  },
  {
    key: 'mule_xml_dir',
    label: 'Mule XML URL',
    placeholder: 'https://github.com/org/repo/tree/main/path/to/mule',
    icon: '🔗',
    mono: true,
    hint: 'GitHub tree URL (or raw URL) of a folder containing Mule flow XML files',
  },
];

const META_FIELDS: FieldDef[] = [
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
  const [inputMode, setInputMode] = useState<InputMode>('path');
  const set = (key: keyof PipelineRequest, value: string) =>
    onChange({ ...request, [key]: value });

  const sourceFields = inputMode === 'url' ? URL_SOURCE_FIELDS : PATH_SOURCE_FIELDS;
  const allFields = [...sourceFields, ...META_FIELDS];

  return (
    <div style={{
      background: 'linear-gradient(135deg, #13172a 0%, #0f1220 100%)',
      border: '1px solid rgba(139,92,246,0.22)',
      borderRadius: '22px',
      padding: '2rem',
      boxShadow: '0 8px 48px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.05)',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Background glow orb */}
      <div style={{
        position: 'absolute', top: '-70px', right: '-70px',
        width: '240px', height: '240px', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(124,58,237,0.1) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute', bottom: '-50px', left: '-50px',
        width: '200px', height: '200px', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(8,145,178,0.07) 0%, transparent 70%)',
        pointerEvents: 'none',
      }} />

      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
          <div style={{
            width: '38px', height: '38px', borderRadius: '10px', flexShrink: 0,
            background: 'linear-gradient(135deg, rgba(124,58,237,0.35), rgba(79,70,229,0.22))',
            border: '1px solid rgba(124,58,237,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem',
            boxShadow: '0 0 16px rgba(124,58,237,0.2)',
          }}>
            ⚙️
          </div>
          <div>
            <h2 style={{ color: '#f1f5f9', fontSize: '1rem', fontWeight: 700, margin: 0, letterSpacing: '-0.01em' }}>
              Pipeline Configuration
            </h2>
            <p style={{ color: '#475569', fontSize: '0.72rem', margin: 0, marginTop: '0.15rem' }}>
              Configure paths or URLs for your validation run
            </p>
          </div>
        </div>

        {/* Input mode toggle */}
        <ModeToggle mode={inputMode} onChange={setInputMode} />
      </div>

      {/* URL mode info banner */}
      {inputMode === 'url' && (
        <div style={{
          padding: '0.75rem 1rem', borderRadius: '10px',
          background: 'linear-gradient(135deg, rgba(8,145,178,0.1), rgba(6,182,212,0.06))',
          border: '1px solid rgba(8,145,178,0.25)',
          marginBottom: '1.25rem',
          fontSize: '0.75rem', color: '#67e8f9',
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.625rem' }}>
            <span style={{ fontSize: '1rem', flexShrink: 0 }}>ℹ️</span>
            <div style={{ lineHeight: 1.6 }}>
              <strong style={{ display: 'block', marginBottom: '0.25rem', color: '#a5f3fc' }}>
                GitHub URLs are supported and auto-converted
              </strong>
              <span style={{ color: '#67e8f9' }}>
                • <strong>blob/</strong> URLs (single files) → converted to raw content automatically<br />
                • <strong>tree/</strong> URLs (folders) → all matching files fetched via GitHub API<br />
                • MUnit folder accepts <code style={{ background: 'rgba(0,0,0,0.3)', padding: '0 3px', borderRadius: '3px' }}>TEST-*.xml</code> surefire reports <strong>or</strong> <code style={{ background: 'rgba(0,0,0,0.3)', padding: '0 3px', borderRadius: '3px' }}>src/test/munit/</code> definition files
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Fields grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
        gap: '1.125rem', marginBottom: '1.75rem',
      }}>
        {allFields.map(({ key, label, placeholder, icon, mono, hint }) => (
          <FieldInput
            key={`${inputMode}-${key}`}
            label={label}
            icon={icon}
            hint={hint}
            value={request[key]}
            placeholder={placeholder}
            mono={mono}
            isUrl={inputMode === 'url' && key !== 'application' && key !== 'runtime'}
            onChange={v => set(key, v)}
          />
        ))}
      </div>

      {/* Run button */}
      <button
        onClick={onRun}
        disabled={loading}
        style={{
          width: '100%',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.625rem',
          padding: '0.95rem 2rem', borderRadius: '13px', fontWeight: 700,
          fontSize: '1rem', cursor: loading ? 'not-allowed' : 'pointer',
          background: loading
            ? 'rgba(40,46,65,0.8)'
            : 'linear-gradient(135deg, #7c3aed 0%, #4f46e5 50%, #0891b2 100%)',
          backgroundSize: loading ? 'auto' : '200% auto',
          color: loading ? '#4b5563' : 'white', border: 'none',
          boxShadow: loading ? 'none' : '0 4px 28px rgba(124,58,237,0.5), 0 0 0 1px rgba(124,58,237,0.35)',
          transition: 'all 0.25s ease',
          letterSpacing: '0.01em',
          fontFamily: 'Inter, system-ui, sans-serif',
          position: 'relative', overflow: 'hidden',
        }}
      >
        {!loading && (
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(135deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0) 100%)',
            pointerEvents: 'none',
          }} />
        )}
        {loading ? (
          <>
            <Spinner />
            Running Pipeline…
          </>
        ) : (
          <>
            <PlayIcon />
            Run Validation Pipeline
          </>
        )}
      </button>

      <style>{`
        .field-input:focus {
          border-color: #7c3aed !important;
          box-shadow: 0 0 0 3px rgba(124,58,237,0.2) !important;
          background: rgba(10,12,22,0.95) !important;
        }
        .field-input-url:focus {
          border-color: #0891b2 !important;
          box-shadow: 0 0 0 3px rgba(8,145,178,0.2) !important;
          background: rgba(10,12,22,0.95) !important;
        }
        .mode-btn:hover { opacity: 0.9; }
      `}</style>
    </div>
  );
}

/* ── Mode Toggle ── */
function ModeToggle({ mode, onChange }: { mode: InputMode; onChange: (m: InputMode) => void }) {
  return (
    <div style={{
      display: 'flex', gap: '0.25rem',
      background: 'rgba(0,0,0,0.4)',
      borderRadius: '11px', padding: '0.25rem',
      border: '1px solid rgba(255,255,255,0.06)',
    }}>
      {(['path', 'url'] as InputMode[]).map(m => {
        const active = mode === m;
        const isUrl = m === 'url';
        const activeColor = isUrl ? '#06b6d4' : '#a78bfa';
        const activeBg = isUrl
          ? 'linear-gradient(135deg, rgba(8,145,178,0.35), rgba(6,182,212,0.22))'
          : 'linear-gradient(135deg, rgba(124,58,237,0.35), rgba(79,70,229,0.22))';
        return (
          <button
            key={m}
            className="mode-btn"
            onClick={() => onChange(m)}
            style={{
              padding: '0.45rem 1.1rem', borderRadius: '8px', border: 'none',
              cursor: 'pointer', fontWeight: 600, fontSize: '0.78rem',
              background: active ? activeBg : 'transparent',
              color: active ? activeColor : '#475569',
              boxShadow: active ? `0 0 12px ${activeColor}25` : 'none',
              transition: 'all 0.2s ease',
              display: 'flex', alignItems: 'center', gap: '0.375rem',
              fontFamily: 'Inter, system-ui, sans-serif',
            }}
          >
            <span>{isUrl ? '🔗' : '📁'}</span>
            {isUrl ? 'URLs' : 'Folder Paths'}
          </button>
        );
      })}
    </div>
  );
}

/* ── GitHub URL type detection ── */
function githubUrlType(value: string): 'blob' | 'tree' | 'raw' | null {
  if (!value.startsWith('http')) return null;
  if (/github\.com\/[^/]+\/[^/]+\/blob\//.test(value)) return 'blob';
  if (/github\.com\/[^/]+\/[^/]+\/tree\//.test(value)) return 'tree';
  if (/raw\.githubusercontent\.com/.test(value)) return 'raw';
  return null;
}

/* ── Field Input ── */
function FieldInput({
  label, icon, hint, value, placeholder, mono, isUrl, onChange,
}: {
  label: string; icon: string; hint?: string; value: string;
  placeholder: string; mono?: boolean; isUrl?: boolean;
  onChange: (v: string) => void;
}) {
  const accentColor = isUrl ? '#06b6d4' : '#7c3aed';
  const ghType = isUrl ? githubUrlType(value) : null;

  const ghBadge: Record<string, { label: string; color: string; bg: string }> = {
    blob: { label: '⚡ GitHub blob → auto-converted to raw', color: '#a5f3fc', bg: 'rgba(8,145,178,0.12)' },
    tree: { label: '📂 GitHub tree → files fetched via API', color: '#86efac', bg: 'rgba(34,197,94,0.1)' },
    raw:  { label: '✓ Raw URL — ready',                    color: '#86efac', bg: 'rgba(34,197,94,0.1)' },
  };

  return (
    <div>
      <label style={{
        display: 'flex', alignItems: 'center', gap: '0.4rem',
        fontSize: '0.7rem', fontWeight: 700, color: isUrl ? '#67e8f9' : '#94a3b8',
        marginBottom: '0.45rem', letterSpacing: '0.07em',
      }}>
        <span style={{ fontSize: '0.85rem' }}>{icon}</span>
        {label.toUpperCase()}
      </label>
      <div style={{ position: 'relative' }}>
        <input
          type={isUrl ? 'url' : 'text'}
          className={isUrl ? 'field-input-url' : 'field-input'}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          style={{
            width: '100%', padding: '0.65rem 0.875rem',
            background: 'rgba(10,12,22,0.85)',
            border: `1px solid ${isUrl ? 'rgba(8,145,178,0.2)' : 'rgba(255,255,255,0.1)'}`,
            borderRadius: '10px', color: '#e2e8f0', outline: 'none',
            fontFamily: mono ? 'ui-monospace, Consolas, "Courier New", monospace' : 'Inter, system-ui, sans-serif',
            fontSize: '0.8rem',
            transition: 'border-color 0.2s, box-shadow 0.2s, background 0.2s',
            boxSizing: 'border-box',
          }}
        />
        {value && !ghType && (
          <div style={{
            position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
            width: '6px', height: '6px', borderRadius: '50%',
            background: accentColor, boxShadow: `0 0 6px ${accentColor}`,
          }} />
        )}
      </div>

      {/* GitHub URL type badge */}
      {ghType && ghBadge[ghType] && (
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
          marginTop: '0.35rem', padding: '0.2rem 0.6rem', borderRadius: '5px',
          background: ghBadge[ghType].bg, fontSize: '0.65rem', fontWeight: 600,
          color: ghBadge[ghType].color, letterSpacing: '0.02em',
        }}>
          {ghBadge[ghType].label}
        </div>
      )}

      {hint && !ghType && (
        <p style={{ fontSize: '0.67rem', color: '#2d3748', marginTop: '0.3rem', marginLeft: '0.1rem', lineHeight: 1.4 }}>
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
      width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.2)',
      borderTopColor: 'rgba(255,255,255,0.6)', borderRadius: '50%',
      animation: 'spin 0.75s linear infinite', flexShrink: 0,
    }} />
  );
}

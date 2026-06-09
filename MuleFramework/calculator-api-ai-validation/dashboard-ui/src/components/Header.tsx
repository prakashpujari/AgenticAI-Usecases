interface Props {
  application?: string;
  runtime?: string;
}

export function Header({ application, runtime }: Props) {
  const appLabel = application?.trim() || 'API';
  const subtitle = runtime?.trim()
    ? `${appLabel.toUpperCase()} · RUNTIME ${runtime} · RELEASE READINESS`
    : 'AI-POWERED RELEASE READINESS PIPELINE';

  return (
    <header style={{
      background: 'linear-gradient(135deg, #1e1040 0%, #16104a 25%, #0f172a 60%, #0f1117 100%)',
      borderBottom: '1px solid rgba(139,92,246,0.25)',
      padding: '0',
      position: 'sticky',
      top: 0,
      zIndex: 100,
      boxShadow: '0 4px 32px rgba(0,0,0,0.6)',
    }}>
      {/* Top accent line */}
      <div style={{ height: '2px', background: 'linear-gradient(90deg, transparent, #7c3aed, #4f46e5, #06b6d4, transparent)' }} />

      <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '1rem 2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
        {/* Left: logo + title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {/* Logo glow */}
          <div style={{ position: 'relative' }}>
            <div style={{
              position: 'absolute', inset: '-4px', borderRadius: '14px',
              background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
              filter: 'blur(8px)', opacity: 0.6,
            }} />
            <div style={{
              position: 'relative',
              width: '46px', height: '46px', borderRadius: '12px',
              background: 'linear-gradient(135deg, #7c3aed 0%, #4f46e5 50%, #0891b2 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '1.375rem', fontWeight: 800, color: 'white',
              boxShadow: '0 0 20px rgba(124,58,237,0.5)',
              letterSpacing: '-0.02em',
            }}>
              AI
            </div>
          </div>

          <div>
            <h1 style={{
              fontSize: '1.3rem', fontWeight: 800, margin: 0, lineHeight: 1.15,
              background: 'linear-gradient(135deg, #f1f5f9 0%, #a78bfa 60%, #67e8f9 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              letterSpacing: '-0.01em',
            }}>
              AI Validation Dashboard
            </h1>
            <p style={{
              fontSize: '0.7rem', margin: 0, marginTop: '0.15rem',
              color: '#7c3aed', letterSpacing: '0.08em', fontWeight: 500,
            }}>
              {subtitle}
            </p>
          </div>
        </div>

        {/* Right: tech pills */}
        <div style={{ display: 'flex', gap: '0.625rem', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <TechPill icon="🔗" label="LangGraph" color="#4f46e5" />
          <TechPill icon="⚡" label="Groq LLM" color="#7c3aed" />
          <TechPill icon="🤖" label="6 Agents" color="#0891b2" />
          <TechPill icon="🔧" label="MuleSoft" color="#059669" />
        </div>
      </div>
    </header>
  );
}

function TechPill({ icon, label, color }: { icon: string; label: string; color: string }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
      padding: '0.3rem 0.75rem', borderRadius: '999px', fontSize: '0.72rem', fontWeight: 600,
      background: `${color}18`, color, border: `1px solid ${color}38`,
      letterSpacing: '0.02em',
      boxShadow: `0 0 8px ${color}18`,
    }}>
      <span style={{ fontSize: '0.8rem' }}>{icon}</span>
      {label}
    </span>
  );
}

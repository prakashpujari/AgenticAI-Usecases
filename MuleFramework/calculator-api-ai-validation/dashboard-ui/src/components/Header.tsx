interface Props {
  application?: string;
  runtime?: string;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
}

export function Header({ application, runtime, theme, onToggleTheme }: Props) {
  const appLabel = application?.trim() || 'API';
  const subtitle = runtime?.trim()
    ? `${appLabel.toUpperCase()} · RUNTIME ${runtime} · RELEASE READINESS`
    : 'MULE-VALIDATION-HUB · AI RELEASE READINESS PIPELINE';

  return (
    <header style={{
      background: 'var(--header-bg)',
      borderBottom: '1px solid var(--header-border)',
      position: 'sticky', top: 0, zIndex: 100,
      boxShadow: 'var(--header-shadow)',
    }}>
      {/* Animated rainbow accent line */}
      <div style={{
        height: '3px',
        background: 'linear-gradient(90deg, transparent 0%, #7c3aed 20%, #4f46e5 40%, #0891b2 60%, #06b6d4 80%, transparent 100%)',
        backgroundSize: '200% auto',
        animation: 'gradientBorder 4s linear infinite',
      }} />

      <div style={{
        maxWidth: '1440px', margin: '0 auto',
        padding: '0.875rem 2rem',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem',
        flexWrap: 'wrap',
      }}>
        {/* Left: logo + title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ position: 'relative', flexShrink: 0 }}>
            <div style={{
              position: 'absolute', inset: '-5px', borderRadius: '15px',
              background: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
              filter: 'blur(10px)', opacity: 0.55,
            }} />
            <div style={{
              position: 'relative',
              width: '48px', height: '48px', borderRadius: '13px',
              background: 'linear-gradient(135deg, #7c3aed 0%, #4f46e5 50%, #0891b2 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '1.4rem', fontWeight: 800, color: 'white',
              boxShadow: '0 0 24px rgba(124,58,237,0.6)',
              letterSpacing: '-0.02em',
            }}>
              AI
            </div>
          </div>

          <div>
            <h1 style={{
              fontSize: '1.35rem', fontWeight: 800, margin: 0, lineHeight: 1.15,
              background: 'linear-gradient(135deg, #f8fafc 0%, #c4b5fd 55%, #67e8f9 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              backgroundClip: 'text', letterSpacing: '-0.015em',
              backgroundSize: '200% auto',
              animation: 'shimmerText 5s linear infinite',
            }}>
              mule-validation-hub
            </h1>
            <p style={{
              fontSize: '0.68rem', margin: 0, marginTop: '0.18rem',
              color: '#a78bfa', letterSpacing: '0.1em', fontWeight: 600,
              textTransform: 'uppercase',
            }}>
              {subtitle}
            </p>
          </div>
        </div>

        {/* Right: tech pills + theme toggle + live badge */}
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <TechPill icon="🔗" label="LangGraph"  color="#4f46e5" />
          <TechPill icon="⚡" label="Groq LLM"   color="#7c3aed" />
          <TechPill icon="🤖" label="6 Agents"   color="#0891b2" />
          <TechPill icon="🔧" label="MuleSoft"   color="#059669" />
          <button
            className="theme-toggle-btn"
            onClick={onToggleTheme}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
          <LiveBadge />
        </div>
      </div>
    </header>
  );
}

function TechPill({ icon, label, color }: { icon: string; label: string; color: string }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
      padding: '0.3rem 0.75rem', borderRadius: '999px',
      fontSize: '0.72rem', fontWeight: 600,
      background: `${color}18`, color, border: `1px solid ${color}38`,
      letterSpacing: '0.02em', boxShadow: `0 0 10px ${color}15`,
    }}>
      <span style={{ fontSize: '0.8rem' }}>{icon}</span>
      {label}
    </span>
  );
}

function LiveBadge() {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.45rem',
      padding: '0.3rem 0.8rem', borderRadius: '999px',
      fontSize: '0.72rem', fontWeight: 700,
      background: 'rgba(34,197,94,0.12)', color: '#4ade80',
      border: '1px solid rgba(34,197,94,0.3)',
      letterSpacing: '0.06em',
      boxShadow: '0 0 12px rgba(34,197,94,0.15)',
    }}>
      <span style={{ position: 'relative', display: 'inline-flex', width: '8px', height: '8px' }}>
        <span style={{
          position: 'absolute', inset: 0, borderRadius: '50%',
          background: '#22c55e',
          animation: 'livePing 1.4s ease-out infinite',
        }} />
        <span style={{
          position: 'relative', width: '8px', height: '8px', borderRadius: '50%',
          background: '#4ade80', boxShadow: '0 0 6px #22c55e',
        }} />
      </span>
      LIVE
    </span>
  );
}

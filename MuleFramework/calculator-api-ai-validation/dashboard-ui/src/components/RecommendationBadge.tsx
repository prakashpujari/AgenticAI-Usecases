import type { Recommendation } from '../types';

const CONFIG: Record<Recommendation, {
  label: string;
  desc: string;
  bg: string;
  border: string;
  color: string;
  icon: string;
  glow: string;
  pulseColor: string;
}> = {
  APPROVED: {
    label: 'APPROVED',
    desc: 'This API meets all quality, security, and performance standards and is ready for production deployment.',
    bg: 'linear-gradient(135deg, rgba(34,197,94,0.12) 0%, rgba(16,185,129,0.08) 100%)',
    border: 'rgba(34,197,94,0.45)',
    color: '#4ade80',
    icon: '✓',
    glow: 'rgba(34,197,94,0.25)',
    pulseColor: 'rgba(34,197,94,0.4)',
  },
  CONDITIONAL: {
    label: 'CONDITIONAL',
    desc: 'Approved with conditions — review agent findings and address flagged issues before deploying to production.',
    bg: 'linear-gradient(135deg, rgba(245,158,11,0.12) 0%, rgba(234,179,8,0.07) 100%)',
    border: 'rgba(245,158,11,0.45)',
    color: '#fbbf24',
    icon: '⚠',
    glow: 'rgba(245,158,11,0.25)',
    pulseColor: 'rgba(245,158,11,0.4)',
  },
  BLOCKED: {
    label: 'BLOCKED',
    desc: 'Critical issues detected — this API is not ready for production. Resolve all blocking findings before proceeding.',
    bg: 'linear-gradient(135deg, rgba(239,68,68,0.12) 0%, rgba(220,38,38,0.07) 100%)',
    border: 'rgba(239,68,68,0.45)',
    color: '#f87171',
    icon: '✕',
    glow: 'rgba(239,68,68,0.25)',
    pulseColor: 'rgba(239,68,68,0.4)',
  },
};

export function RecommendationBadge({ recommendation }: { recommendation: Recommendation }) {
  const cfg = CONFIG[recommendation];

  return (
    <div style={{
      background: cfg.bg,
      border: `1.5px solid ${cfg.border}`,
      borderRadius: '20px',
      padding: '2rem 2.5rem',
      display: 'flex',
      alignItems: 'center',
      gap: '1.75rem',
      boxShadow: `0 0 48px ${cfg.glow}, 0 4px 24px rgba(0,0,0,0.4)`,
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Animated border pulse */}
      <style>{`
        @keyframes recPulse {
          0%, 100% { opacity: 0.6; }
          50% { opacity: 1; }
        }
      `}</style>
      <div style={{
        position: 'absolute', inset: 0, borderRadius: '20px',
        border: `1px solid ${cfg.pulseColor}`,
        animation: 'recPulse 2.5s ease-in-out infinite',
        pointerEvents: 'none',
      }} />

      {/* Icon circle */}
      <div style={{
        flexShrink: 0,
        width: '64px', height: '64px', borderRadius: '50%',
        background: `${cfg.color}18`,
        border: `2px solid ${cfg.color}50`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '2rem',
        color: cfg.color,
        boxShadow: `0 0 24px ${cfg.glow}`,
        fontWeight: 900,
        lineHeight: 1,
      }}>
        {cfg.icon}
      </div>

      {/* Text */}
      <div style={{ flex: 1 }}>
        <div style={{
          fontSize: '2rem', fontWeight: 900, color: cfg.color,
          letterSpacing: '0.04em', lineHeight: 1, marginBottom: '0.5rem',
          textShadow: `0 0 20px ${cfg.glow}`,
        }}>
          {cfg.label}
        </div>
        <div style={{
          fontSize: '0.875rem', color: '#94a3b8', lineHeight: 1.6, maxWidth: '480px',
        }}>
          {cfg.desc}
        </div>
      </div>
    </div>
  );
}

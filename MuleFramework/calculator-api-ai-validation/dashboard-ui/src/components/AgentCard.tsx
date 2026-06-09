import { useState } from 'react';
import type { AgentReport, Severity } from '../types';

const AGENT_META: Record<string, { icon: string; label: string; color: string; gradientFrom: string; gradientTo: string }> = {
  api_design: {
    icon: '📐', label: 'API Design', color: '#818cf8',
    gradientFrom: 'rgba(129,140,248,0.12)', gradientTo: 'rgba(99,102,241,0.06)',
  },
  mule_review: {
    icon: '⚙️', label: 'Mule Review', color: '#34d399',
    gradientFrom: 'rgba(52,211,153,0.12)', gradientTo: 'rgba(16,185,129,0.06)',
  },
  munit: {
    icon: '🧪', label: 'MUnit Tests', color: '#60a5fa',
    gradientFrom: 'rgba(96,165,250,0.12)', gradientTo: 'rgba(59,130,246,0.06)',
  },
  security: {
    icon: '🔒', label: 'Security', color: '#f472b6',
    gradientFrom: 'rgba(244,114,182,0.12)', gradientTo: 'rgba(236,72,153,0.06)',
  },
  performance: {
    icon: '⚡', label: 'Performance', color: '#fbbf24',
    gradientFrom: 'rgba(251,191,36,0.12)', gradientTo: 'rgba(245,158,11,0.06)',
  },
  executive_reporting: {
    icon: '📊', label: 'Executive Report', color: '#a78bfa',
    gradientFrom: 'rgba(167,139,250,0.12)', gradientTo: 'rgba(139,92,246,0.06)',
  },
};

const SEV_CONFIG: Record<Severity, { color: string; bg: string; border: string; label: string }> = {
  info:     { color: '#94a3b8', bg: 'rgba(100,116,139,0.12)', border: 'rgba(100,116,139,0.25)', label: 'INFO' },
  low:      { color: '#4ade80', bg: 'rgba(34,197,94,0.1)',    border: 'rgba(34,197,94,0.25)',   label: 'LOW' },
  medium:   { color: '#fbbf24', bg: 'rgba(245,158,11,0.1)',   border: 'rgba(245,158,11,0.3)',   label: 'MEDIUM' },
  high:     { color: '#fb923c', bg: 'rgba(249,115,22,0.12)',  border: 'rgba(249,115,22,0.3)',   label: 'HIGH' },
  critical: { color: '#f87171', bg: 'rgba(239,68,68,0.14)',   border: 'rgba(239,68,68,0.35)',   label: 'CRITICAL' },
};

function scoreColor(v: number) {
  if (v >= 90) return '#22c55e';
  if (v >= 75) return '#f59e0b';
  return '#ef4444';
}

function ScoreBadge({ score, color }: { score: number; color: string }) {
  const r = 18;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  return (
    <div style={{ position: 'relative', width: 44, height: 44, flexShrink: 0 }}>
      <svg width={44} height={44} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={22} cy={22} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={5} />
        <circle
          cx={22} cy={22} r={r} fill="none" stroke={color} strokeWidth={5}
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={offset}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '0.75rem', fontWeight: 800, color,
      }}>
        {score}
      </div>
    </div>
  );
}

export function AgentCard({ report }: { report: AgentReport }) {
  const [open, setOpen] = useState(false);
  const meta = AGENT_META[report.agent] ?? { icon: '🤖', label: report.agent, color: '#94a3b8', gradientFrom: 'rgba(148,163,184,0.08)', gradientTo: 'rgba(100,116,139,0.04)' };
  const sc = scoreColor(report.score);
  const criticalCount = report.findings.filter(f => f.severity === 'critical').length;
  const highCount = report.findings.filter(f => f.severity === 'high').length;

  return (
    <div style={{
      background: open
        ? `linear-gradient(135deg, ${meta.gradientFrom}, ${meta.gradientTo})`
        : 'rgba(22,27,46,0.6)',
      border: `1px solid ${open ? meta.color + '35' : 'rgba(255,255,255,0.07)'}`,
      borderRadius: '14px',
      overflow: 'hidden',
      transition: 'all 0.25s ease',
      boxShadow: open ? `0 4px 24px rgba(0,0,0,0.3), 0 0 0 1px ${meta.color}20` : 'none',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', background: 'none', border: 'none', cursor: 'pointer',
          padding: '1rem 1.25rem',
          display: 'flex', alignItems: 'center', gap: '1rem',
          color: 'inherit', textAlign: 'left',
        }}
      >
        {/* Agent icon */}
        <div style={{
          width: '40px', height: '40px', borderRadius: '10px', flexShrink: 0,
          background: `${meta.color}15`,
          border: `1px solid ${meta.color}30`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.25rem',
        }}>
          {meta.icon}
        </div>

        {/* Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.9rem', fontWeight: 700, color: meta.color }}>{meta.label}</span>
            {criticalCount > 0 && (
              <span style={{ fontSize: '0.6rem', fontWeight: 700, color: '#f87171', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', padding: '0.1rem 0.4rem', borderRadius: '4px', letterSpacing: '0.06em' }}>
                {criticalCount} CRITICAL
              </span>
            )}
            {highCount > 0 && (
              <span style={{ fontSize: '0.6rem', fontWeight: 700, color: '#fb923c', background: 'rgba(249,115,22,0.12)', border: '1px solid rgba(249,115,22,0.25)', padding: '0.1rem 0.4rem', borderRadius: '4px', letterSpacing: '0.06em' }}>
                {highCount} HIGH
              </span>
            )}
          </div>
          <div style={{
            fontSize: '0.76rem', color: '#64748b', marginTop: '0.2rem',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '500px',
          }}>
            {report.summary}
          </div>
        </div>

        {/* Score ring + finding count + chevron */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem', flexShrink: 0 }}>
          {report.findings.length > 0 && (
            <span style={{
              fontSize: '0.7rem', color: '#64748b',
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.08)',
              padding: '0.2rem 0.5rem', borderRadius: '6px',
              whiteSpace: 'nowrap',
            }}>
              {report.findings.length} finding{report.findings.length !== 1 ? 's' : ''}
            </span>
          )}
          <ScoreBadge score={report.score} color={sc} />
          <svg
            width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#475569" strokeWidth="2"
            style={{ transition: 'transform 0.25s ease', transform: open ? 'rotate(180deg)' : 'rotate(0deg)', flexShrink: 0 }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </button>

      {/* Expanded content */}
      {open && (
        <div style={{ borderTop: `1px solid ${meta.color}20`, padding: '1.25rem 1.25rem 1.5rem' }}>
          {/* Summary paragraph */}
          <p style={{
            fontSize: '0.8125rem', color: '#94a3b8', lineHeight: 1.7,
            marginBottom: report.findings.length > 0 ? '1.25rem' : 0,
          }}>
            {report.summary}
          </p>

          {/* Findings */}
          {report.findings.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#475569', letterSpacing: '0.08em', marginBottom: '0.25rem' }}>
                FINDINGS ({report.findings.length})
              </div>
              {report.findings.map((f, i) => {
                const sev = SEV_CONFIG[f.severity] ?? SEV_CONFIG.info;
                return (
                  <div key={i} style={{
                    background: sev.bg,
                    border: `1px solid ${sev.border}`,
                    borderRadius: '10px',
                    padding: '0.75rem 1rem',
                    display: 'grid',
                    gridTemplateColumns: 'auto 1fr',
                    gap: '0.5rem 0.875rem',
                    alignItems: 'start',
                  }}>
                    <span style={{
                      display: 'inline-block',
                      fontSize: '0.62rem', fontWeight: 700, letterSpacing: '0.08em',
                      color: sev.color,
                      background: `${sev.color}20`,
                      border: `1px solid ${sev.color}40`,
                      padding: '0.2rem 0.5rem', borderRadius: '5px',
                      whiteSpace: 'nowrap', marginTop: '0.15rem',
                    }}>
                      {sev.label}
                    </span>
                    <div>
                      <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#e2e8f0', lineHeight: 1.4 }}>
                        {f.title}
                      </div>
                      {f.detail && (
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.3rem', lineHeight: 1.5 }}>
                          {f.detail}
                        </div>
                      )}
                      {f.recommendation && (
                        <div style={{
                          display: 'flex', alignItems: 'flex-start', gap: '0.35rem',
                          fontSize: '0.75rem', color: '#a78bfa', marginTop: '0.35rem', lineHeight: 1.5,
                        }}>
                          <span style={{ flexShrink: 0, marginTop: '0.05rem' }}>→</span>
                          <span>{f.recommendation}</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

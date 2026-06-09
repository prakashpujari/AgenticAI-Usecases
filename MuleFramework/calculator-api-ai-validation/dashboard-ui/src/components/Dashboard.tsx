import type { PipelineResponse } from '../types';
import { ScoreRing, scoreColor } from './ScoreRing';
import { RecommendationBadge } from './RecommendationBadge';
import { AgentCard } from './AgentCard';

interface Props {
  result: PipelineResponse;
  elapsed: number | null;
}

const AGENT_PIPELINE = [
  { key: 'api_design',          icon: '📐', label: 'API Design' },
  { key: 'mule_review',         icon: '⚙️', label: 'Mule Review' },
  { key: 'munit',               icon: '🧪', label: 'MUnit' },
  { key: 'security',            icon: '🔒', label: 'Security' },
  { key: 'performance',         icon: '⚡', label: 'Performance' },
  { key: 'executive_reporting', icon: '📊', label: 'Executive' },
];

export function Dashboard({ result, elapsed }: Props) {
  const { dashboard, agent_reports, executive_summary, artifacts } = result;

  const agentScoreMap: Record<string, number> = {};
  for (const r of agent_reports) {
    agentScoreMap[r.agent] = r.score;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .dash-section {
          animation: fadeSlideUp 0.4s ease forwards;
        }
      `}</style>

      {/* ── 1. Recommendation Banner (full width) ── */}
      <div className="dash-section" style={{ animationDelay: '0ms' }}>
        <RecommendationBadge recommendation={dashboard.recommendation} />
      </div>

      {/* ── 2. Executive Summary card ── */}
      <div className="dash-section" style={{
        animationDelay: '60ms',
        background: 'linear-gradient(135deg, #161b2e 0%, #12172a 100%)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '20px',
        padding: '1.75rem 2rem',
        boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', bottom: '-40px', right: '-40px',
          width: '160px', height: '160px', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(79,70,229,0.08) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <SectionTitle icon="📋">Executive Summary</SectionTitle>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            {elapsed !== null && (
              <span style={{
                fontSize: '0.7rem', color: '#475569',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.07)',
                padding: '0.25rem 0.65rem', borderRadius: '6px',
                display: 'flex', alignItems: 'center', gap: '0.3rem',
              }}>
                ⏱ {elapsed}s pipeline
              </span>
            )}
            <Tag label={dashboard.application} color="#7c3aed" />
            <Tag label={`Mule ${dashboard.runtime}`} color="#0891b2" />
            <Tag label={`${dashboard.testsExecuted} tests`} color="#059669" />
          </div>
        </div>
        <p style={{ fontSize: '0.875rem', color: '#94a3b8', lineHeight: 1.75, position: 'relative' }}>
          {executive_summary}
        </p>
      </div>

      {/* ── 3. Score Rings grid ── */}
      <div className="dash-section" style={{
        animationDelay: '120ms',
        background: 'linear-gradient(135deg, #161b2e 0%, #12172a 100%)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '20px',
        padding: '1.75rem 2rem',
        boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
      }}>
        <SectionTitle icon="📊">Quality Metrics</SectionTitle>
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: '1.5rem 2.5rem',
          justifyContent: 'space-around', marginTop: '1.5rem',
          alignItems: 'flex-start',
        }}>
          <ScoreRing value={dashboard.coverage}          label="Coverage"     sublabel="%" size={100} />
          <ScoreRing value={dashboard.passRate}          label="Pass Rate"    sublabel="%" size={100} />
          <ScoreRing value={dashboard.securityScore}     label="Security"                  size={100} />
          <ScoreRing value={dashboard.performanceScore}  label="Performance"               size={100} />
          <ScoreRing value={dashboard.confidenceScore}   label="Confidence"                size={100} />
          <ScoreRing value={dashboard.productionReadiness} label="Readiness"               size={100} />
          <ScoreRing
            value={dashboard.riskScore}
            label="Risk"
            size={100}
            color={dashboard.riskScore > 25 ? '#ef4444' : '#22c55e'}
          />
        </div>
      </div>

      {/* ── 4. Test Stats row ── */}
      <div className="dash-section" style={{ animationDelay: '180ms', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
        <StatTile
          label="Tests Executed"
          value={artifacts.munit_total}
          icon="🧪"
          accentColor="#60a5fa"
        />
        <StatTile
          label="Tests Passed"
          value={dashboard.testsPassed}
          icon="✅"
          accentColor="#4ade80"
          sub={`${dashboard.passRate}% pass rate`}
        />
        <StatTile
          label="Tests Failed"
          value={dashboard.testsFailed}
          icon="❌"
          accentColor={dashboard.testsFailed > 0 ? '#f87171' : '#4ade80'}
          sub={dashboard.testsFailed > 0 ? 'needs attention' : 'all passing'}
        />
        <StatTile
          label="Coverage"
          value={`${artifacts.munit_coverage}%`}
          icon="🎯"
          accentColor={artifacts.munit_coverage >= 80 ? '#4ade80' : artifacts.munit_coverage >= 60 ? '#fbbf24' : '#f87171'}
          sub="code coverage"
        />
      </div>

      {/* ── 5. Agent Pipeline bar ── */}
      <div className="dash-section" style={{
        animationDelay: '240ms',
        background: 'linear-gradient(135deg, #161b2e 0%, #12172a 100%)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '20px',
        padding: '1.75rem 2rem',
        boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
      }}>
        <SectionTitle icon="🔄">Agent Pipeline</SectionTitle>
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: '0.75rem',
          marginTop: '1.25rem', alignItems: 'center',
        }}>
          {AGENT_PIPELINE.map((ag, idx) => {
            const score = agentScoreMap[ag.key];
            const hasScore = score !== undefined;
            const color = hasScore ? scoreColor(score) : '#475569';
            return (
              <div key={ag.key} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  padding: '0.5rem 0.875rem', borderRadius: '999px',
                  background: hasScore ? `${color}12` : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${hasScore ? color + '35' : 'rgba(255,255,255,0.08)'}`,
                  boxShadow: hasScore ? `0 0 12px ${color}15` : 'none',
                  transition: 'all 0.2s',
                }}>
                  <span style={{ fontSize: '1rem' }}>{ag.icon}</span>
                  <span style={{ fontSize: '0.78rem', fontWeight: 600, color: hasScore ? color : '#475569' }}>
                    {ag.label}
                  </span>
                  {hasScore && (
                    <span style={{
                      fontSize: '0.72rem', fontWeight: 800, color,
                      background: `${color}20`, padding: '0.1rem 0.4rem',
                      borderRadius: '5px', marginLeft: '0.1rem',
                    }}>
                      {score}
                    </span>
                  )}
                </div>
                {idx < AGENT_PIPELINE.length - 1 && (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2d3748" strokeWidth="2.5">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── 6. Agent Cards accordion ── */}
      <div className="dash-section" style={{
        animationDelay: '300ms',
        background: 'linear-gradient(135deg, #161b2e 0%, #12172a 100%)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '20px',
        padding: '1.75rem 2rem',
        boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
      }}>
        <div style={{ marginBottom: '1.25rem' }}>
          <SectionTitle icon="🤖">Agent Reports</SectionTitle>
          <p style={{ fontSize: '0.78rem', color: '#475569', marginTop: '0.4rem', marginLeft: '1.75rem' }}>
            Click any agent card to expand findings and recommendations
          </p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
          {agent_reports.map((r) => (
            <AgentCard key={r.agent} report={r} />
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── Sub-components ─── */

function SectionTitle({ icon, children }: { icon: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
      <span style={{ fontSize: '1rem' }}>{icon}</span>
      <h3 style={{
        fontSize: '0.95rem', fontWeight: 700, color: '#e2e8f0', margin: 0,
        letterSpacing: '-0.01em',
      }}>
        {children}
      </h3>
    </div>
  );
}

function StatTile({ label, value, icon, accentColor, sub }: {
  label: string; value: string | number; icon: string;
  accentColor: string; sub?: string;
}) {
  return (
    <div style={{
      background: 'linear-gradient(135deg, #161b2e 0%, #12172a 100%)',
      border: `1px solid ${accentColor}22`,
      borderRadius: '16px',
      padding: '1.375rem 1.5rem',
      boxShadow: `0 4px 24px rgba(0,0,0,0.3), 0 0 0 1px ${accentColor}15`,
      position: 'relative', overflow: 'hidden',
    }}>
      {/* Accent top bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: '2px',
        background: `linear-gradient(90deg, ${accentColor}, transparent)`,
      }} />
      <div style={{ fontSize: '1.125rem', marginBottom: '0.5rem' }}>{icon}</div>
      <div style={{
        fontSize: '0.65rem', fontWeight: 700, color: '#475569',
        letterSpacing: '0.08em', marginBottom: '0.375rem',
      }}>
        {label.toUpperCase()}
      </div>
      <div style={{ fontSize: '2rem', fontWeight: 800, color: accentColor, lineHeight: 1, letterSpacing: '-0.02em' }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: '0.68rem', color: '#475569', marginTop: '0.3rem' }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function Tag({ label, color }: { label: string; color: string }) {
  return (
    <span style={{
      fontSize: '0.7rem', fontWeight: 600, padding: '0.25rem 0.65rem',
      borderRadius: '999px', background: `${color}18`, color,
      border: `1px solid ${color}35`,
    }}>
      {label}
    </span>
  );
}

import { useState, useEffect, useLayoutEffect } from 'react';
import { InputPanel } from './components/InputPanel';
import { Dashboard } from './components/Dashboard';
import { Header } from './components/Header';
import type { PipelineRequest, PipelineResponse } from './types';
import './index.css';

const DEFAULT_PATHS: PipelineRequest = {
  munit_reports_dir: '',
  raml_path: '',
  mule_xml_dir: '',
  application: 'calculator-api',
  runtime: '4.9',
};

const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_ENDPOINT    = API_BASE ? `${API_BASE}/validate` : '/api/validate';
const HEALTH_ENDPOINT = API_BASE ? `${API_BASE}/health`   : '/api/health';

declare global {
  interface Window {
    __injectMockResult?: (data: PipelineResponse) => void;
  }
}

function friendlyError(e: unknown, status?: number): string {
  if (status !== undefined && status >= 500) {
    return 'The validation service encountered an internal error. This usually means the provided paths or URLs are invalid or unreachable. Please check your inputs and try again.';
  }
  if (status !== undefined && status === 400) {
    return 'Invalid request — one of your inputs could not be resolved. Check that your GitHub URLs are correct and accessible.';
  }
  if (e instanceof TypeError && (e.message === 'Failed to fetch' || e.message.includes('fetch'))) {
    return 'Could not reach the validation service. It may be starting up (Render free tier takes ~30 seconds on first load). Please wait a moment and try again.';
  }
  if (e instanceof SyntaxError) {
    return 'The validation service returned an unexpected response. Please try again.';
  }
  return e instanceof Error ? e.message : 'An unexpected error occurred. Please try again.';
}

export default function App() {
  const [request, setRequest] = useState<PipelineRequest>(DEFAULT_PATHS);
  const [result, setResult] = useState<PipelineResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [showEmptyHint, setShowEmptyHint] = useState(false);
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try { return (localStorage.getItem('mvh-theme') as 'dark' | 'light') || 'dark'; }
    catch { return 'dark'; }
  });

  // Sync theme to <html> element synchronously before paint (no flash).
  useLayoutEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(t => {
      const next = t === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('mvh-theme', next); } catch { /* */ }
      return next;
    });
  };

  // Keep-alive ping every 10 min to prevent Render free-tier sleep.
  useEffect(() => {
    const ping = () => fetch(HEALTH_ENDPOINT, { method: 'GET' }).catch(() => {});
    ping();
    const id = setInterval(ping, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  if (typeof window !== 'undefined') {
    window.__injectMockResult = (data: PipelineResponse) => {
      setResult(data);
      setLoading(false);
      setError(null);
      setElapsed(12);
    };
  }

  const hasAnyInput = !!(
    request.munit_reports_dir?.trim() ||
    request.raml_path?.trim() ||
    request.mule_xml_dir?.trim()
  );

  async function runValidation(forceDemoMode = false) {
    if (!hasAnyInput && !forceDemoMode) {
      setShowEmptyHint(true);
      return;
    }
    setShowEmptyHint(false);
    setLoading(true);
    setError(null);
    setResult(null);
    setElapsed(null);
    const start = Date.now();
    try {
      const res = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(request),
      });
      let data: Record<string, unknown> = {};
      try { data = await res.json(); } catch { /* non-JSON body */ }
      if (!res.ok) {
        const detail = data?.detail;
        setError(
          detail
            ? (typeof detail === 'string' ? detail : JSON.stringify(detail))
            : friendlyError(null, res.status)
        );
      } else {
        setResult(data as unknown as PipelineResponse);
        setElapsed(Math.round((Date.now() - start) / 1000));
      }
    } catch (e: unknown) {
      setError(friendlyError(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg-base)',
      color: 'var(--text-primary)',
      fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
      position: 'relative',
    }}>
      {/* ── Ambient background orbs ── */}
      <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0, overflow: 'hidden' }}>
        <div style={{
          position: 'absolute', top: '-15%', left: '-8%',
          width: '650px', height: '650px', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(124,58,237,0.09) 0%, transparent 70%)',
          animation: 'floatUpDown 9s ease-in-out infinite',
        }} />
        <div style={{
          position: 'absolute', top: '30%', right: '-12%',
          width: '550px', height: '550px', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(8,145,178,0.07) 0%, transparent 70%)',
          animation: 'floatUpDown 11s ease-in-out 2.5s infinite',
        }} />
        <div style={{
          position: 'absolute', bottom: '-10%', left: '28%',
          width: '700px', height: '700px', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(79,70,229,0.06) 0%, transparent 70%)',
          animation: 'floatUpDown 13s ease-in-out 5s infinite',
        }} />
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: 'radial-gradient(rgba(139,92,246,0.06) 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }} />
      </div>

      {/* ── Main content ── */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        <Header application={request.application} runtime={request.runtime} theme={theme} onToggleTheme={toggleTheme} />

        <main style={{
          maxWidth: '1440px', margin: '0 auto',
          padding: '2rem 1.5rem',
          display: 'flex', flexDirection: 'column', gap: '1.75rem',
        }}>
          <InputPanel request={request} onChange={r => { setRequest(r); setShowEmptyHint(false); }} onRun={runValidation} loading={loading} />

          {showEmptyHint && !loading && (
            <div style={{
              borderRadius: '16px',
              border: '1px solid rgba(6,182,212,0.35)',
              background: 'linear-gradient(135deg, rgba(8,145,178,0.1), rgba(6,182,212,0.06))',
              padding: '1.25rem 1.5rem',
              display: 'flex', alignItems: 'flex-start', gap: '1rem',
              boxShadow: '0 0 24px rgba(8,145,178,0.1)',
            }}>
              <span style={{ fontSize: '1.3rem', flexShrink: 0 }}>💡</span>
              <div style={{ flex: 1 }}>
                <strong style={{ display: 'block', marginBottom: '0.4rem', color: '#a5f3fc', fontSize: '0.9rem' }}>
                  No inputs provided
                </strong>
                <p style={{ color: '#67e8f9', fontSize: '0.82rem', lineHeight: 1.65, margin: '0 0 0.875rem' }}>
                  Enter your GitHub URLs or local folder paths above, then click{' '}
                  <em>Run Validation Pipeline</em>. Or click the button below to instantly run
                  a validation against the bundled <strong>calculator-api</strong> demo project.
                </p>
                <button
                  onClick={() => runValidation(true)}
                  style={{
                    padding: '0.5rem 1.25rem', borderRadius: '8px', border: 'none',
                    background: 'linear-gradient(135deg, rgba(8,145,178,0.5), rgba(6,182,212,0.35))',
                    color: '#a5f3fc', fontWeight: 700, fontSize: '0.8rem',
                    cursor: 'pointer', letterSpacing: '0.02em',
                    boxShadow: '0 0 12px rgba(8,145,178,0.3)',
                    fontFamily: 'Inter, system-ui, sans-serif',
                  }}
                >
                  Run with Demo Data
                </button>
              </div>
            </div>
          )}

          {error && (
            <div style={{
              borderRadius: '16px',
              border: '1px solid rgba(239,68,68,0.4)',
              background: 'linear-gradient(135deg, rgba(239,68,68,0.12), rgba(220,38,38,0.07))',
              padding: '1.125rem 1.5rem',
              color: '#fca5a5',
              fontSize: '0.875rem',
              display: 'flex', alignItems: 'flex-start', gap: '0.875rem',
              boxShadow: '0 0 32px rgba(239,68,68,0.12), inset 0 1px 0 rgba(255,255,255,0.04)',
            }}>
              <span style={{ fontSize: '1.2rem', flexShrink: 0, marginTop: '0.05rem' }}>⚠️</span>
              <div>
                <strong style={{ display: 'block', marginBottom: '0.35rem', color: '#f87171', fontSize: '0.9rem' }}>
                  Something went wrong
                </strong>
                <span style={{ color: '#fca5a5', lineHeight: 1.6 }}>{error}</span>
              </div>
            </div>
          )}

          {loading && <LoadingState />}
          {result && !loading && <Dashboard result={result} elapsed={elapsed} />}
        </main>

        {/* ── Footer ── */}
        <footer style={{
          borderTop: '1px solid var(--footer-border)',
          padding: '1.25rem 2rem',
          textAlign: 'center',
          color: 'var(--footer-text)',
          fontSize: '0.72rem',
          letterSpacing: '0.04em',
        }}>
          mule-validation-hub · LangGraph + Groq LLM · 6-Agent Pipeline
        </footer>
      </div>
    </div>
  );
}

const AGENT_STEPS = [
  { icon: '📂', label: 'Loading MUnit reports' },
  { icon: '📐', label: 'API Design review' },
  { icon: '⚙️', label: 'Mule XML analysis' },
  { icon: '🧪', label: 'Test coverage check' },
  { icon: '🔒', label: 'Security audit' },
  { icon: '⚡', label: 'Performance analysis' },
  { icon: '📊', label: 'Executive reporting' },
];

function LoadingState() {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '4rem 2rem', gap: '2rem',
      background: 'var(--bg-loading-card)',
      borderRadius: '24px',
      border: '1px solid var(--border-panel)',
      boxShadow: 'var(--shadow-panel)',
    }}>
      {/* Spinning rings */}
      <div style={{ position: 'relative', width: '80px', height: '80px' }}>
        <div style={{
          position: 'absolute', inset: 0, borderRadius: '50%',
          border: '3px solid rgba(139,92,246,0.12)',
        }} />
        <div style={{
          position: 'absolute', inset: 0, borderRadius: '50%',
          border: '3px solid transparent',
          borderTopColor: '#7c3aed', borderRightColor: '#4f46e5',
          animation: 'spin 1s linear infinite',
        }} />
        <div style={{
          position: 'absolute', inset: '12px', borderRadius: '50%',
          border: '2px solid transparent',
          borderTopColor: '#06b6d4',
          animation: 'spinRev 0.7s linear infinite',
        }} />
        <div style={{
          position: 'absolute', inset: '24px', borderRadius: '50%',
          border: '2px solid transparent',
          borderTopColor: '#a78bfa',
          animation: 'spin 1.3s linear infinite',
        }} />
        <div style={{
          position: 'absolute', inset: 0, display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: '1.5rem',
        }}>
          🤖
        </div>
      </div>

      <div style={{ textAlign: 'center' }}>
        <p style={{
          fontWeight: 700, fontSize: '1.15rem', margin: 0, marginBottom: '0.45rem',
          background: 'linear-gradient(135deg, #f1f5f9, #a78bfa, #67e8f9)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          backgroundClip: 'text', backgroundSize: '200% auto',
          animation: 'shimmerText 2.5s linear infinite',
        }}>
          Running AI validation pipeline…
        </p>
        <p style={{ color: 'var(--text-dim)', fontSize: '0.825rem', margin: 0 }}>
          6 specialized agents are analyzing your MuleSoft API
        </p>
      </div>

      {/* Steps list */}
      <div style={{
        display: 'flex', flexDirection: 'column', gap: '0.5rem',
        width: '100%', maxWidth: '400px',
      }}>
        {AGENT_STEPS.map((step, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: '0.75rem',
            padding: '0.55rem 0.875rem', borderRadius: '10px',
            background: 'var(--bg-loading-step)',
            border: '1px solid var(--border-subtle)',
            animation: `pulse 2s ease-in-out ${i * 0.2}s infinite`,
          }}>
            <span style={{ fontSize: '0.95rem' }}>{step.icon}</span>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', flex: 1 }}>{step.label}</span>
            <div style={{
              width: '6px', height: '6px', borderRadius: '50%',
              background: 'linear-gradient(135deg, #7c3aed, #06b6d4)',
              animation: `pulse 1.5s ease-in-out ${i * 0.25}s infinite`,
              boxShadow: '0 0 6px rgba(124,58,237,0.6)',
            }} />
          </div>
        ))}
      </div>
    </div>
  );
}

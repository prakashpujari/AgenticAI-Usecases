import { useState } from 'react';
import { InputPanel } from './components/InputPanel';
import { Dashboard } from './components/Dashboard';
import { Header } from './components/Header';
import type { PipelineRequest, PipelineResponse } from './types';
import './index.css';

const DEFAULT_PATHS: PipelineRequest = {
  munit_reports_dir:
    'C:/pp/GitHub/AgenticAI-Usecases/MuleFramework/calculator-api-ai-validation/ai-validation-service/sample_reports',
  raml_path:
    'C:/pp/GitHub/AgenticAI-Usecases/MuleFramework/calculator-api-ai-validation/mule-app/src/main/resources/api/calculator-api.raml',
  mule_xml_dir:
    'C:/pp/GitHub/AgenticAI-Usecases/MuleFramework/calculator-api-ai-validation/mule-app/src/main/mule',
  application: 'calculator-api',
  runtime: '4.9',
};

declare global {
  interface Window {
    __injectMockResult?: (data: PipelineResponse) => void;
  }
}

export default function App() {
  const [request, setRequest] = useState<PipelineRequest>(DEFAULT_PATHS);
  const [result, setResult] = useState<PipelineResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);

  // Allow Puppeteer/tests to inject mock results
  if (typeof window !== 'undefined') {
    window.__injectMockResult = (data: PipelineResponse) => {
      setResult(data);
      setLoading(false);
      setError(null);
      setElapsed(12);
    };
  }

  async function runValidation() {
    setLoading(true);
    setError(null);
    setResult(null);
    setElapsed(null);
    const start = Date.now();
    try {
      const res = await fetch('/api/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(request),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail ? JSON.stringify(data.detail) : `Server error ${res.status}`);
      } else {
        setResult(data as PipelineResponse);
        setElapsed(Math.round((Date.now() - start) / 1000));
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Network error — is the backend running on :8000?');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0f1117',
      color: '#e2e8f0',
      fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
    }}>
      <Header application={request.application} runtime={request.runtime} />

      <main style={{
        maxWidth: '1440px', margin: '0 auto',
        padding: '2rem 1.5rem',
        display: 'flex', flexDirection: 'column', gap: '1.75rem',
      }}>
        <InputPanel request={request} onChange={setRequest} onRun={runValidation} loading={loading} />

        {error && (
          <div style={{
            borderRadius: '14px',
            border: '1px solid rgba(239,68,68,0.35)',
            background: 'linear-gradient(135deg, rgba(239,68,68,0.1), rgba(220,38,38,0.06))',
            padding: '1rem 1.5rem',
            color: '#fca5a5',
            fontSize: '0.875rem',
            display: 'flex', alignItems: 'flex-start', gap: '0.75rem',
            boxShadow: '0 0 24px rgba(239,68,68,0.1)',
          }}>
            <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>⚠️</span>
            <div>
              <strong style={{ display: 'block', marginBottom: '0.25rem', color: '#f87171' }}>Validation Error</strong>
              {error}
            </div>
          </div>
        )}

        {loading && <LoadingState />}
        {result && !loading && <Dashboard result={result} elapsed={elapsed} />}
      </main>
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
    }}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity:0.4; } 50% { opacity:1; } }
        @keyframes shimmer {
          0% { background-position: -200% center; }
          100% { background-position: 200% center; }
        }
      `}</style>

      {/* Spinning ring */}
      <div style={{ position: 'relative', width: '72px', height: '72px' }}>
        <div style={{
          position: 'absolute', inset: 0, borderRadius: '50%',
          border: '3px solid rgba(139,92,246,0.15)',
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
          animation: 'spin 0.7s linear infinite reverse',
        }} />
        <div style={{
          position: 'absolute', inset: 0, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          fontSize: '1.5rem',
        }}>
          🤖
        </div>
      </div>

      <div style={{ textAlign: 'center' }}>
        <p style={{
          color: '#f1f5f9', fontWeight: 700, fontSize: '1.1rem',
          margin: 0, marginBottom: '0.4rem',
          background: 'linear-gradient(135deg, #f1f5f9, #a78bfa, #67e8f9)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          backgroundSize: '200% auto',
          animation: 'shimmer 2.5s linear infinite',
        }}>
          Running AI validation pipeline…
        </p>
        <p style={{ color: '#475569', fontSize: '0.825rem', margin: 0 }}>
          6 agents analyzing your MuleSoft API
        </p>
      </div>

      {/* Steps list */}
      <div style={{
        display: 'flex', flexDirection: 'column', gap: '0.5rem',
        width: '100%', maxWidth: '380px',
      }}>
        {AGENT_STEPS.map((step, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: '0.75rem',
            padding: '0.5rem 0.875rem', borderRadius: '10px',
            background: 'rgba(22,27,46,0.5)',
            border: '1px solid rgba(255,255,255,0.06)',
            animation: `pulse 2s ease-in-out ${i * 0.2}s infinite`,
          }}>
            <span style={{ fontSize: '0.9rem' }}>{step.icon}</span>
            <span style={{ fontSize: '0.78rem', color: '#64748b' }}>{step.label}</span>
            <div style={{
              marginLeft: 'auto', width: '6px', height: '6px', borderRadius: '50%',
              background: '#7c3aed',
              animation: `pulse 1.5s ease-in-out ${i * 0.25}s infinite`,
            }} />
          </div>
        ))}
      </div>
    </div>
  );
}

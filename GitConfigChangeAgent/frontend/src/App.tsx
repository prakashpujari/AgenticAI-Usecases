import { useEffect, useState } from 'react';
import './App.css';

interface Run {
  run_id: string;
  config_type: string;
  mode: string;
  status: string;
  projects_scanned: number;
  files_scanned: number;
  files_matched: number;
  files_changed: number;
  risk_score: number;
  created_at: string;
}

function App() {
  const [health, setHealth] = useState<string>('loading');
  const [token, setToken] = useState<string>('');
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'runs' | 'create'>('overview');
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');

  const [formData, setFormData] = useState({
    config_type: 'yaml',
    old_value: '',
    new_value: '',
    key_path: '',
    scope: { group_ids: [], project_ids: [] },
    mode: 'dry-run',
    branch_strategy: 'feature-per-project',
    open_merge_requests: false,
    description: '',
  });
  const [estimate, setEstimate] = useState<{ query: string; projects_scanned: number; files_matched: number; details: { project_id: number; name?: string; files_matched: number }[] } | null>(null);

  useEffect(() => {
    const initAuth = async () => {
      try {
        const r = await fetch('/dev/auth/token', { method: 'POST' });
        const data = await r.json();
        setToken(data.access_token);
      } catch (e) {
        console.error('Failed to get auth token:', e);
      }
      fetchHealth();
    };
    initAuth();
  }, []);

  const authHeaders = () => ({
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  });

  const fetchHealth = async () => {
    try {
      const r = await fetch('/api/v1/healthz');
      const data = await r.json();
      setHealth(data.status ?? 'unknown');
    } catch {
      setHealth('failed');
    }
  };

  const fetchRuns = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const r = await fetch('/api/v1/runs', {
        headers: authHeaders(),
      });
      if (r.ok) {
        const data = await r.json();
        setRuns(data);
      } else {
        setRuns([]);
      }
    } catch {
      setRuns([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setFormError('Authentication token not available');
      return;
    }
    setFormError('');
    setFormSuccess('');

    try {
      const payload = {
        ...formData,
        scope: {
          group_ids: formData.scope.group_ids.length > 0 
            ? formData.scope.group_ids.map(Number).filter(Boolean)
            : [],
          project_ids: formData.scope.project_ids.length > 0
            ? formData.scope.project_ids.map(Number).filter(Boolean)
            : [],
        },
      };

      const r = await fetch('/api/v1/runs', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });

      if (r.ok) {
        setFormSuccess('Run created successfully!');
        setFormData({
          config_type: 'yaml',
          old_value: '',
          new_value: '',
          key_path: '',
          scope: { group_ids: [], project_ids: [] },
          mode: 'dry-run',
          branch_strategy: 'feature-per-project',
          open_merge_requests: false,
          description: '',
        });
        setTimeout(() => {
          setActiveTab('runs');
          fetchRuns();
        }, 1500);
      } else {
        const error = await r.json();
        setFormError(`Error: ${error.detail || 'Failed to create run'}`);
      }
    } catch (e) {
      setFormError(`Error: ${e instanceof Error ? e.message : 'Unknown error'}`);
    }
  };

  const handleEstimate = async () => {
    if (!token) {
      setFormError('Authentication token not available');
      return;
    }
    setFormError('');
    setFormSuccess('');
    const query = formData.key_path || formData.old_value || formData.new_value || '';
    if (!query) {
      setFormError('Provide a search keyword (Key Path or value) to estimate impact');
      return;
    }

    try {
      const payload = { query, scope: formData.scope };
      const r = await fetch('/api/v1/estimate', { method: 'POST', headers: authHeaders(), body: JSON.stringify(payload) });
      if (r.ok) {
        const data = await r.json();
        setEstimate(data);
      } else {
        const err = await r.text();
        setFormError(`Estimate failed: ${err}`);
      }
    } catch (e) {
      setFormError(`Estimate error: ${e instanceof Error ? e.message : 'Unknown error'}`);
    }
  };

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 0, margin: 0 }}>
      {/* Header */}
      <header style={{ background: '#0066cc', color: 'white', padding: '1.5rem 2rem' }}>
        <h1 style={{ margin: 0 }}>GitConfigChangeAgent</h1>
        <p style={{ margin: '0.5rem 0 0 0', opacity: 0.9 }}>Backend health: <strong>{health}</strong></p>
      </header>

      {/* Navigation Tabs */}
      <nav style={{ background: '#f5f5f5', borderBottom: '1px solid #ddd', padding: '0 2rem' }}>
        <div style={{ display: 'flex', gap: '2rem' }}>
          {(['overview', 'runs', 'create'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                if (tab === 'runs') fetchRuns();
              }}
              style={{
                background: activeTab === tab ? '#0066cc' : 'transparent',
                color: activeTab === tab ? 'white' : '#333',
                border: 'none',
                padding: '1rem 0',
                cursor: 'pointer',
                fontSize: '1rem',
                borderBottom: activeTab === tab ? '3px solid #0066cc' : 'none',
              }}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>
      </nav>

      {/* Main Content */}
      <main style={{ padding: '2rem' }}>
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <section>
            <h2>Overview</h2>
            <p>Welcome to GitConfigChangeAgent. This tool allows you to manage configuration changes across GitLab projects.</p>
            <div style={{ background: '#f9f9f9', padding: '1rem', borderRadius: '4px', marginTop: '1rem' }}>
              <h3>Features:</h3>
              <ul>
                <li>Create configuration change runs (dry-run or apply)</li>
                <li>Support for YAML, properties, and constants config files</li>
                <li>Automatic project and file scanning</li>
                <li>Risk assessment for changes</li>
                <li>View run history and details</li>
              </ul>
            </div>
          </section>
        )}

        {/* Runs Tab */}
        {activeTab === 'runs' && (
          <section>
            <h2>Configuration Change Runs</h2>
            {loading && <p>Loading runs...</p>}
            {!loading && runs.length === 0 && <p>No runs found. Create one to get started.</p>}
            {runs.length > 0 && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: '#f5f5f5', borderBottom: '2px solid #ddd' }}>
                      <th style={{ padding: '1rem', textAlign: 'left' }}>Run ID</th>
                      <th style={{ padding: '1rem', textAlign: 'left' }}>Type</th>
                      <th style={{ padding: '1rem', textAlign: 'left' }}>Mode</th>
                      <th style={{ padding: '1rem', textAlign: 'left' }}>Status</th>
                      <th style={{ padding: '1rem', textAlign: 'left' }}>Files</th>
                      <th style={{ padding: '1rem', textAlign: 'left' }}>Risk</th>
                      <th style={{ padding: '1rem', textAlign: 'left' }}>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr key={run.run_id} style={{ borderBottom: '1px solid #eee' }}>
                        <td style={{ padding: '1rem' }}>{run.run_id}</td>
                        <td style={{ padding: '1rem' }}>{run.config_type}</td>
                        <td style={{ padding: '1rem' }}>{run.mode}</td>
                        <td style={{ padding: '1rem' }}>{run.status}</td>
                        <td style={{ padding: '1rem' }}>{run.files_changed}/{run.files_matched}</td>
                        <td style={{ padding: '1rem' }}>{run.risk_score.toFixed(2)}</td>
                        <td style={{ padding: '1rem' }}>{new Date(run.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* Create Run Tab */}
        {activeTab === 'create' && (
          <section>
            <h2>Create Configuration Change</h2>
            <form onSubmit={handleCreateRun} style={{ maxWidth: '600px' }}>
              {formError && (
                <div style={{ background: '#fee', color: '#c00', padding: '1rem', borderRadius: '4px', marginBottom: '1rem' }}>
                  {formError}
                </div>
              )}
              {formSuccess && (
                <div style={{ background: '#efe', color: '#060', padding: '1rem', borderRadius: '4px', marginBottom: '1rem' }}>
                  {formSuccess}
                </div>
              )}

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>
                  Config Type: <span style={{ color: 'red' }}>*</span>
                </label>
                <select
                  value={formData.config_type}
                  onChange={(e) => setFormData({ ...formData, config_type: e.target.value })}
                  style={{ width: '100%', padding: '0.5rem' }}
                  required
                >
                  <option value="yaml">YAML</option>
                  <option value="properties">Properties</option>
                  <option value="constants">Constants</option>
                </select>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>
                  Key Path:
                </label>
                <input
                  type="text"
                  value={formData.key_path}
                  onChange={(e) => setFormData({ ...formData, key_path: e.target.value })}
                  placeholder="e.g., database.host"
                  style={{ width: '100%', padding: '0.5rem', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>
                  Old Value: <span style={{ color: 'red' }}>*</span>
                </label>
                <textarea
                  value={formData.old_value}
                  onChange={(e) => setFormData({ ...formData, old_value: e.target.value })}
                  placeholder="Current value"
                  rows={3}
                  style={{ width: '100%', padding: '0.5rem', boxSizing: 'border-box' }}
                  required
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>
                  New Value: <span style={{ color: 'red' }}>*</span>
                </label>
                <textarea
                  value={formData.new_value}
                  onChange={(e) => setFormData({ ...formData, new_value: e.target.value })}
                  placeholder="New value"
                  rows={3}
                  style={{ width: '100%', padding: '0.5rem', boxSizing: 'border-box' }}
                  required
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>
                  Mode: <span style={{ color: 'red' }}>*</span>
                </label>
                <select
                  value={formData.mode}
                  onChange={(e) => setFormData({ ...formData, mode: e.target.value })}
                  style={{ width: '100%', padding: '0.5rem' }}
                  required
                >
                  <option value="dry-run">Dry Run</option>
                  <option value="apply">Apply</option>
                </select>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>
                  Branch Strategy:
                </label>
                <input
                  type="text"
                  value={formData.branch_strategy}
                  onChange={(e) => setFormData({ ...formData, branch_strategy: e.target.value })}
                  placeholder="e.g., feature-per-project"
                  style={{ width: '100%', padding: '0.5rem', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label>
                  <input
                    type="checkbox"
                    checked={formData.open_merge_requests}
                    onChange={(e) => setFormData({ ...formData, open_merge_requests: e.target.checked })}
                  />
                  Open Merge Requests
                </label>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '0.5rem' }}>
                  Description:
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Describe the purpose of this change"
                  rows={2}
                  style={{ width: '100%', padding: '0.5rem', boxSizing: 'border-box' }}
                />
              </div>

              <button
                type="submit"
                style={{
                  background: '#0066cc',
                  color: 'white',
                  padding: '0.75rem 1.5rem',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '1rem',
                }}
              >
                Create Run
              </button>
              <button
                type="button"
                onClick={handleEstimate}
                style={{
                  marginLeft: '1rem',
                  background: '#f0ad4e',
                  color: 'white',
                  padding: '0.75rem 1rem',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.95rem',
                }}
              >
                Estimate Impact
              </button>
              {estimate && (
                <div style={{ marginTop: '1rem', background: '#eef6ff', padding: '1rem', borderRadius: '4px' }}>
                  <strong>Estimate:</strong> {estimate.files_matched} files across {estimate.projects_scanned} projects match "{estimate.query}"
                  <div style={{ marginTop: '0.5rem' }}>
                    {estimate.details.slice(0,5).map(d => (
                      <div key={d.project_id}>Project {d.project_id}: {d.files_matched} files</div>
                    ))}
                    {estimate.details.length > 5 && <div>...and {estimate.details.length - 5} more projects</div>}
                  </div>
                </div>
              )}
            </form>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;

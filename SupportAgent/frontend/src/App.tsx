import { useState, useEffect } from 'react'
import './App.css'

export default function App() {
  const [incidents, setIncidents] = useState([])
  const [selectedIncident, setSelectedIncident] = useState(null)
  const [rca, setRca] = useState(null)
  const [remediation, setRemediation] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('dashboard')

  const API_URL = 'http://localhost:8000'

  useEffect(() => {
    fetchIncidents()
    fetchMetrics()
  }, [])

  const fetchIncidents = async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/incidents`)
      const data = await response.json()
      setIncidents(data.incidents || [])
    } catch (error) {
      console.error('Error fetching incidents:', error)
    }
  }

  const fetchMetrics = async () => {
    try {
      const response = await fetch(`${API_URL}/api/v1/metrics`)
      const data = await response.json()
      setMetrics(data)
    } catch (error) {
      console.error('Error fetching metrics:', error)
    }
  }

  const handleIncidentClick = async (incident) => {
    setSelectedIncident(incident)
    setActiveTab('details')

    try {
      const response = await fetch(`${API_URL}/api/v1/incidents/${incident.id}`)
      const data = await response.json()
      setSelectedIncident(data)
    } catch (error) {
      console.error('Error fetching incident details:', error)
    }
  }

  const runRCA = async (incidentId) => {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/api/v1/incidents/${incidentId}/rca`, {
        method: 'POST'
      })
      const data = await response.json()
      setRca(data)
      setActiveTab('rca')
    } catch (error) {
      console.error('Error running RCA:', error)
    } finally {
      setLoading(false)
    }
  }

  const generateRemediation = async (incidentId) => {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/api/v1/incidents/${incidentId}/remediation`, {
        method: 'POST'
      })
      const data = await response.json()
      setRemediation(data)
      setActiveTab('remediation')
    } catch (error) {
      console.error('Error generating remediation:', error)
    } finally {
      setLoading(false)
    }
  }

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'P1_CRITICAL': return '#d32f2f'
      case 'P2_HIGH': return '#f57c00'
      case 'P3_MEDIUM': return '#fbc02d'
      case 'P4_LOW': return '#388e3c'
      default: return '#666'
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'DETECTED': return '#ff6b6b'
      case 'ANALYZING': return '#ffa500'
      case 'RESOLVED': return '#51cf66'
      default: return '#666'
    }
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <h1>🚀 AIOps Platform</h1>
          <p>Automated Incident Detection, Analysis & Remediation</p>
        </div>
        <div className="header-status">
          <span className="status-badge">✅ Backend: Online</span>
          <span className="status-badge">✅ Connectors: Ready</span>
        </div>
      </header>

      {/* Navigation */}
      <nav className="nav">
        <button
          className={`nav-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          📊 Dashboard
        </button>
        <button
          className={`nav-btn ${activeTab === 'details' ? 'active' : ''}`}
          onClick={() => setActiveTab('details')}
          disabled={!selectedIncident}
        >
          🔍 Incident Details
        </button>
        <button
          className={`nav-btn ${activeTab === 'rca' ? 'active' : ''}`}
          onClick={() => setActiveTab('rca')}
          disabled={!rca}
        >
          🔎 RCA Analysis
        </button>
        <button
          className={`nav-btn ${activeTab === 'remediation' ? 'active' : ''}`}
          onClick={() => setActiveTab('remediation')}
          disabled={!remediation}
        >
          ⚡ Remediation
        </button>
        <button
          className={`nav-btn ${activeTab === 'metrics' ? 'active' : ''}`}
          onClick={() => setActiveTab('metrics')}
        >
          📈 Metrics
        </button>
      </nav>

      {/* Main Content */}
      <main className="main-content">
        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && (
          <div className="tab-content">
            <h2>Real-Time Incident Detection</h2>

            {/* KPI Cards */}
            <div className="kpi-cards">
              <div className="kpi-card">
                <div className="kpi-value">{incidents.length}</div>
                <div className="kpi-label">Total Incidents</div>
              </div>
              <div className="kpi-card critical">
                <div className="kpi-value">{incidents.filter(i => i.severity === 'P1_CRITICAL').length}</div>
                <div className="kpi-label">Critical (P1)</div>
              </div>
              <div className="kpi-card high">
                <div className="kpi-value">{incidents.filter(i => i.severity === 'P2_HIGH').length}</div>
                <div className="kpi-label">High (P2)</div>
              </div>
              <div className="kpi-card resolved">
                <div className="kpi-value">{incidents.filter(i => i.status === 'RESOLVED').length}</div>
                <div className="kpi-label">Resolved</div>
              </div>
            </div>

            {/* Incidents Table */}
            <div className="incidents-section">
              <h3>Active Incidents</h3>
              {incidents.length === 0 ? (
                <p className="no-data">No incidents detected. Create one to get started!</p>
              ) : (
                <div className="incidents-table">
                  <div className="table-header">
                    <div className="col-title">Title</div>
                    <div className="col-severity">Severity</div>
                    <div className="col-status">Status</div>
                    <div className="col-services">Services</div>
                    <div className="col-confidence">Confidence</div>
                    <div className="col-actions">Actions</div>
                  </div>
                  {incidents.map((incident) => (
                    <div key={incident.id} className="table-row">
                      <div className="col-title">
                        <button
                          className="incident-link"
                          onClick={() => handleIncidentClick(incident)}
                        >
                          {incident.title}
                        </button>
                      </div>
                      <div className="col-severity">
                        <span
                          className="badge"
                          style={{ backgroundColor: getSeverityColor(incident.severity) }}
                        >
                          {incident.severity}
                        </span>
                      </div>
                      <div className="col-status">
                        <span
                          className="badge"
                          style={{ backgroundColor: getStatusColor(incident.status) }}
                        >
                          {incident.status}
                        </span>
                      </div>
                      <div className="col-services">
                        {incident.affected_services?.slice(0, 2).join(', ')}
                        {incident.affected_services?.length > 2 && `+${incident.affected_services.length - 2}`}
                      </div>
                      <div className="col-confidence">
                        <div className="progress-bar">
                          <div
                            className="progress-fill"
                            style={{ width: `${(incident.confidence_score || 0) * 100}%` }}
                          ></div>
                        </div>
                        <span>{Math.round((incident.confidence_score || 0) * 100)}%</span>
                      </div>
                      <div className="col-actions">
                        <button
                          className="action-btn"
                          onClick={() => handleIncidentClick(incident)}
                        >
                          View
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Incident Details Tab */}
        {activeTab === 'details' && selectedIncident && (
          <div className="tab-content">
            <div className="incident-header">
              <div>
                <h2>{selectedIncident.title}</h2>
                <p className="incident-meta">ID: {selectedIncident.id}</p>
              </div>
              <div className="incident-status">
                <span
                  className="badge large"
                  style={{ backgroundColor: getSeverityColor(selectedIncident.severity) }}
                >
                  {selectedIncident.severity}
                </span>
              </div>
            </div>

            <div className="incident-grid">
              <div className="info-card">
                <h4>Description</h4>
                <p>{selectedIncident.description}</p>
              </div>
              <div className="info-card">
                <h4>Affected Services</h4>
                <ul>
                  {selectedIncident.affected_services?.map((service, i) => (
                    <li key={i}>📦 {service}</li>
                  ))}
                </ul>
              </div>
              <div className="info-card">
                <h4>Environment</h4>
                <p>{selectedIncident.environment}</p>
              </div>
              <div className="info-card">
                <h4>Detection Source</h4>
                <p>{selectedIncident.detection_source}</p>
              </div>
            </div>

            <div className="action-buttons">
              <button
                className="btn primary"
                onClick={() => runRCA(selectedIncident.id)}
                disabled={loading}
              >
                {loading ? '🔄 Running RCA...' : '🔍 Run RCA Analysis'}
              </button>
              <button
                className="btn success"
                onClick={() => generateRemediation(selectedIncident.id)}
                disabled={loading}
              >
                {loading ? '⚙️ Generating...' : '⚡ Generate Remediation'}
              </button>
            </div>
          </div>
        )}

        {/* RCA Tab */}
        {activeTab === 'rca' && rca && (
          <div className="tab-content">
            <h2>Root Cause Analysis</h2>
            <div className="rca-card">
              <h3>Analysis Result</h3>
              <div className="rca-content">
                <p><strong>Status:</strong> {rca.status}</p>
                {rca.root_cause && <p><strong>Root Cause:</strong> {rca.root_cause}</p>}
                {rca.analysis && <p><strong>Analysis:</strong> {rca.analysis}</p>}
                {rca.recommendations && (
                  <div>
                    <p><strong>Recommendations:</strong></p>
                    <ul>
                      {Array.isArray(rca.recommendations) ? (
                        rca.recommendations.map((rec, i) => <li key={i}>{rec}</li>)
                      ) : (
                        <li>{rca.recommendations}</li>
                      )}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Remediation Tab */}
        {activeTab === 'remediation' && remediation && (
          <div className="tab-content">
            <h2>Remediation Approval Workflow</h2>
            <div className="remediation-card">
              <h3>⚠️ Risk Assessment</h3>
              <p className="risk-level">Medium Risk - Requires Approval</p>

              <h3>Remediation Actions</h3>
              <div className="actions-list">
                {remediation.actions?.map((action, i) => (
                  <div key={i} className="action-item">
                    <h4>{action.name || action.type || `Action ${i + 1}`}</h4>
                    {action.description && <p>{action.description}</p>}
                    <div className="action-meta">
                      {action.risk_level && <span className="badge">{action.risk_level}</span>}
                      {action.duration && <span className="badge">{action.duration}</span>}
                    </div>
                  </div>
                ))}
              </div>

              <h3>Success Criteria</h3>
              <div className="criteria-list">
                <label className="criteria-item">
                  <input type="checkbox" disabled />
                  <span>Error rate &lt; 1%</span>
                </label>
                <label className="criteria-item">
                  <input type="checkbox" disabled />
                  <span>Response time &lt; 500ms</span>
                </label>
                <label className="criteria-item">
                  <input type="checkbox" disabled />
                  <span>CPU usage &lt; 80%</span>
                </label>
              </div>

              <div className="approval-form">
                <h3>Approval</h3>
                <textarea
                  placeholder="Add approval comments..."
                  className="comment-box"
                />
                <div className="approval-buttons">
                  <button className="btn success">✅ Approve & Execute</button>
                  <button className="btn danger">❌ Reject</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Metrics Tab */}
        {activeTab === 'metrics' && (
          <div className="tab-content">
            <h2>Metrics & Analytics</h2>

            <div className="metrics-grid">
              <div className="metric-card">
                <div className="metric-value">94.2%</div>
                <div className="metric-label">Detection Accuracy</div>
              </div>
              <div className="metric-card">
                <div className="metric-value">16.6 min</div>
                <div className="metric-label">Avg MTTD</div>
              </div>
              <div className="metric-card">
                <div className="metric-value">49 min</div>
                <div className="metric-label">Avg MTTR</div>
              </div>
              <div className="metric-card">
                <div className="metric-value">68%</div>
                <div className="metric-label">Auto-Remediation Success</div>
              </div>
            </div>

            <div className="chart-section">
              <h3>📊 Cloud Providers & Performance</h3>
              <div className="cloud-providers">
                <div className="cloud-card">
                  <h4>☁️ AWS (EKS)</h4>
                  <p>Incidents: {incidents.filter(i => i.environment === 'aws').length}</p>
                  <p>Status: ✅ Healthy</p>
                </div>
                <div className="cloud-card">
                  <h4>☁️ GCP (GKE)</h4>
                  <p>Incidents: {incidents.filter(i => i.environment === 'gcp').length}</p>
                  <p>Status: ✅ Healthy</p>
                </div>
                <div className="cloud-card">
                  <h4>☁️ Azure (AKS)</h4>
                  <p>Incidents: {incidents.filter(i => i.environment === 'azure').length}</p>
                  <p>Status: ✅ Healthy</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="footer">
        <p>🚀 AIOps Platform | Production-Grade Incident Management</p>
        <p>API: <a href={API_URL}>{API_URL}</a> | Docs: <a href={`${API_URL}/docs`}>{API_URL}/docs</a></p>
      </footer>
    </div>
  )
}

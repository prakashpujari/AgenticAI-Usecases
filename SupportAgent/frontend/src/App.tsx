export default function App() {
  return (
    <div style={{ padding: '40px', fontFamily: 'Arial, sans-serif', backgroundColor: '#f5f5f5', minHeight: '100vh' }}>
      <h1>🚀 AIOps Platform</h1>
      <p style={{ fontSize: '16px', color: '#666' }}>Frontend is running successfully!</p>

      <div style={{ marginTop: '30px', padding: '20px', backgroundColor: '#fff', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
        <h2>Backend Status</h2>
        <p>API Health: <a href="http://localhost:8000/health" target="_blank" rel="noopener noreferrer">http://localhost:8000/health</a></p>
        <p>API Docs: <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer">http://localhost:8000/docs</a></p>
      </div>

      <div style={{ marginTop: '20px', padding: '20px', backgroundColor: '#fff', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
        <h3>Dashboard Features</h3>
        <ul style={{ lineHeight: '1.8' }}>
          <li>✅ Real-time incident detection</li>
          <li>✅ Root Cause Analysis (RCA)</li>
          <li>✅ Auto-remediation approval workflow</li>
          <li>✅ Metrics and analytics</li>
          <li>✅ Multi-cloud support</li>
        </ul>
      </div>

      <div style={{ marginTop: '20px', padding: '20px', backgroundColor: '#e8f5e9', borderRadius: '8px' }}>
        <h3>Quick Start</h3>
        <p>Create an incident via API:</p>
        <code style={{ backgroundColor: '#f5f5f5', padding: '10px', display: 'block', borderRadius: '4px', fontSize: '12px', overflowX: 'auto' }}>
          curl -X POST http://localhost:8000/api/v1/incidents
        </code>
      </div>
    </div>
  );
}

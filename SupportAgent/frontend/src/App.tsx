import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import IncidentDetails from './pages/IncidentDetails';
import RemediationApproval from './pages/RemediationApproval';
import Metrics from './pages/Metrics';

export default function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/incidents/:id" element={<IncidentDetails />} />
          <Route path="/remediation/:id" element={<RemediationApproval />} />
          <Route path="/metrics" element={<Metrics />} />
        </Routes>
      </Layout>
    </Router>
  );
}

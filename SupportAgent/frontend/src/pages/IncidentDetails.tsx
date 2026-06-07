import { useParams } from 'react-router-dom';
import { useState } from 'react';
import axios from 'axios';
import { FileText, Activity, Wrench } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function IncidentDetails() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState('overview');
  const [rcaLoading, setRcaLoading] = useState(false);
  const [remediationLoading, setRemediationLoading] = useState(false);

  const handleRunRCA = async () => {
    setRcaLoading(true);
    try {
      await axios.post(`${API_URL}/api/v1/incidents/${id}/rca`);
      // Refresh data
    } catch (error) {
      console.error('RCA failed:', error);
    } finally {
      setRcaLoading(false);
    }
  };

  const handleGenerateRemediation = async () => {
    setRemediationLoading(true);
    try {
      await axios.post(`${API_URL}/api/v1/incidents/${id}/remediation`);
      // Refresh data
    } catch (error) {
      console.error('Remediation generation failed:', error);
    } finally {
      setRemediationLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-2xl font-bold text-white mb-2">Database Connection Pool Exhaustion</h1>
            <p className="text-gray-400">INC-20240315120000-ABC12345</p>
          </div>
          <span className="bg-red-600 text-white px-4 py-2 rounded-lg font-semibold">P1 CRITICAL</span>
        </div>

        <div className="grid grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-gray-500 font-semibold">Status</p>
            <p className="text-white mt-1">Analyzing</p>
          </div>
          <div>
            <p className="text-gray-500 font-semibold">Affected Services</p>
            <p className="text-white mt-1">API, Database, Cache</p>
          </div>
          <div>
            <p className="text-gray-500 font-semibold">Environment</p>
            <p className="text-white mt-1">production</p>
          </div>
          <div>
            <p className="text-gray-500 font-semibold">Detected At</p>
            <p className="text-white mt-1">2024-03-15 12:00:00</p>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-4">
        <button
          onClick={handleRunRCA}
          disabled={rcaLoading}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold"
        >
          <FileText className="w-4 h-4" />
          {rcaLoading ? 'Analyzing...' : 'Run RCA'}
        </button>
        <button
          onClick={handleGenerateRemediation}
          disabled={remediationLoading}
          className="flex items-center gap-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold"
        >
          <Wrench className="w-4 h-4" />
          {remediationLoading ? 'Generating...' : 'Generate Remediation'}
        </button>
      </div>

      {/* Tabs */}
      <div className="bg-gray-800 rounded-lg border border-gray-700">
        <div className="flex border-b border-gray-700">
          {['overview', 'rca', 'evidence'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-6 py-3 font-semibold transition ${
                activeTab === tab
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              {tab.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="p-6">
          {activeTab === 'overview' && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Description</h3>
                <p className="text-gray-300">
                  Detected elevated database connection pool exhaustion on the primary production database.
                  Connection pool utilization reached 95% causing API timeout errors.
                </p>
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">Affected Components</h3>
                <ul className="text-gray-300 list-disc list-inside space-y-1">
                  <li>PostgreSQL Primary (db.prod.internal:5432)</li>
                  <li>API Server (api.prod.internal:8000)</li>
                  <li>Redis Cache (cache.prod.internal:6379)</li>
                </ul>
              </div>
            </div>
          )}

          {activeTab === 'rca' && (
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-700">
                <p className="font-semibold">Running RCA analysis...</p>
              </div>
              <div>
                <h4 className="font-semibold text-white mb-2">Root Cause (Preliminary)</h4>
                <p className="text-gray-300">
                  A recent deployment introduced a query N+1 problem in the user service that causes
                  excess database connections without proper connection pooling.
                </p>
              </div>
            </div>
          )}

          {activeTab === 'evidence' && (
            <div className="space-y-4">
              <div className="bg-gray-700 rounded p-4">
                <h4 className="font-semibold text-white mb-2">Recent Logs</h4>
                <p className="text-gray-300 text-sm font-mono">
                  [ERROR] Connection pool exhausted: max_connections=100, active_connections=100
                </p>
              </div>
              <div className="bg-gray-700 rounded p-4">
                <h4 className="font-semibold text-white mb-2">Metrics</h4>
                <p className="text-gray-300 text-sm">
                  PostgreSQL connections: 100/100 (95% utilization)
                  <br />
                  API error rate: 45%
                  <br />
                  API p99 latency: 15000ms
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { AlertTriangle, AlertCircle, AlertSquare, Info } from 'lucide-react';
import axios from 'axios';

interface Incident {
  id: string;
  incident_number: string;
  title: string;
  severity: string;
  status: string;
  confidence_score: number;
  affected_services: string[];
  detected_at: string;
  environment: string;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function Dashboard() {
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [filterEnvironment, setFilterEnvironment] = useState<string>('all');

  const { data: incidents = [], isLoading, error } = useQuery({
    queryKey: ['incidents'],
    queryFn: async () => {
      const response = await axios.get(`${API_URL}/api/v1/incidents`);
      return response.data;
    },
    refetchInterval: 5000, // Refetch every 5 seconds
  });

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'P1_CRITICAL':
        return 'text-red-600 bg-red-100';
      case 'P2_HIGH':
        return 'text-orange-600 bg-orange-100';
      case 'P3_MEDIUM':
        return 'text-yellow-600 bg-yellow-100';
      case 'P4_LOW':
        return 'text-blue-600 bg-blue-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'P1_CRITICAL':
        return <AlertTriangle className="w-5 h-5" />;
      case 'P2_HIGH':
        return <AlertCircle className="w-5 h-5" />;
      case 'P3_MEDIUM':
        return <AlertSquare className="w-5 h-5" />;
      case 'P4_LOW':
        return <Info className="w-5 h-5" />;
      default:
        return <AlertCircle className="w-5 h-5" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, { color: string; label: string }> = {
      DETECTED: { color: 'bg-red-500', label: 'Detected' },
      ANALYZING: { color: 'bg-yellow-500', label: 'Analyzing' },
      RESOLVED: { color: 'bg-green-500', label: 'Resolved' },
      ESCALATED: { color: 'bg-purple-500', label: 'Escalated' },
      FALSE_POSITIVE: { color: 'bg-gray-500', label: 'False Positive' },
    };

    const mapEntry = statusMap[status] || { color: 'bg-gray-500', label: status };
    return (
      <span className={`${mapEntry.color} text-white px-2 py-1 rounded text-xs font-semibold`}>
        {mapEntry.label}
      </span>
    );
  };

  const filteredIncidents = incidents.filter((incident: Incident) => {
    if (filterSeverity !== 'all' && incident.severity !== filterSeverity) return false;
    if (filterEnvironment !== 'all' && incident.environment !== filterEnvironment) return false;
    return true;
  });

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        <p className="font-semibold">Error loading incidents</p>
        <p className="text-sm">{String(error)}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-white">Incident Dashboard</h1>
          <p className="text-gray-400 mt-2">Real-time incident detection and management</p>
        </div>
        <button className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg font-semibold">
          Trigger Detection
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <p className="text-gray-400 text-sm font-semibold">TOTAL INCIDENTS</p>
          <p className="text-3xl font-bold text-white mt-2">{incidents.length}</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <p className="text-gray-400 text-sm font-semibold">P1 CRITICAL</p>
          <p className="text-3xl font-bold text-red-500 mt-2">
            {incidents.filter((i: Incident) => i.severity === 'P1_CRITICAL').length}
          </p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <p className="text-gray-400 text-sm font-semibold">ANALYZING</p>
          <p className="text-3xl font-bold text-yellow-500 mt-2">
            {incidents.filter((i: Incident) => i.status === 'ANALYZING').length}
          </p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <p className="text-gray-400 text-sm font-semibold">RESOLVED</p>
          <p className="text-3xl font-bold text-green-500 mt-2">
            {incidents.filter((i: Incident) => i.status === 'RESOLVED').length}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <select
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
          className="bg-gray-800 text-white rounded-lg px-4 py-2 border border-gray-700"
        >
          <option value="all">All Severities</option>
          <option value="P1_CRITICAL">P1 Critical</option>
          <option value="P2_HIGH">P2 High</option>
          <option value="P3_MEDIUM">P3 Medium</option>
          <option value="P4_LOW">P4 Low</option>
        </select>

        <select
          value={filterEnvironment}
          onChange={(e) => setFilterEnvironment(e.target.value)}
          className="bg-gray-800 text-white rounded-lg px-4 py-2 border border-gray-700"
        >
          <option value="all">All Environments</option>
          <option value="prod">Production</option>
          <option value="staging">Staging</option>
          <option value="dev">Development</option>
        </select>
      </div>

      {/* Incidents Table */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-900 border-b border-gray-700">
            <tr>
              <th className="px-6 py-3 text-left text-gray-300 font-semibold">Incident</th>
              <th className="px-6 py-3 text-left text-gray-300 font-semibold">Severity</th>
              <th className="px-6 py-3 text-left text-gray-300 font-semibold">Status</th>
              <th className="px-6 py-3 text-left text-gray-300 font-semibold">Services</th>
              <th className="px-6 py-3 text-left text-gray-300 font-semibold">Confidence</th>
              <th className="px-6 py-3 text-left text-gray-300 font-semibold">Detected</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-6 py-4 text-center text-gray-400">
                  Loading incidents...
                </td>
              </tr>
            ) : filteredIncidents.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-4 text-center text-gray-400">
                  No incidents detected
                </td>
              </tr>
            ) : (
              filteredIncidents.map((incident: Incident) => (
                <tr key={incident.id} className="hover:bg-gray-700 transition">
                  <td className="px-6 py-4">
                    <a href={`/incidents/${incident.id}`} className="text-blue-400 hover:text-blue-300">
                      <p className="font-semibold">{incident.title}</p>
                      <p className="text-xs text-gray-500">{incident.incident_number}</p>
                    </a>
                  </td>
                  <td className="px-6 py-4">
                    <div className={`flex items-center gap-2 w-fit p-2 rounded ${getSeverityColor(incident.severity)}`}>
                      {getSeverityIcon(incident.severity)}
                      <span className="text-sm font-semibold">{incident.severity}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {getStatusBadge(incident.status)}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-300">
                    {incident.affected_services.join(', ')}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-gray-700 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all ${
                            incident.confidence_score > 0.85
                              ? 'bg-red-500'
                              : incident.confidence_score > 0.7
                              ? 'bg-yellow-500'
                              : 'bg-green-500'
                          }`}
                          style={{ width: `${incident.confidence_score * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400">
                        {(incident.confidence_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {new Date(incident.detected_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

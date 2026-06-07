import { useParams } from 'react-router-dom';
import { useState } from 'react';
import axios from 'axios';
import { CheckCircle, XCircle } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function RemediationApproval() {
  const { id } = useParams<{ id: string }>();
  const [approvalComment, setApprovalComment] = useState('');
  const [loading, setLoading] = useState(false);

  const handleApprove = async () => {
    setLoading(true);
    try {
      await axios.post(`${API_URL}/api/v1/remediation/${id}/approve`, {
        approved_by: 'current_user',
        approval_comment: approvalComment,
      });
      alert('Remediation approved');
    } catch (error) {
      console.error('Approval failed:', error);
      alert('Failed to approve remediation');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    alert('Remediation rejected');
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h1 className="text-2xl font-bold text-white mb-4">Remediation Approval</h1>

        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6 text-yellow-800">
          <p className="font-semibold mb-2">⚠️ This is a P1 CRITICAL incident</p>
          <p>Approval from a senior engineer is required before execution.</p>
        </div>

        {/* Remediation Actions */}
        <div className="space-y-4 mb-6">
          <h2 className="text-lg font-semibold text-white">Proposed Actions</h2>

          <div className="bg-gray-700 rounded-lg p-4 border border-gray-600">
            <div className="flex justify-between items-start mb-3">
              <div>
                <h3 className="font-semibold text-white">Increase Database Connection Pool</h3>
                <p className="text-gray-400 text-sm mt-1">
                  Temporary measure to handle traffic spike
                </p>
              </div>
              <span className="bg-blue-600 text-white px-3 py-1 rounded text-sm font-semibold">
                Step 1
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-gray-400">Risk Level</p>
                <p className="text-white font-semibold">Low</p>
              </div>
              <div>
                <p className="text-gray-400">Est. Duration</p>
                <p className="text-white font-semibold">5 minutes</p>
              </div>
              <div>
                <p className="text-gray-400">Rollback Possible</p>
                <p className="text-green-400 font-semibold">✓ Yes</p>
              </div>
              <div>
                <p className="text-gray-400">Requires Approval</p>
                <p className="text-white font-semibold">Yes</p>
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-gray-600">
              <p className="text-sm text-gray-400 font-semibold mb-2">Implementation:</p>
              <code className="text-xs bg-gray-800 p-2 rounded block text-gray-300">
                alter system set max_connections = 150;
                <br />
                select pg_reload_conf();
              </code>
            </div>
          </div>

          <div className="bg-gray-700 rounded-lg p-4 border border-gray-600">
            <div className="flex justify-between items-start mb-3">
              <div>
                <h3 className="font-semibold text-white">Rollback Bad Deployment</h3>
                <p className="text-gray-400 text-sm mt-1">
                  Revert to previous stable version
                </p>
              </div>
              <span className="bg-blue-600 text-white px-3 py-1 rounded text-sm font-semibold">
                Step 2
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-gray-400">Risk Level</p>
                <p className="text-white font-semibold">Medium</p>
              </div>
              <div>
                <p className="text-gray-400">Est. Duration</p>
                <p className="text-white font-semibold">10 minutes</p>
              </div>
            </div>
          </div>
        </div>

        {/* Success Criteria */}
        <div className="bg-gray-700 rounded-lg p-4 border border-gray-600 mb-6">
          <h3 className="font-semibold text-white mb-3">Success Criteria</h3>
          <ul className="space-y-2 text-sm text-gray-300">
            <li>✓ Database connection pool utilization drops below 80%</li>
            <li>✓ API error rate returns to below 0.5%</li>
            <li>✓ P99 latency returns to below 500ms</li>
            <li>✓ No customer-facing errors</li>
          </ul>
        </div>

        {/* Approval Form */}
        <div className="bg-gray-700 rounded-lg p-4 border border-gray-600 space-y-4">
          <h3 className="font-semibold text-white">Approval Review</h3>

          <div>
            <label className="block text-gray-300 font-semibold mb-2">Comments</label>
            <textarea
              value={approvalComment}
              onChange={(e) => setApprovalComment(e.target.value)}
              placeholder="Add any notes or concerns..."
              className="w-full bg-gray-800 text-white rounded-lg p-3 border border-gray-600 focus:border-blue-500 outline-none"
              rows={4}
            />
          </div>

          <div className="flex gap-4">
            <button
              onClick={handleApprove}
              disabled={loading}
              className="flex items-center gap-2 flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-4 py-3 rounded-lg font-semibold transition"
            >
              <CheckCircle className="w-5 h-5" />
              {loading ? 'Approving...' : 'Approve & Execute'}
            </button>
            <button
              onClick={handleReject}
              disabled={loading}
              className="flex items-center gap-2 flex-1 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white px-4 py-3 rounded-lg font-semibold transition"
            >
              <XCircle className="w-5 h-5" />
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

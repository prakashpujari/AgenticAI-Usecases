import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const mockMetricsData = [
  { time: '12:00', detected: 2, resolved: 1, analyzing: 1 },
  { time: '13:00', detected: 4, resolved: 3, analyzing: 2 },
  { time: '14:00', detected: 3, resolved: 4, analyzing: 1 },
  { time: '15:00', detected: 5, resolved: 2, analyzing: 3 },
  { time: '16:00', detected: 2, resolved: 5, analyzing: 1 },
];

const mockMTTDData = [
  { date: 'Mon', mttr: 45, mttd: 15 },
  { date: 'Tue', mttr: 52, mttd: 18 },
  { date: 'Wed', mttr: 38, mttd: 12 },
  { date: 'Thu', mttr: 61, mttd: 22 },
  { date: 'Fri', mttr: 48, mttd: 16 },
];

export default function Metrics() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white">Platform Metrics</h1>
        <p className="text-gray-400 mt-2">Real-time observability and performance data</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <p className="text-gray-400 text-sm font-semibold">DETECTION ACCURACY</p>
          <p className="text-3xl font-bold text-green-500 mt-2">94.2%</p>
          <p className="text-xs text-gray-500 mt-2">↑ 2.3% this week</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <p className="text-gray-400 text-sm font-semibold">AVG MTTD</p>
          <p className="text-3xl font-bold text-blue-500 mt-2">16.6m</p>
          <p className="text-xs text-gray-500 mt-2">Mean Time To Detect</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <p className="text-gray-400 text-sm font-semibold">AVG MTTR</p>
          <p className="text-3xl font-bold text-orange-500 mt-2">49m</p>
          <p className="text-xs text-gray-500 mt-2">Mean Time To Resolve</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <p className="text-gray-400 text-sm font-semibold">AUTO REMEDIATION</p>
          <p className="text-3xl font-bold text-purple-500 mt-2">68%</p>
          <p className="text-xs text-gray-500 mt-2">Success Rate</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-6">
        {/* Incident Timeline */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-lg font-semibold text-white mb-4">Incidents Over Time</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={mockMetricsData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="time" stroke="#9CA3AF" />
              <YAxis stroke="#9CA3AF" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1F2937',
                  border: '1px solid #4B5563',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: '#F3F4F6' }}
              />
              <Legend />
              <Bar dataKey="detected" fill="#EF4444" />
              <Bar dataKey="analyzing" fill="#F59E0B" />
              <Bar dataKey="resolved" fill="#10B981" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* MTTD vs MTTR */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-lg font-semibold text-white mb-4">MTTD vs MTTR</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={mockMTTDData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" stroke="#9CA3AF" />
              <YAxis stroke="#9CA3AF" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1F2937',
                  border: '1px solid #4B5563',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: '#F3F4F6' }}
              />
              <Legend />
              <Line type="monotone" dataKey="mttd" stroke="#3B82F6" strokeWidth={2} name="MTTD (minutes)" />
              <Line type="monotone" dataKey="mttr" stroke="#F97316" strokeWidth={2} name="MTTR (minutes)" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Detailed Stats */}
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4">Incidents by Severity</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-400">P1 Critical</span>
              <div className="flex items-center gap-2">
                <div className="w-24 bg-gray-700 rounded-full h-2">
                  <div className="h-2 rounded-full bg-red-500" style={{ width: '35%' }} />
                </div>
                <span className="text-white font-semibold">35 (45%)</span>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">P2 High</span>
              <div className="flex items-center gap-2">
                <div className="w-24 bg-gray-700 rounded-full h-2">
                  <div className="h-2 rounded-full bg-orange-500" style={{ width: '28%' }} />
                </div>
                <span className="text-white font-semibold">28 (36%)</span>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">P3 Medium</span>
              <div className="flex items-center gap-2">
                <div className="w-24 bg-gray-700 rounded-full h-2">
                  <div className="h-2 rounded-full bg-yellow-500" style={{ width: '12%' }} />
                </div>
                <span className="text-white font-semibold">12 (15%)</span>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">P4 Low</span>
              <div className="flex items-center gap-2">
                <div className="w-24 bg-gray-700 rounded-full h-2">
                  <div className="h-2 rounded-full bg-blue-500" style={{ width: '4%' }} />
                </div>
                <span className="text-white font-semibold">4 (5%)</span>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h3 className="text-lg font-semibold text-white mb-4">RCA Quality Metrics</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-400">RCA Accuracy</span>
              <span className="text-white font-semibold">89.5%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">False Positives</span>
              <span className="text-white font-semibold">5.2%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Avg RCA Time</span>
              <span className="text-white font-semibold">8.3 minutes</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">KB Match Rate</span>
              <span className="text-white font-semibold">74.3%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

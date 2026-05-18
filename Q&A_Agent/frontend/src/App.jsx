import { useState } from 'react'
import DocumentUpload from './components/DocumentUpload'
import JobStatus from './components/JobStatus'
import Dashboard from './components/Dashboard'

export default function App() {
  const [currentJobId, setCurrentJobId] = useState(null)
  const [activeTab, setActiveTab] = useState('pipeline')

  const handleJobSubmitted = (jobId) => {
    setCurrentJobId(jobId)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Q&A Agent</h1>
              <p className="text-gray-600 mt-1">Generate MCQ questions from any document</p>
            </div>
            {/* Tab navigation */}
            <nav className="flex gap-1 bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => setActiveTab('pipeline')}
                className={`px-4 py-2 text-sm font-medium rounded-md transition ${
                  activeTab === 'pipeline'
                    ? 'bg-white text-indigo-700 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Pipeline
              </button>
              <button
                onClick={() => setActiveTab('dashboard')}
                className={`px-4 py-2 text-sm font-medium rounded-md transition ${
                  activeTab === 'dashboard'
                    ? 'bg-white text-indigo-700 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Dashboard
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {activeTab === 'pipeline' ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Upload Section */}
            <div>
              <DocumentUpload onJobSubmitted={handleJobSubmitted} />
            </div>

            {/* Status Section */}
            <div>
              {currentJobId ? (
                <JobStatus pipelineId={currentJobId} />
              ) : (
                <div className="bg-white rounded-lg shadow-md p-8 h-full flex items-center justify-center">
                  <div className="text-center">
                    <p className="text-gray-500 text-lg">Submit a document to see status</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <Dashboard />
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p className="text-sm text-gray-500">
            &copy; {new Date().getFullYear()} Q&amp;A Agent. All rights reserved.
          </p>
          <p className="text-sm font-semibold text-indigo-600 tracking-wide">
            Powered by PrakashPujariAI
          </p>
        </div>
      </footer>
    </div>
  )
}

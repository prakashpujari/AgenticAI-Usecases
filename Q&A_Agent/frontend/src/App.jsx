import { useState } from 'react'
import DocumentUpload from './components/DocumentUpload'
import JobStatus from './components/JobStatus'

export default function App() {
  const [currentJobId, setCurrentJobId] = useState(null)

  const handleJobSubmitted = (jobId) => {
    setCurrentJobId(jobId)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-3xl font-bold text-gray-900">Q&A Agent</h1>
          <p className="text-gray-600 mt-1">Generate MCQ questions from any document</p>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
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
      </main>
    </div>
  )
}

import { useState, useEffect } from 'react'
import axios from 'axios'

export default function JobStatus({ pipelineId }) {
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const getFileName = (filePath) => {
    if (!filePath) return ''
    return filePath.split(/[\\/]/).pop()
  }

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await axios.get(`/api/qa/status/${pipelineId}`)
        setJob(response.data)
        setError(null)
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to fetch status')
      } finally {
        setLoading(false)
      }
    }

    fetchStatus()

    // Poll every 2 seconds if not completed or failed
    const interval = setInterval(fetchStatus, 2000)
    return () => clearInterval(interval)
  }, [pipelineId])

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-8">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          <p className="ml-3 text-gray-600">Loading status...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-md p-8">
        <p className="text-red-600">{error}</p>
      </div>
    )
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'queued':
        return 'bg-yellow-100 text-yellow-800'
      case 'processing':
        return 'bg-blue-100 text-blue-800'
      case 'completed':
        return 'bg-green-100 text-green-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'queued':
        return '⏳'
      case 'processing':
        return '⚙️'
      case 'completed':
        return '✅'
      case 'failed':
        return '❌'
      default:
        return '❓'
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-8">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Job Status</h2>

      {/* Status Card */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">Pipeline ID</p>
            <p className="text-lg font-mono text-gray-900">{pipelineId}</p>
          </div>
          <div
            className={`px-4 py-2 rounded-full font-medium text-sm ${getStatusColor(job.status)}`}
          >
            {getStatusIcon(job.status)} {job.status.toUpperCase()}
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="space-y-4 mb-6">
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wide">Created At</p>
          <p className="text-sm text-gray-700">
            {new Date(job.created_at).toLocaleString()}
          </p>
        </div>
        {job.updated_at && (
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wide">Last Updated</p>
            <p className="text-sm text-gray-700">
              {new Date(job.updated_at).toLocaleString()}
            </p>
          </div>
        )}
      </div>

      {/* Input Source */}
      <div className="mb-6 p-3 bg-gray-50 rounded-md">
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Input Source</p>
        <p className="text-sm text-gray-700 break-all font-mono">{job.input_source}</p>
      </div>

      {/* Queue Position */}
      {job.status === 'queued' && job.queue_position !== null && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
          <p className="text-sm text-yellow-800">
            Position in queue: <strong>#{job.queue_position}</strong>
          </p>
        </div>
      )}

      {/* Results */}
      {job.status === 'completed' && (
        <div className="space-y-4">
          {job.result_markdown && (
            <div>
              <h3 className="font-semibold text-gray-900 mb-2">Generated Questions</h3>
              <div className="bg-gray-50 rounded-md p-4 max-h-64 overflow-y-auto">
                <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono">
                  {job.result_markdown.substring(0, 500)}...
                </pre>
              </div>
            </div>
          )}

          {job.result_pdf_path && (
            <div className="flex gap-2">
              <a
                href={`/api/qa/file/${pipelineId}/${getFileName(job.result_pdf_path)}`}
                download
                className="flex-1 bg-green-600 text-white font-medium py-2 px-4 rounded-md hover:bg-green-700 transition text-center"
              >
                📥 Download PDF
              </a>
              <button
                onClick={() => {
                  const filename = getFileName(job.result_pdf_path)
                  window.open(
                    `/api/qa/file/${pipelineId}/${filename}`,
                    '_blank'
                  )
                }}
                className="flex-1 bg-indigo-600 text-white font-medium py-2 px-4 rounded-md hover:bg-indigo-700 transition"
              >
                👁️ View PDF
              </button>
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {job.status === 'failed' && job.error_message && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm font-medium text-red-900">Error</p>
          <p className="text-sm text-red-700 mt-1">{job.error_message}</p>
        </div>
      )}

      {/* Processing Indicator */}
      {job.status === 'processing' && (
        <div className="flex items-center gap-2 text-blue-600">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
          <p className="text-sm">Processing your document...</p>
        </div>
      )}
    </div>
  )
}

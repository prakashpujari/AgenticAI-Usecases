import { useState } from 'react'
import axios from 'axios'

export default function DocumentUpload({ onJobSubmitted }) {
  const [inputMode, setInputMode] = useState('file')
  const [file, setFile] = useState(null)
  const [source, setSource] = useState('')
  const [numQuestions, setNumQuestions] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [dragActive, setDragActive] = useState(false)

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    const files = e.dataTransfer.files
    if (files && files[0]) {
      setFile(files[0])
      setError(null)
    }
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setError(null)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (inputMode === 'file') {
      if (!file) {
        setError('Please select a file')
        return
      }
    } else {
      if (!source.trim()) {
        setError('Please provide a website URL, YouTube URL, or local path')
        return
      }
    }

    setLoading(true)
    setError(null)

    try {
      let response
      if (inputMode === 'file') {
        const formData = new FormData()
        formData.append('file', file)
        formData.append('num_questions', numQuestions)
        response = await axios.post('/api/qa/generate', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      } else {
        response = await axios.post('/api/qa/generate-source', {
          source: source.trim(),
          num_questions: numQuestions,
        })
      }

      onJobSubmitted(response.data.pipeline_id)
      setFile(null)
      setSource('')
      setNumQuestions(5)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit job')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-8">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Upload Document</h2>

      <div className="mb-6 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => {
            setInputMode('file')
            setError(null)
          }}
          className={`px-4 py-2 rounded-md border font-medium transition ${
            inputMode === 'file'
              ? 'bg-indigo-600 text-white border-indigo-600'
              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
          }`}
        >
          Local File
        </button>
        <button
          type="button"
          onClick={() => {
            setInputMode('source')
            setError(null)
          }}
          className={`px-4 py-2 rounded-md border font-medium transition ${
            inputMode === 'source'
              ? 'bg-indigo-600 text-white border-indigo-600'
              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
          }`}
        >
          URL / Source
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        {inputMode === 'file' ? (
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition ${
              dragActive
                ? 'border-indigo-500 bg-indigo-50'
                : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <input
              type="file"
              onChange={handleFileChange}
              accept=".pdf,.txt,.md,.docx,.xlsx,.csv,.png,.jpg,.jpeg,.webp,.mp3,.wav,.m4a,.aac,.webm,.mp4,.mov,.avi,.mkv"
              className="hidden"
              id="file-input"
              disabled={loading}
            />
            <label htmlFor="file-input" className="cursor-pointer">
              <div className="space-y-2">
                <svg
                  className="mx-auto h-12 w-12 text-gray-400"
                  stroke="currentColor"
                  fill="none"
                  viewBox="0 0 48 48"
                >
                  <path
                    d="M28 8H12a4 4 0 00-4 4v20a4 4 0 004 4h24a4 4 0 004-4V20"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {file ? file.name : 'Drag and drop your file here'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    PDF, text, doc, sheet, image, audio, or video
                  </p>
                </div>
              </div>
            </label>
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Source URL or Path
            </label>
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="https://example.com/article OR https://youtube.com/watch?v=..."
              disabled={loading}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            />
            <p className="text-xs text-gray-500 mt-2">
              Supports website URLs, YouTube URLs, and server-accessible local paths.
            </p>
          </div>
        )}

        {/* Number of Questions */}
        <div className="mt-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Number of Questions
          </label>
          <input
            type="number"
            min="1"
            max="20"
            value={numQuestions}
            onChange={(e) => setNumQuestions(parseInt(e.target.value))}
            disabled={loading}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
          />
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading || (inputMode === 'file' ? !file : !source.trim())}
          className="w-full mt-6 bg-indigo-600 text-white font-medium py-2 px-4 rounded-md hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
        >
          {loading ? 'Submitting...' : 'Generate Questions'}
        </button>
      </form>

      {/* Supported Formats */}
      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
        <h3 className="text-sm font-medium text-blue-900">Supported Formats</h3>
        <ul className="text-sm text-blue-800 mt-2 space-y-1">
          <li>• PDF documents</li>
          <li>• Text files (TXT, MD, RST)</li>
          <li>• Word documents (DOCX)</li>
          <li>• Spreadsheets (XLSX, CSV)</li>
          <li>• Website and YouTube URLs</li>
          <li>• Images (PNG, JPG, WEBP)</li>
          <li>• Audio and video (MP3, WAV, MP4, WEBM)</li>
        </ul>
      </div>
    </div>
  )
}

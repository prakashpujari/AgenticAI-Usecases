import { useState } from 'react'
import axios from 'axios'
import RateLimitBanner from './RateLimitBanner'
import { parseApiError, getDeviceFingerprint } from '../utils/errorHandler'

const MAX_FILE_BYTES = 50 * 1024 * 1024 // 50 MB

// ── YouTube helpers ────────────────────────────────────────────────────────
function isYouTubeUrl(url) {
  return /(?:youtube\.com|youtu\.be)/i.test(url)
}
function extractVideoId(url) {
  const patterns = [
    /[?&]v=([A-Za-z0-9_-]{11})/,
    /youtu\.be\/([A-Za-z0-9_-]{11})/,
    /\/shorts\/([A-Za-z0-9_-]{11})/,
    /\/live\/([A-Za-z0-9_-]{11})/,
    /\/embed\/([A-Za-z0-9_-]{11})/,
  ]
  for (const p of patterns) {
    const m = url.match(p)
    if (m) return m[1]
  }
  return null
}
const ALLOWED_EXTENSIONS = new Set([
  // Documents
  'pdf','txt','md','rst','docx',
  // Spreadsheets
  'xlsx','xls','csv',
  // Images
  'png','jpg','jpeg','webp',
  // Audio / Video
  'mp3','wav','m4a','mp4','mov','avi','webm','mkv',
])

const ACCEPTED_LABEL = 'PDF, DOCX, TXT, MD, RST · XLSX, XLS, CSV · PNG, JPG, JPEG, WEBP · MP3, WAV, M4A, MP4, MOV, AVI, WEBM, MKV'

function validateFileClient(f) {
  const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
  if (!ALLOWED_EXTENSIONS.has(ext))
    return `Unsupported file type ".${ext}". Accepted: ${ACCEPTED_LABEL}`
  if (f.size > MAX_FILE_BYTES)
    return `File is too large (${(f.size / 1024 / 1024).toFixed(1)} MB). Maximum is 50 MB.`
  return null
}

export default function DocumentUpload({ onJobSubmitted }) {
  const [inputMode, setInputMode] = useState('file')
  const [outputMode, setOutputMode] = useState('questions')
  const [file, setFile] = useState(null)
  const [source, setSource] = useState('')
  const [numQuestions, setNumQuestions] = useState(5)
  const [loading, setLoading] = useState(false)
  const [loadingMsg, setLoadingMsg] = useState('Submitting...')
  const [error, setError] = useState(null)
  const [rateLimitInfo, setRateLimitInfo] = useState(null) // { retryAfter, debugId }
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
      const f = e.target.files[0]
      const clientErr = validateFileClient(f)
      if (clientErr) { setError(clientErr); return }
      setFile(f)
      setError(null)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (inputMode === 'file') {
      if (!file) { setError('Please select a file'); return }
    } else {
      if (!source.trim()) { setError('Please provide a URL or path'); return }
    }

    setLoading(true)
    setLoadingMsg('Submitting...')
    setError(null)
    setRateLimitInfo(null)

    try {
      const fingerprint = await getDeviceFingerprint()
      const headers = { 'X-Device-Fingerprint': fingerprint }
      let response

      if (inputMode === 'file') {
        // ── File upload path ────────────────────────────────────────────────
        const formData = new FormData()
        formData.append('file', file)
        formData.append('num_questions', numQuestions)
        formData.append('output_mode', outputMode)
        response = await axios.post('/api/qa/generate', formData, {
          headers: { ...headers, 'Content-Type': 'multipart/form-data' },
        })
      } else {
        const src = source.trim()

        // ── YouTube: try Vercel proxy first ────────────────────────────────
        if (isYouTubeUrl(src)) {
          const videoId = extractVideoId(src)
          if (videoId) {
            setLoadingMsg('Fetching YouTube transcript...')
            try {
              const proxyRes = await axios.get(
                `/api/youtube-transcript?videoId=${videoId}`,
                { timeout: 45000 }
              )
              const transcript = proxyRes.data?.transcript
              if (transcript && transcript.length > 50) {
                // Convert transcript text to a virtual .txt file and submit
                setLoadingMsg('Transcript fetched — submitting...')
                const blob = new Blob([transcript], { type: 'text/plain' })
                const txtFile = new File([blob], `youtube-${videoId}.txt`, { type: 'text/plain' })
                const formData = new FormData()
                formData.append('file', txtFile)
                formData.append('num_questions', numQuestions)
                formData.append('output_mode', outputMode)
                response = await axios.post('/api/qa/generate', formData, {
                  headers: { ...headers, 'Content-Type': 'multipart/form-data' },
                })
                onJobSubmitted(response.data.pipeline_id)
                setFile(null); setSource(''); setNumQuestions(5)
                return
              }
            } catch (_proxyErr) {
              // Proxy failed — fall through to backend (3-layer Whisper fallback)
              setLoadingMsg('Falling back to server processing...')
            }
          }
        }

        // ── Regular URL / YouTube fallback to Render backend ───────────────
        response = await axios.post('/api/qa/generate-source', {
          source: src,
          num_questions: numQuestions,
          output_mode: outputMode,
        }, { headers })
      }

      onJobSubmitted(response.data.pipeline_id)
      setFile(null); setSource(''); setNumQuestions(5)
    } catch (err) {
      const parsed = parseApiError(err)
      if (parsed.errorCode === 'RATE_LIMIT_EXCEEDED' || parsed.errorCode === 'SPIKE_ARREST') {
        setRateLimitInfo({ retryAfter: parsed.retryAfter, debugId: parsed.debugId })
      } else {
        setError(parsed.message)
      }
    } finally {
      setLoading(false)
      setLoadingMsg('Submitting...')
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-8">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Upload Document</h2>

      {/* Input mode toggle */}
      <div className="mb-6 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => { setInputMode('file'); setError(null) }}
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
          onClick={() => { setInputMode('source'); setError(null) }}
          className={`px-4 py-2 rounded-md border font-medium transition ${
            inputMode === 'source'
              ? 'bg-indigo-600 text-white border-indigo-600'
              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
          }`}
        >
          URL / Source
        </button>
      </div>

      {/* Output mode selector */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          What would you like to generate?
        </label>
        <div className="grid grid-cols-3 gap-2">
          {[
            { value: 'text',      label: '📄 Captured Text',   desc: 'LLM summary of the document' },
            { value: 'questions', label: '❓ Q&A Questions',    desc: 'Multiple-choice questions' },
            { value: 'both',      label: '📋 Both',             desc: 'Summary + questions' },
          ].map(({ value, label, desc }) => (
            <button
              key={value}
              type="button"
              onClick={() => setOutputMode(value)}
              className={`flex flex-col items-center px-3 py-3 rounded-md border text-sm font-medium transition ${
                outputMode === value
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              <span>{label}</span>
              <span className={`text-xs mt-1 ${outputMode === value ? 'text-indigo-100' : 'text-gray-400'}`}>
                {desc}
              </span>
            </button>
          ))}
        </div>
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
              accept=".pdf,.txt,.md,.rst,.docx,.xlsx,.xls,.csv,.png,.jpg,.jpeg,.webp,.mp3,.wav,.m4a,.mp4,.mov,.avi,.webm,.mkv"
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

        {/* Number of Questions — hidden when text-only mode */}
        {outputMode !== 'text' && (
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
        )}

        {/* Rate-limit countdown */}
        {rateLimitInfo && (
          <RateLimitBanner
            retryAfter={rateLimitInfo.retryAfter}
            debugId={rateLimitInfo.debugId}
            onExpired={() => setRateLimitInfo(null)}
          />
        )}

        {/* General error */}
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
          {loading ? loadingMsg : 'Generate Questions'}
        </button>
      </form>

      {/* Supported Formats */}
      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
        <h3 className="text-sm font-medium text-blue-900">Supported Formats</h3>
        <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-sm text-blue-800">
          <span>📄 Documents — PDF, TXT, MD, RST, DOCX</span>
          <span>📊 Spreadsheets — XLSX, XLS, CSV</span>
          <span>🖼️ Images — PNG, JPG, JPEG, WEBP</span>
          <span>🎵 Audio — MP3, WAV, M4A</span>
          <span>🎬 Video — MP4, MOV, AVI, WEBM, MKV</span>
          <span>🔗 URLs — Web pages &amp; YouTube</span>
        </div>
      </div>
    </div>
  )
}

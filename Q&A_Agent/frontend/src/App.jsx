import { useState } from 'react'
import DocumentUpload from './components/DocumentUpload'
import JobStatus from './components/JobStatus'
import Dashboard from './components/Dashboard'

// ── Hero Banner ────────────────────────────────────────────────────────────────
function HeroBanner() {
  return (
    <div className="relative w-full rounded-2xl overflow-hidden shadow-2xl mb-10 group">
      {/* Image */}
      <img
        src="/hero.jpg"
        alt="AI Robot generating MCQ questions from a document"
        className="w-full h-56 sm:h-72 md:h-80 lg:h-96 object-cover object-center
                   transition-transform duration-700 group-hover:scale-105"
        onError={e => { e.currentTarget.style.display = 'none' }}
      />

      {/* Gradient overlay — dark left, transparent right */}
      <div className="absolute inset-0 bg-gradient-to-r
                      from-indigo-950/90 via-indigo-900/70 to-indigo-800/20" />

      {/* Text content */}
      <div className="absolute inset-0 flex flex-col justify-center px-8 sm:px-12 md:px-16">
        {/* Badge */}
        <span className="inline-flex items-center gap-2 bg-indigo-500/30 border border-indigo-400/40
                         text-indigo-200 text-xs font-semibold px-3 py-1 rounded-full w-fit mb-4
                         backdrop-blur-sm">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          Powered by Groq LPU · Gemini · LangGraph
        </span>

        <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-white leading-tight
                       drop-shadow-lg">
          AI-Powered Q&amp;A
          <br />
          <span className="text-indigo-300">Generation Agent</span>
        </h2>

        <p className="mt-3 text-indigo-100 text-sm sm:text-base max-w-md leading-relaxed
                      drop-shadow-md">
          Upload any document, paste a URL or YouTube link — get professional
          MCQ questions and summaries generated in seconds.
        </p>

        {/* Feature pills */}
        <div className="flex flex-wrap gap-2 mt-5">
          {[
            { icon: '📄', label: 'PDF / DOCX / TXT' },
            { icon: '🌐', label: 'Web URLs' },
            { icon: '🎥', label: 'YouTube' },
            { icon: '🧠', label: 'RAG Pipeline' },
            { icon: '⚡', label: 'Sub-3s Generation' },
          ].map(f => (
            <span key={f.label}
              className="flex items-center gap-1.5 bg-white/10 backdrop-blur-sm
                         border border-white/20 text-white text-xs font-medium
                         px-3 py-1 rounded-full">
              {f.icon} {f.label}
            </span>
          ))}
        </div>
      </div>

      {/* Corner accent */}
      <div className="absolute top-4 right-4 bg-white/10 backdrop-blur-sm border border-white/20
                      rounded-xl px-3 py-2 text-right hidden sm:block">
        <p className="text-white text-xs font-bold">Q&amp;A Agent</p>
        <p className="text-indigo-300 text-xs">Knowledge Extraction</p>
      </div>
    </div>
  )
}

// ── Empty State ───────────────────────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="bg-white rounded-2xl shadow-md overflow-hidden h-full flex flex-col">
      {/* Mini hero thumbnail */}
      <div className="relative h-40 overflow-hidden">
        <img
          src="/hero.jpg"
          alt="Q&A Agent"
          className="w-full h-full object-cover object-right-top opacity-60"
          onError={e => { e.currentTarget.parentElement.style.background = 'linear-gradient(135deg,#4f46e5,#7c3aed)' }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-white/90" />
      </div>
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center -mt-4">
        <div className="w-16 h-16 rounded-full bg-indigo-50 border-2 border-indigo-100
                        flex items-center justify-center text-3xl mb-4 shadow-inner">
          🤖
        </div>
        <h3 className="text-lg font-semibold text-gray-700">Ready to generate</h3>
        <p className="text-gray-400 text-sm mt-1 max-w-xs leading-relaxed">
          Submit a document on the left to start generating questions.
          Results will appear here in real time.
        </p>
        <div className="mt-6 grid grid-cols-3 gap-3 text-xs text-gray-400 w-full max-w-xs">
          {[
            ['📄','Upload file'],
            ['🔗','Paste URL'],
            ['🎥','YouTube link'],
          ].map(([icon, label]) => (
            <div key={label} className="bg-gray-50 border border-gray-100 rounded-lg p-2 text-center">
              <div className="text-xl mb-1">{icon}</div>
              {label}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  const [currentJobId, setCurrentJobId] = useState(null)
  const [activeTab, setActiveTab]       = useState('pipeline')

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100">

      {/* ── Header ── */}
      <header className="bg-white/80 backdrop-blur-md shadow-sm sticky top-0 z-40 border-b border-white/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between gap-4">
            {/* Logo + title */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600
                              flex items-center justify-center text-white text-lg font-bold shadow">
                Q
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900 leading-tight">Q&amp;A Agent</h1>
                <p className="text-xs text-gray-500 hidden sm:block">Generate MCQ questions from any document</p>
              </div>
            </div>

            {/* Tab nav */}
            <nav className="flex gap-1 bg-gray-100 rounded-xl p-1">
              {[
                { id: 'pipeline',  label: '⚡ Pipeline'  },
                { id: 'dashboard', label: '📊 Dashboard' },
              ].map(t => (
                <button key={t.id} onClick={() => setActiveTab(t.id)}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-all ${
                    activeTab === t.id
                      ? 'bg-white text-indigo-700 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}>
                  {t.label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

        {activeTab === 'pipeline' ? (
          <>
            {/* Hero image banner — only on Pipeline tab */}
            <HeroBanner />

            {/* Two-column layout */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <DocumentUpload onJobSubmitted={setCurrentJobId} />

              <div>
                {currentJobId
                  ? <JobStatus pipelineId={currentJobId} />
                  : <EmptyState />
                }
              </div>
            </div>
          </>
        ) : (
          <Dashboard />
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="bg-white/60 backdrop-blur-sm border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5
                        flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600
                            flex items-center justify-center text-white text-xs font-bold">
              Q
            </div>
            <p className="text-sm text-gray-500">
              &copy; {new Date().getFullYear()} Q&amp;A Agent · All rights reserved
            </p>
          </div>
          <p className="text-sm font-semibold text-indigo-600 tracking-wide">
            Powered by PrakashPujariAI
          </p>
        </div>
      </footer>
    </div>
  )
}

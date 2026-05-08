import React from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import CreateTicketPage from './pages/CreateTicketPage';
import ReviewTicketPage from './pages/ReviewTicketPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
    mutations: { retry: 0 },
  },
});

const NAV_ACTIVE =
  'text-indigo-600 border-b-2 border-indigo-600 pb-1 font-medium';
const NAV_IDLE =
  'text-gray-500 hover:text-gray-800 pb-1 font-medium transition-colors';

const App: React.FC = () => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        {/* Top nav */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
          <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold text-indigo-600">JiraAI</span>
              <span className="text-xs text-gray-400 hidden sm:block">
                Automation Agent
              </span>
            </div>
            <nav className="flex gap-6 text-sm">
              <NavLink
                to="/"
                end
                className={({ isActive }) => (isActive ? NAV_ACTIVE : NAV_IDLE)}
              >
                Create Ticket
              </NavLink>
              <NavLink
                to="/review"
                className={({ isActive }) => (isActive ? NAV_ACTIVE : NAV_IDLE)}
              >
                Review Ticket
              </NavLink>
            </nav>
          </div>
        </header>

        {/* Content */}
        <main>
          <Routes>
            <Route path="/" element={<CreateTicketPage />} />
            <Route path="/review" element={<ReviewTicketPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  </QueryClientProvider>
);

export default App;

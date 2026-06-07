import { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Activity, BarChart3, Menu } from 'lucide-react';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gray-900">
      {/* Navbar */}
      <nav className="bg-gray-800 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2 font-bold text-xl">
                <AlertTriangle className="w-6 h-6 text-red-500" />
                AIOps Platform
              </Link>
              <div className="hidden md:flex gap-6">
                <Link to="/" className="hover:text-gray-300 transition">
                  Dashboard
                </Link>
                <Link to="/metrics" className="hover:text-gray-300 transition">
                  Metrics
                </Link>
              </div>
            </div>
            <div className="text-sm text-gray-400">
              Status: <span className="text-green-400">Operational</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 text-gray-400 text-center py-4 mt-12">
        <p>AIOps Platform v1.0.0 | Enterprise Incident Detection & Remediation</p>
      </footer>
    </div>
  );
}

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/context/AuthContext";
import Layout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";
import LoginPage from "@/pages/LoginPage";
import AgentPage from "@/pages/AgentPage";
import MetricsPage from "@/pages/MetricsPage";
import HealthPage from "@/pages/HealthPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />

            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/agent"   element={<AgentPage />} />
                <Route path="/metrics" element={<MetricsPage />} />
                <Route path="/health"  element={<HealthPage />} />
              </Route>
            </Route>

            <Route path="*" element={<Navigate to="/agent" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

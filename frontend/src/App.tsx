import { BrowserRouter, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { History } from './pages/History';
import { HealthRecordForm } from './pages/HealthRecordForm';
import { AdminPanel } from './pages/AdminPanel';
import { Settings } from './pages/Settings';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Navbar } from './components/Navbar';
import { PageTransition } from './components/PageTransition';
import { BottomTabBar } from './components/BottomTabBar';
import { ThemeProvider } from './components/ThemeProvider';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: (failureCount, error: any) => {
        // Don't retry on 401 (unauthorized)
        if (error?.response?.status === 401) {
          return false;
        }
        return failureCount < 1; // Retry once for other errors
      },
      // Enable request deduplication - same queries will be deduplicated automatically
      staleTime: 30 * 1000, // Consider data fresh for 30 seconds to prevent duplicate requests
      gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
    },
  },
});

function AppRoutes() {
  return (
    <>
      <Navbar />
      <PageTransition>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/history"
          element={
            <ProtectedRoute>
              <History />
            </ProtectedRoute>
          }
        />
        <Route
          path="/form/:type"
          element={
            <ProtectedRoute>
              <HealthRecordForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/form/:type/:id"
          element={
            <ProtectedRoute>
              <HealthRecordForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <AdminPanel />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </PageTransition>
      <BottomTabBar />
    </>
  );
}

function App() {
  // Use root path everywhere - no basename needed
  const basename = '/';

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={basename}>
        <ThemeProvider>
          <AppRoutes />
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;

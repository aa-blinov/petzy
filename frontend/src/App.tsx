import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Navbar } from './components/Navbar';
import { BottomTabBar } from './components/BottomTabBar';
import { ThemeProvider } from './components/ThemeProvider';
import { LoadingSpinner } from './components/LoadingSpinner';

// Lazy load pages for code splitting
const Login = lazy(() => import('./pages/Login').then(m => ({ default: m.Login })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const History = lazy(() => import('./pages/History').then(m => ({ default: m.History })));
const HealthRecordForm = lazy(() => import('./pages/HealthRecordForm').then(m => ({ default: m.HealthRecordForm })));
const AdminPanel = lazy(() => import('./pages/AdminPanel').then(m => ({ default: m.AdminPanel })));
const UserForm = lazy(() => import('./pages/UserForm').then(m => ({ default: m.UserForm })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const Pets = lazy(() => import('./pages/Pets').then(m => ({ default: m.Pets })));
const PetForm = lazy(() => import('./pages/PetForm').then(m => ({ default: m.PetForm })));
const FormDefaults = lazy(() => import('./pages/FormDefaults').then(m => ({ default: m.FormDefaults })));
const TilesSettings = lazy(() => import('./pages/TilesSettings').then(m => ({ default: m.TilesSettings })));

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
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
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
            path="/pets"
            element={
              <ProtectedRoute>
                <Pets />
              </ProtectedRoute>
            }
          />
          <Route
            path="/pets/new"
            element={
              <ProtectedRoute>
                <PetForm />
              </ProtectedRoute>
            }
          />
          <Route
            path="/pets/:id/edit"
            element={
              <ProtectedRoute>
                <PetForm />
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
            path="/admin/users/new"
            element={
              <ProtectedRoute>
                <UserForm />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/users/:username/edit"
            element={
              <ProtectedRoute>
                <UserForm />
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
          <Route
            path="/form-defaults"
            element={
              <ProtectedRoute>
                <FormDefaults />
              </ProtectedRoute>
            }
          />
          <Route
            path="/tiles-settings"
            element={
              <ProtectedRoute>
                <TilesSettings />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
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
